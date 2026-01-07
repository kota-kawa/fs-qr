import os
import re
import secrets
import uuid
from datetime import timedelta
import shutil
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from werkzeug.utils import secure_filename

from rate_limit import (
    SCOPE_QR,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, render_template
from . import fsqr_data as fs_data

router = APIRouter()

# Base configuration (same as in app.py)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC = os.path.join(BASE_DIR, "static", "upload")
# Ensure the upload directory exists to avoid FileNotFoundError
os.makedirs(STATIC, exist_ok=True)


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


def _get_room_by_credentials(room_id, password):
    data = fs_data.get_data_by_credentials(room_id, password)
    if not data:
        return None, None
    record = data[0]
    return record.get("secure_id"), record


def _calculate_deletion_context(record):
    retention_days = record.get("retention_days", 7)
    created_at = record.get("time")
    deletion_date = None
    if created_at:
        try:
            deletion_date = (created_at + timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            deletion_date = None
    return retention_days, deletion_date


@router.get("/fs-qr_menu", name="fsqr.fs_qr")
async def fs_qr(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "fs-qr.html")


@router.get("/fs-qr", name="fsqr.fs_qr_upload")
async def fs_qr_upload(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "fs-qr-upload.html")


@router.post("/upload", name="fsqr.upload")
async def upload(
    request: Request,
    name: str = Form(""),
    file_type: str = Form("multiple"),
    original_filename: str = Form(""),
    retention_days: str = Form(""),
    upfile: Optional[List[UploadFile]] = File(None),
):
    uid = str(uuid.uuid4())[:10]
    id_val = name.strip()
    file_type = file_type or "multiple"
    original_filename = original_filename or ""

    retention_value = (retention_days or "").strip()
    try:
        retention_days_int = int(retention_value) if retention_value else 7
    except ValueError:
        retention_days_int = 7

    if retention_days_int not in (1, 7, 30):
        retention_days_int = 7

    if not id_val:
        import string

        chars = string.ascii_letters + string.digits
        id_val = "".join(secrets.choice(chars) for _ in range(6))

    if id_val:
        if not re.match(r"^[a-zA-Z0-9]+$", id_val):
            return json_or_msg(request, "IDに無効な文字が含まれています。半角英数字のみ使用してください。")
        if len(id_val) != 6:
            return json_or_msg(request, "IDは6文字の半角英数字で入力してください。")

    password = str(secrets.randbelow(10**6)).zfill(6)

    secure_id_base = f"{id_val}-{uid}-"

    if not upfile:
        return json_or_msg(request, "アップロード失敗")

    if len(upfile) > 10:
        return json_or_msg(request, "ファイル数は最大10個までです")

    total_size = 0
    max_total_size = 50 * 1024 * 1024

    for file in upfile:
        if file.filename:
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)
            total_size += file_size

    if total_size > max_total_size:
        return json_or_msg(request, "ファイルの合計サイズは50MBまでです")

    uploaded_files = []

    for file in upfile:
        filename = secure_filename(file.filename or "")
        if not filename:
            return json_or_msg(request, "不正なファイル名です")

        save_path = os.path.join(STATIC, secure_id_base + filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_files.append(filename)

    if file_type == "single":
        secure_id = (secure_id_base + uploaded_files[-1]).replace(".enc", "")
    else:
        secure_id = (secure_id_base + uploaded_files[-1]).replace(".zip", "")

    fs_data.save_file(
        uid=uid,
        id=id_val,
        password=password,
        secure_id=secure_id,
        file_type=file_type,
        original_filename=original_filename,
        retention_days=retention_days_int,
    )

    return JSONResponse({"redirect_url": build_url(request, "fsqr.upload_complete", secure_id=secure_id)})


@router.get("/upload_complete/{secure_id}", name="fsqr.upload_complete")
async def upload_complete(request: Request, secure_id: str):
    data = fs_data.get_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)

    row = data[0]
    id_val = row["id"]
    password_val = row["password"]

    share_url = build_url(
        request,
        "fsqr.fs_qr_room",
        room_id=id_val,
        password=password_val,
        _external=True,
    )
    retention_days, deletion_date = _calculate_deletion_context(row)

    return render_template(
        request,
        "info.html",
        id=id_val,
        password=password_val,
        secure_id=secure_id,
        mode="upload",
        url=share_url,
        retention_days=retention_days,
        deletion_date=deletion_date,
    )


@router.get("/download/{secure_id}", name="fsqr.download")
async def download(request: Request, secure_id: str):
    data = fs_data.get_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)
    row = data[0]
    return RedirectResponse(
        build_url(request, "fsqr.fs_qr_room", room_id=row["id"], password=row["password"]),
        status_code=302,
    )


@router.get("/fs-qr/{room_id}/{password}", name="fsqr.fs_qr_room")
async def fs_qr_room(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = check_rate_limit(SCOPE_QR, ip)
    if not allowed:
        return msg(request, get_block_message(block_label), 429)

    secure_id, record = _get_room_by_credentials(room_id, password)
    if not secure_id:
        _, block_label = register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDかパスワードが間違っています", 404)

    register_success(SCOPE_QR, ip)

    retention_days, deletion_date = _calculate_deletion_context(record)

    return render_template(
        request,
        "info.html",
        mode="download",
        id=record["id"],
        password=record["password"],
        secure_id=secure_id,
        url=build_url(request, "fsqr.fs_qr_download", room_id=room_id, password=password),
        retention_days=retention_days,
        deletion_date=deletion_date,
    )


@router.post("/download_go/{secure_id}", name="fsqr.download_go")
async def download_go(request: Request, secure_id: str):
    return _send_file_response(request, secure_id)


@router.post("/fs-qr/{room_id}/{password}/download", name="fsqr.fs_qr_download")
async def fs_qr_download(request: Request, room_id: str, password: str):
    secure_id, _ = _get_room_by_credentials(room_id, password)
    if not secure_id:
        return msg(request, "IDかパスワードが間違っています")
    return _send_file_response(request, secure_id)


def _send_file_response(request: Request, secure_id: str):
    data = fs_data.get_data(secure_id)
    if not data:
        return msg(request, "パラメータが不正です")

    file_type = data[0].get("file_type", "multiple")
    original_filename = data[0].get("original_filename", "")

    if file_type == "single":
        path = os.path.join(STATIC, secure_id + ".enc")
        download_name = original_filename if original_filename else secure_id + ".enc"
        mimetype = "application/octet-stream"
    else:
        path = os.path.join(STATIC, secure_id + ".zip")
        download_name = secure_id + ".zip"
        mimetype = "application/zip"

    if not os.path.exists(path):
        return msg(request, "ファイルが存在しません")

    response = FileResponse(path, media_type=mimetype)
    response.headers["Content-Disposition"] = f"inline; filename=\"{download_name}\""
    response.headers["X-File-Type"] = file_type
    if original_filename:
        response.headers["X-Original-Filename"] = original_filename
    return response


@router.get("/search_fs-qr", name="fsqr.search_fs_qr")
async def search_fs_qr(request: Request):
    return render_template(request, "kensaku-form.html")


@router.post("/try_login", name="fsqr.kekka")
async def kekka(request: Request):
    form = await request.form()
    id_val = (form.get("name") or "").strip()
    password = (form.get("pw") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = check_rate_limit(SCOPE_QR, ip)
    if not allowed:
        return msg(request, get_block_message(block_label), 429)

    if not re.match(r"^[a-zA-Z0-9]+$", id_val) or not re.match(r"^[0-9]+$", password):
        _, block_label = register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDまたはパスワードに不正な文字が含まれています。")

    secure_id = fs_data.try_login(id_val, password)

    if not secure_id:
        _, block_label = register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDかパスワードが間違っています")

    register_success(SCOPE_QR, ip)

    return RedirectResponse(
        build_url(request, "fsqr.fs_qr_room", room_id=id_val, password=password),
        status_code=302,
    )


@router.get("/remove-succes", name="fsqr.after_remove")
async def after_remove(request: Request):
    return render_template(request, "after-remove.html")


def msg(request: Request, message: str, status_code: int = 200):
    response = render_template(request, "error.html", message=message)
    response.status_code = status_code
    return response


def json_or_msg(request: Request, message: str, status_code: int = 400):
    content_type = request.headers.get("content-type", "")
    if (
        content_type == "application/x-www-form-urlencoded"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        return JSONResponse({"error": message}, status_code=status_code)
    if "multipart/form-data" in content_type:
        return JSONResponse({"error": message}, status_code=status_code)

    return msg(request, message, status_code=status_code)
