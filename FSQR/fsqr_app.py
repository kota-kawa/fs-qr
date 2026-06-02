import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
import shutil
import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from starlette.responses import RedirectResponse, Response

from api_response import api_error_response, api_ok_response
from file_validation import (
    build_content_disposition_attachment,
    normalize_upload_filename,
    sanitize_download_filename,
    validate_upload_limits,
)
from i18n import is_language_query_only
from models import FsqrUploadInput
from rate_limit import (
    SCOPE_QR,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from room_credentials import generate_room_password, validate_room_credentials
from settings import (
    FSQR_UPLOAD_DIR,
    UPLOAD_MAX_FILES,
    UPLOAD_MAX_TOTAL_SIZE_BYTES,
    UPLOAD_MAX_TOTAL_SIZE_MB,
)
from share_links import (
    ServiceKey,
    build_share_url,
    create_share_link,
    encrypt_share_password,
    resolve_share_link,
    share_link_password,
)
from web import build_url, enforce_csrf, render_template, wants_json_response
import room_access
from . import fsqr_data as fs_data

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC = FSQR_UPLOAD_DIR
# Ensure the upload directory exists to avoid FileNotFoundError
os.makedirs(STATIC, exist_ok=True)
FSQR_UPLOAD_ACCESS_SESSION_KEY = "fsqr_upload_access"
FSQR_UPLOAD_FILE_TYPES = frozenset({"single", "multiple"})
SHARE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


def _canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def _get_room_by_credentials(room_id, password):
    data = await fs_data.get_data_by_credentials(room_id, password)
    if not data:
        return None, None
    record = data[0]
    if await _remove_if_expired(record):
        return None, None
    return record.get("secure_id"), record


def _remember_fsqr_access(
    request: Request,
    secure_id: str,
    id_val: str,
    password: str,
    share_token: str = "",
    can_delete: bool = False,
) -> None:
    payload = {"id": id_val, "password": password, "share_token": share_token}
    if can_delete:
        payload["can_delete"] = "1"
    room_access.grant_access(
        request.session,
        FSQR_UPLOAD_ACCESS_SESSION_KEY,
        secure_id,
        payload=payload,
    )


def _get_fsqr_access(request: Request, secure_id: str):
    entry = room_access.get_access(
        request.session, FSQR_UPLOAD_ACCESS_SESSION_KEY, secure_id
    )
    if not entry:
        return None
    id_val = entry.get("id")
    if not isinstance(id_val, str):
        return None
    share_token = entry.get("share_token", "")
    if not isinstance(share_token, str):
        share_token = ""
    password = entry.get("password", "")
    if not isinstance(password, str):
        password = ""
    can_delete = entry.get("can_delete", "") == "1"
    return {
        "id": id_val,
        "password": password,
        "share_token": share_token,
        "can_delete": can_delete,
    }


def _can_delete_fsqr_upload(request: Request, secure_id: str, record: dict) -> bool:
    access = _get_fsqr_access(request, secure_id)
    return bool(
        access and access.get("can_delete") and access.get("id") == record.get("id")
    )


def _forget_fsqr_access(request: Request, secure_id: str) -> None:
    room_access.revoke_access(
        request.session, FSQR_UPLOAD_ACCESS_SESSION_KEY, secure_id
    )


def _is_valid_share_token(share_token: str) -> bool:
    return bool(SHARE_TOKEN_RE.match(share_token or ""))


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


def _is_record_expired(record, now=None) -> bool:
    created_at = record.get("time")
    if not created_at:
        return False
    try:
        retention_days = int(record.get("retention_days", 7))
        current_time = now or datetime.now(tz=created_at.tzinfo)
        return created_at + timedelta(days=retention_days) <= current_time
    except Exception:
        return False


async def _remove_if_expired(record) -> bool:
    if not _is_record_expired(record):
        return False
    secure_id = record.get("secure_id")
    if secure_id:
        await fs_data.remove_data(secure_id)
        logger.info(
            "Expired FSQR record removed during access: secure_id=%s", secure_id
        )
    return True


async def _get_active_data(secure_id):
    data = await fs_data.get_data(secure_id)
    if not data:
        return None
    record = data[0]
    if await _remove_if_expired(record):
        return None
    return data


def _strip_upload_suffix(filename: str, suffix: str) -> str:
    if filename.lower().endswith(suffix):
        return filename[: -len(suffix)]
    return filename


def _validate_fsqr_encrypted_payload(
    file_type: str, files: List[UploadFile]
) -> str | None:
    if file_type not in FSQR_UPLOAD_FILE_TYPES:
        return "アップロード形式が不正です。"

    if len(files) != 1:
        return "アップロードデータが不正です。ファイルを選び直してください。"

    filename = normalize_upload_filename(files[0].filename or "")
    if not filename:
        return "不正なファイル名です"

    normalized = filename.lower()
    if file_type == "single" and not normalized.endswith(".enc"):
        return "暗号化済みファイルを送信できませんでした。画面を再読み込みして再度お試しください。"
    if file_type == "multiple" and not normalized.endswith(".zip"):
        return "圧縮済みファイルを送信できませんでした。画面を再読み込みして再度お試しください。"

    return None


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
async def upload(  # noqa: C901
    request: Request,
    name: str = Form(""),
    download_password: str = Form(""),
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

    download_password = (download_password or "").strip()
    if download_password:
        try:
            _, download_password = validate_room_credentials(id_val, download_password)
        except ValueError:
            return json_or_msg(
                request,
                "アップロード用パスワードの生成に失敗しました。画面を再読み込みして再度お試しください。",
            )
        password = download_password
    else:
        password = generate_room_password()
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

    payload_error = _validate_fsqr_encrypted_payload(file_type, upfile)
    if payload_error:
        return json_or_msg(request, payload_error)

    file = upfile[0]
    filename = normalize_upload_filename(file.filename or "")
    if not filename:
        return json_or_msg(request, "不正なファイル名です")

    if file_type == "single":
        secure_id = secure_id_base + _strip_upload_suffix(filename, ".enc")
        final_path = os.path.join(STATIC, secure_id + ".enc")
    else:
        secure_id = secure_id_base + _strip_upload_suffix(filename, ".zip")
        final_path = os.path.join(STATIC, secure_id + ".zip")

    temp_path = os.path.join(STATIC, f".{secure_id}.{secrets.token_hex(8)}.uploading")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    metadata_saved = False
    share_token = ""
    try:
        await fs_data.save_file(
            uid=uid,
            id=id_val,
            password=password,
            secure_id=secure_id,
            file_type=file_type,
            original_filename=original_filename,
            retention_days=retention_days_int,
        )
        metadata_saved = True
        share_token = await create_share_link(
            service_key=ServiceKey.FSQR,
            resource_id=secure_id,
            expires_at=datetime.now() + timedelta(days=retention_days_int),
            metadata={"id": id_val, "password_enc": encrypt_share_password(password)},
        )
        os.replace(temp_path, final_path)
    except Exception:
        if metadata_saved:
            logger.exception("FSQR upload activation failed: secure_id=%s", secure_id)
            try:
                await fs_data.remove_data(secure_id)
            except Exception:
                logger.exception(
                    "FSQR upload metadata rollback failed: secure_id=%s", secure_id
                )
        else:
            logger.exception(
                "FSQR upload metadata save failed: secure_id=%s", secure_id
            )
        for orphan_path in (temp_path, final_path):
            try:
                if os.path.exists(orphan_path):
                    os.remove(orphan_path)
            except OSError:
                logger.warning("Failed to remove orphaned upload: %s", orphan_path)
        return json_or_msg(
            request,
            "アップロード情報の保存に失敗しました。時間をおいて再度お試しください。",
            status_code=500,
        )
    _remember_fsqr_access(
        request, secure_id, id_val, password, share_token, can_delete=True
    )

    return api_ok_response(
        {
            "redirect_url": build_url(
                request, "fsqr.upload_complete", secure_id=secure_id
            )
        }
    )


@router.get("/upload_complete/{secure_id}", name="fsqr.upload_complete")
async def upload_complete(request: Request, secure_id: str):
    data = await _get_active_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)

    row = data[0]
    access = _get_fsqr_access(request, secure_id)
    id_val = row["id"]
    password_val = ""
    share_url = ""
    if access and access["id"] == id_val:
        password_val = access.get("password", "")
        share_token = access.get("share_token", "")
        if share_token:
            share_url = build_share_url(
                request, service_key=ServiceKey.FSQR, token=share_token
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
        can_delete=_can_delete_fsqr_upload(request, secure_id, row),
    )


@router.get("/download/{secure_id}", name="fsqr.download")
async def download(request: Request, secure_id: str):
    data = await _get_active_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)
    row = data[0]
    access = _get_fsqr_access(request, secure_id)
    if access and access["id"] == row["id"]:
        share_token = access.get("share_token", "")
        if share_token:
            return RedirectResponse(
                build_url(request, "fsqr.share_entry", token=share_token),
                status_code=302,
            )
        retention_days, deletion_date = _calculate_deletion_context(row)
        return render_template(
            request,
            "info.html",
            mode="download",
            id=row["id"],
            password=access.get("password", ""),
            secure_id=secure_id,
            file_type=row.get("file_type", "multiple"),
            original_filename=row.get("original_filename", ""),
            url=build_url(request, "fsqr.download_go", secure_id=secure_id),
            retention_days=retention_days,
            deletion_date=deletion_date,
            can_delete=_can_delete_fsqr_upload(request, secure_id, row),
        )
    raise HTTPException(status_code=404)


@router.get("/fs-qr/s/{token}", name="fsqr.share_entry")
async def fs_qr_share(request: Request, token: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_QR, ip)
    if not allowed:
        return msg(request, get_block_message(block_label), 429)

    if not _is_valid_share_token(token):
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        raise HTTPException(status_code=404)

    link = await resolve_share_link(token, service_key=ServiceKey.FSQR)
    if not link:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        raise HTTPException(status_code=404)
    data = await fs_data.get_data(link["resource_id"])
    if not data:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        raise HTTPException(status_code=404)
    if await _remove_if_expired(data[0]):
        raise HTTPException(status_code=404)

    await register_success(SCOPE_QR, ip)
    record = data[0]
    retention_days, deletion_date = _calculate_deletion_context(record)
    link_password = share_link_password(link)

    return render_template(
        request,
        "info.html",
        mode="download",
        id=record["id"],
        password=link_password,
        secure_id=record["secure_id"],
        file_type=record.get("file_type", "multiple"),
        original_filename=record.get("original_filename", ""),
        url=build_url(request, "fsqr.share_download", token=token),
        retention_days=retention_days,
        deletion_date=deletion_date,
        can_delete=_can_delete_fsqr_upload(request, record["secure_id"], record),
    )


@router.post("/fs-qr/delete/{secure_id}", name="fsqr.delete_upload")
async def delete_upload(request: Request, secure_id: str):
    await enforce_csrf(request)
    data = await _get_active_data(secure_id)
    if not data:
        raise HTTPException(status_code=404)

    if not _can_delete_fsqr_upload(request, secure_id, data[0]):
        if wants_json_response(request):
            return api_error_response("削除権限がありません。", status_code=403)
        return msg(request, "削除権限がありません。", status_code=403)

    await fs_data.remove_data(secure_id)
    _forget_fsqr_access(request, secure_id)
    if wants_json_response(request):
        return api_ok_response(
            {"redirect_url": build_url(request, "fsqr.after_remove")}
        )
    return RedirectResponse(build_url(request, "fsqr.after_remove"), status_code=302)


@router.get("/fs-qr/{room_id}/{password}", name="fsqr.legacy_room")
async def fs_qr_room(request: Request, room_id: str, password: str):
    return msg(
        request,
        "旧形式のFSQR URLは停止しました。新しい共有URLからアクセスしてください。",
        410,
    )


@router.post("/download_go/{secure_id}", name="fsqr.download_go")
async def download_go(request: Request, secure_id: str):
    await enforce_csrf(request)
    if not _get_fsqr_access(request, secure_id):
        raise HTTPException(status_code=404)
    return await _send_file_response(request, secure_id)


@router.post("/fs-qr/s/{token}/download", name="fsqr.share_download")
async def fs_qr_share_download(request: Request, token: str):
    await enforce_csrf(request)
    if not _is_valid_share_token(token):
        raise HTTPException(status_code=404)
    link = await resolve_share_link(token, service_key=ServiceKey.FSQR)
    if not link:
        raise HTTPException(status_code=404)
    data = await fs_data.get_data(link["resource_id"])
    if not data:
        raise HTTPException(status_code=404)
    if await _remove_if_expired(data[0]):
        raise HTTPException(status_code=404)
    return await _send_file_response(request, data[0]["secure_id"])


@router.post("/fs-qr/{room_id}/{password}/download", name="fsqr.legacy_download")
async def fs_qr_download(request: Request, room_id: str, password: str):
    await enforce_csrf(request)
    return msg(
        request,
        "旧形式のFSQRダウンロードは停止しました。新しい共有URLを使用してください。",
        410,
    )


async def _send_file_response(request: Request, secure_id: str):
    data = await _get_active_data(secure_id)
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

    headers = {
        "Content-Disposition": build_content_disposition_attachment(download_name),
        "Content-Length": str(os.path.getsize(path)),
        "X-File-Type": file_type,
    }
    safe_original_filename = sanitize_download_filename(original_filename, default="")
    if safe_original_filename:
        headers["X-Original-Filename"] = safe_original_filename
    with open(path, "rb") as file:
        return Response(content=file.read(), media_type=mimetype, headers=headers)


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
        id_val, password = validate_room_credentials(id_val, password)
    except ValueError as exc:
        return msg(request, str(exc), 400)

    secure_id, record = await _get_room_by_credentials(id_val, password)
    if not secure_id or not record:
        _, block_label = await register_failure(SCOPE_QR, ip)
        if block_label:
            return msg(request, get_block_message(block_label), 429)
        return msg(request, "IDまたはパスワードが違います。", 404)

    await register_success(SCOPE_QR, ip)
    _remember_fsqr_access(request, secure_id, id_val, password)
    return RedirectResponse(
        build_url(request, "fsqr.download", secure_id=secure_id),
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
