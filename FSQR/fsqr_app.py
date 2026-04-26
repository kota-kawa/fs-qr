import os
import secrets
import uuid
from datetime import timedelta
import shutil
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from starlette.responses import FileResponse, RedirectResponse

from api_response import api_error_response, api_ok_response
from file_validation import (
    build_content_disposition_attachment,
    normalize_upload_filename,
    sanitize_download_filename,
    validate_upload_file_content,
    validate_upload_limits,
)
from models import FsqrUploadInput, RoomSearchInput
from rate_limit import (
    SCOPE_QR,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from settings import (
    UPLOAD_MAX_FILES,
    UPLOAD_MAX_TOTAL_SIZE_BYTES,
    UPLOAD_MAX_TOTAL_SIZE_MB,
)
from web import build_url, enforce_csrf, render_template
from password_security import is_password_hashed
from . import fsqr_data as fs_data

router = APIRouter()

# Base configuration (same as in app.py)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC = os.path.join(BASE_DIR, "static", "upload")
# Ensure the upload directory exists to avoid FileNotFoundError
os.makedirs(STATIC, exist_ok=True)
FSQR_UPLOAD_ACCESS_SESSION_KEY = "fsqr_upload_access"


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def _get_room_by_credentials(room_id, password):
    data = await fs_data.get_data_by_credentials(room_id, password)
    if not data:
        return None, None
    record = data[0]
    return record.get("secure_id"), record


def _remember_fsqr_access(
    request: Request, secure_id: str, id_val: str, password: str
) -> None:
    payload = request.session.get(FSQR_UPLOAD_ACCESS_SESSION_KEY)
    if not isinstance(payload, dict):
        payload = {}
    payload[str(secure_id)] = {"id": str(id_val), "password": str(password)}
    if len(payload) > 20:
        payload = dict(list(payload.items())[-20:])
    request.session[FSQR_UPLOAD_ACCESS_SESSION_KEY] = payload


def _get_fsqr_access(request: Request, secure_id: str):
    payload = request.session.get(FSQR_UPLOAD_ACCESS_SESSION_KEY)
    if not isinstance(payload, dict):
        return None
    entry = payload.get(str(secure_id))
    if not isinstance(entry, dict):
        return None
    id_val = entry.get("id")
    password = entry.get("password")
    if not isinstance(id_val, str) or not isinstance(password, str):
        return None
    return {"id": id_val, "password": password}


def _calculate_deletion_context(record):
    retention_days = record.get("retention_days", 7)
    created_at = record.get("time")
    deletion_date = None
    if created_at:
        try:
            deletion_date = (created_at + timedelta(days=retention_days)).strftime(
                "%Y-%m-%d %H:%M"
            )
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
    await enforce_csrf(request)
    uid = str(uuid.uuid4())[:10]
    file_type = file_type or "multiple"
    original_filename = original_filename or ""

    upload_in = FsqrUploadInput(name=name, retention_days=retention_days)
    retention_days_int = upload_in.retention_days
    id_val = upload_in.name

    if not id_val:
        import string

        chars = string.ascii_letters + string.digits
        id_val = "".join(secrets.choice(chars) for _ in range(6))
    else:
        try:
            upload_in.validate_manual_id()
        except ValueError as exc:
            return json_or_msg(request, str(exc))

    password = str(secrets.randbelow(10**6)).zfill(6)

    secure_id_base = f"{id_val}-{uid}-"

    if not upfile:
        return json_or_msg(request, "アップロード失敗")

    limits_error = validate_upload_limits(
        upfile,
        max_files=UPLOAD_MAX_FILES,
        max_total_size_bytes=UPLOAD_MAX_TOTAL_SIZE_BYTES,
        max_total_size_mb=UPLOAD_MAX_TOTAL_SIZE_MB,
        too_many_files_message=f"ファイル数は最大{UPLOAD_MAX_FILES}個までです",
        too_large_total_size_message=(
            f"ファイルの合計サイズは{UPLOAD_MAX_TOTAL_SIZE_MB}MBまでです"
        ),
    )
    if limits_error:
        return json_or_msg(request, limits_error)

    uploaded_files = []

    for file in upfile:
        filename = normalize_upload_filename(file.filename or "")
        if not filename:
            return json_or_msg(request, "不正なファイル名です")

        content_error = validate_upload_file_content(file)
        if content_error:
            return json_or_msg(request, content_error)

        save_path = os.path.join(STATIC, secure_id_base + filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_files.append(filename)

    if file_type == "single":
        secure_id = (secure_id_base + uploaded_files[-1]).replace(".enc", "")
    else:
        secure_id = (secure_id_base + uploaded_files[-1]).replace(".zip", "")

    await fs_data.save_file(
        uid=uid,
        id=id_val,
        password=password,
        secure_id=secure_id,
        file_type=file_type,
        original_filename=original_filename,
        retention_days=retention_days_int,
    )
    _remember_fsqr_access(request, secure_id, id_val, password)

    return api_ok_response(
        {
            "redirect_url": build_url(
                request, "fsqr.upload_complete", secure_id=secure_id
            )
        }
    )


@router.get("/upload_complete/{secure_id}", name="fsqr.upload_complete")
async def upload_complete(request: Request, secure_id: str):
    data = await fs_data.get_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)

    row = data[0]
    access = _get_fsqr_access(request, secure_id)
    id_val = row["id"]
    password_val = ""
    if access and access["id"] == id_val:
        password_val = access["password"]
    elif isinstance(row.get("password"), str) and not is_password_hashed(
        row["password"]
    ):
        password_val = row["password"]

    share_url = ""
    if password_val:
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
        file_type=row.get("file_type", "multiple"),
        original_filename=row.get("original_filename", ""),
        mode="upload",
        url=share_url,
        retention_days=retention_days,
        deletion_date=deletion_date,
    )


@router.get("/download/{secure_id}", name="fsqr.download")
async def download(request: Request, secure_id: str):
    data = await fs_data.get_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)
    row = data[0]
    access = _get_fsqr_access(request, secure_id)
    password = None
    if access and access["id"] == row["id"]:
        password = access["password"]
    elif isinstance(row.get("password"), str) and not is_password_hashed(
        row["password"]
    ):
        password = row["password"]
    if not password:
        raise HTTPException(status_code=404)
    return RedirectResponse(
        build_url(request, "fsqr.fs_qr_room", room_id=row["id"], password=password),
        status_code=302,
    )


@router.get("/fs-qr/{room_id}/{password}", name="fsqr.fs_qr_room")
async def fs_qr_room(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_QR, ip)
    if not allowed:
        return msg(request, get_block_message(block_label), 429)

    secure_id, record = await _get_room_by_credentials(room_id, password)
    if not secure_id:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDかパスワードが間違っています", 404)

    await register_success(SCOPE_QR, ip)

    retention_days, deletion_date = _calculate_deletion_context(record)

    return render_template(
        request,
        "info.html",
        mode="download",
        id=record["id"],
        password=password,
        secure_id=secure_id,
        file_type=record.get("file_type", "multiple"),
        original_filename=record.get("original_filename", ""),
        url=build_url(
            request, "fsqr.fs_qr_download", room_id=room_id, password=password
        ),
        retention_days=retention_days,
        deletion_date=deletion_date,
    )


@router.post("/download_go/{secure_id}", name="fsqr.download_go")
async def download_go(request: Request, secure_id: str):
    await enforce_csrf(request)
    return await _send_file_response(request, secure_id)


@router.post("/fs-qr/{room_id}/{password}/download", name="fsqr.fs_qr_download")
async def fs_qr_download(request: Request, room_id: str, password: str):
    await enforce_csrf(request)
    secure_id, _ = await _get_room_by_credentials(room_id, password)
    if not secure_id:
        return msg(request, "IDかパスワードが間違っています")
    return await _send_file_response(request, secure_id)


async def _send_file_response(request: Request, secure_id: str):
    data = await fs_data.get_data(secure_id)
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
    response.headers["Content-Disposition"] = build_content_disposition_attachment(
        download_name
    )
    response.headers["X-File-Type"] = file_type
    safe_original_filename = sanitize_download_filename(original_filename, default="")
    if safe_original_filename:
        response.headers["X-Original-Filename"] = safe_original_filename
    return response


@router.get("/search_fs-qr", name="fsqr.search_fs_qr")
async def search_fs_qr(request: Request):
    return render_template(request, "kensaku-form.html")


@router.post("/try_login", name="fsqr.kekka")
async def kekka(request: Request):
    await enforce_csrf(request)
    form = await request.form()
    id_val = (form.get("name") or "").strip()
    password = (form.get("pw") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_QR, ip)
    if not allowed:
        return msg(request, get_block_message(block_label), 429)

    try:
        inp = RoomSearchInput(room_id=id_val, password=password)
    except ValidationError:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDまたはパスワードに不正な文字が含まれています。")
    id_val, password = inp.room_id, inp.password

    secure_id = await fs_data.try_login(id_val, password)

    if not secure_id:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDかパスワードが間違っています")

    await register_success(SCOPE_QR, ip)

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
        return api_error_response(message, status_code=status_code)
    if "multipart/form-data" in content_type:
        return api_error_response(message, status_code=status_code)

    return msg(request, message, status_code=status_code)
