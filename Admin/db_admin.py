import os
import tempfile
import zipfile

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from starlette.background import BackgroundTask
from starlette.responses import (
    FileResponse,
    RedirectResponse,
)
from werkzeug.utils import secure_filename

from api_response import api_error_response, api_ok_response
from database import db_session
from file_validation import build_content_disposition_attachment
from FSQR import fsqr_data as fs_data
from Group import group_data
from Group.group_storage import collect_room_files, existing_room_folders, room_folder
from session_auth import (
    clear_session_authenticated,
    is_session_authenticated,
    mark_session_authenticated,
    secure_compare_secret,
)
from rate_limit import (
    SCOPE_DB_ADMIN,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, enforce_csrf, flash_message, render_template
from settings import (
    DB_ADMIN_PASSWORD,
    FSQR_UPLOAD_DIR,
    GROUP_UPLOAD_DIR as SETTINGS_GROUP_UPLOAD_DIR,
)

fs_db = db_session
grp_db = db_session

ADMIN_DB_PW = DB_ADMIN_PASSWORD
DB_ADMIN_SESSION_KEY = "db_admin_authenticated"

UPLOAD_DIR = FSQR_UPLOAD_DIR
GROUP_UPLOAD_DIR = SETTINGS_GROUP_UPLOAD_DIR

router = APIRouter(prefix="/admin")


def _remove_temp_file(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


COUNT_QUERIES = {
    "fsqr": text("SELECT COUNT(*) FROM fsqr"),
    "room": text("SELECT COUNT(*) FROM room"),
    "note_room": text("SELECT COUNT(*) FROM note_room"),
    "note_content": text("SELECT COUNT(*) FROM note_content"),
}

RECENT_QUERIES = {
    ("fsqr", "time"): text("SELECT * FROM fsqr ORDER BY time DESC LIMIT :limit"),
    ("room", "time"): text("SELECT * FROM room ORDER BY time DESC LIMIT :limit"),
    ("note_room", "time"): text(
        "SELECT * FROM note_room ORDER BY time DESC LIMIT :limit"
    ),
    ("note_content", "updated_at"): text(
        "SELECT * FROM note_content ORDER BY updated_at DESC LIMIT :limit"
    ),
}


def _validate_recent_limit(limit):
    if not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be greater than 0")
    return limit


async def table_exists(sess, table_name):
    q = """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = :t
    """
    result = await sess.execute(text(q), {"t": table_name})
    exists = bool(result.scalar())
    try:
        await sess.rollback()
    except Exception:  # noqa: S110
        pass
    return exists


async def safe_count(sess, table):
    query = COUNT_QUERIES.get(table)
    if query is None:
        return 0
    if not await table_exists(sess, table):
        return 0
    result = await sess.execute(query)
    count = result.scalar()
    try:
        await sess.rollback()
    except Exception:  # noqa: S110
        pass
    return count


async def safe_recent(sess, table, time_col, limit=10):
    query = RECENT_QUERIES.get((table, time_col))
    if query is None:
        return None
    if not await table_exists(sess, table):
        return None
    result = await sess.execute(query, {"limit": _validate_recent_limit(limit)})
    rows = result.mappings().all()
    try:
        await sess.rollback()
    except Exception:  # noqa: S110
        pass
    return rows


async def _get_record(secure_id):
    # DB管理画面ではハッシュ済み password 列を含む生のレコードが必要なので、
    # password を strip するキャッシュ層を経由せず DB を直接参照する。
    data = await fs_data.get_data_direct(secure_id)
    if not data:
        return None
    return data[0]


def _resolve_file_path(record):
    secure_id = record.get("secure_id")
    file_type = record.get("file_type", "multiple")

    if file_type == "single":
        filename = f"{secure_id}.enc"
        display_name = record.get("original_filename") or filename
        mimetype = "application/octet-stream"
    else:
        filename = f"{secure_id}.zip"
        display_name = filename
        mimetype = "application/zip"

    path = os.path.join(UPLOAD_DIR, filename)
    return path, filename, display_name, mimetype


async def _get_room_record(room_id):
    # password 列を含む生のレコードが必要なため、キャッシュ層をバイパスする。
    data = await group_data.get_data_direct(room_id)
    if not data:
        return None
    return data[0]


def _get_room_folder(room_id):
    if not room_id:
        return None
    folders = existing_room_folders(room_id, primary_root=GROUP_UPLOAD_DIR)
    if folders:
        return folders[0][1]
    return room_folder(room_id, root=GROUP_UPLOAD_DIR)


def _collect_room_files(room_id):
    files = []
    try:
        for name, file_path in collect_room_files(
            room_id, primary_root=GROUP_UPLOAD_DIR
        ).items():
            files.append(
                {
                    "stored_name": name,
                    "display_name": name,
                    "size": os.path.getsize(file_path),
                    "_path": file_path,
                }
            )
    except OSError:
        return []

    files.sort(key=lambda item: item["display_name"].lower())
    return files


def _is_db_admin_authenticated(request: Request) -> bool:
    return is_session_authenticated(request.session, DB_ADMIN_SESSION_KEY)


@router.get("/", name="db_admin.dashboard")
@router.post("/", name="db_admin.dashboard_post")
async def dashboard(request: Request):
    if "pw" in request.query_params:
        return RedirectResponse(
            build_url(request, "db_admin.dashboard"), status_code=302
        )

    if request.method == "POST":
        await enforce_csrf(request)
        form = await request.form()
        pw = (form.get("password", "") or "").strip()
        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_DB_ADMIN, ip)
        if not allowed:
            flash_message(request, get_block_message(block_label))
            response = render_template(request, "db_admin.html", authenticated=False)
            response.status_code = 429
            return response

        if not secure_compare_secret(pw, ADMIN_DB_PW):
            _, block_label = await register_failure(SCOPE_DB_ADMIN, ip)
            if block_label:
                flash_message(request, get_block_message(block_label))
                response = render_template(
                    request, "db_admin.html", authenticated=False
                )
                response.status_code = 429
                return response
            flash_message(request, "パスワードが違います")
            return render_template(request, "db_admin.html", authenticated=False)
        await register_success(SCOPE_DB_ADMIN, ip)
        mark_session_authenticated(request.session, DB_ADMIN_SESSION_KEY)
        return RedirectResponse(
            build_url(request, "db_admin.dashboard"), status_code=302
        )

    if not _is_db_admin_authenticated(request):
        return render_template(request, "db_admin.html", authenticated=False)

    summary = [
        {"name": "fsqr", "count": await safe_count(fs_db, "fsqr")},
        {"name": "room", "count": await safe_count(grp_db, "room")},
        {"name": "note_room", "count": await safe_count(grp_db, "note_room")},
        {"name": "note_content", "count": await safe_count(grp_db, "note_content")},
    ]

    recent_rows = {
        "fsqr": await safe_recent(fs_db, "fsqr", "time"),
        "room": await safe_recent(grp_db, "room", "time"),
        "note_room": await safe_recent(grp_db, "note_room", "time"),
        "note_content": await safe_recent(grp_db, "note_content", "updated_at"),
    }

    return render_template(
        request,
        "db_admin.html",
        authenticated=True,
        summary=summary,
        recent=recent_rows,
    )


@router.get("/file/{secure_id}", name="db_admin.file_detail")
async def file_detail(request: Request, secure_id: str):
    if not _is_db_admin_authenticated(request):
        return api_error_response("forbidden", status_code=403)

    record = await _get_record(secure_id)
    if not record:
        return api_error_response("not_found", status_code=404)

    path, stored_name, display_name, _ = _resolve_file_path(record)
    files = []
    if os.path.exists(path):
        files.append(
            {
                "stored_name": stored_name,
                "display_name": display_name,
                "size": os.path.getsize(path),
            }
        )

    created_at = record.get("time")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat(sep=" ")

    return api_ok_response(
        {
            "secure_id": record.get("secure_id"),
            "id": record.get("id"),
            "password": record.get("password"),
            "file_type": record.get("file_type", "multiple"),
            "original_filename": record.get("original_filename"),
            "created_at": created_at,
            "files": files,
        }
    )


@router.get("/file/{secure_id}/download", name="db_admin.file_download")
async def file_download(request: Request, secure_id: str):
    if not _is_db_admin_authenticated(request):
        raise HTTPException(status_code=403)

    record = await _get_record(secure_id)
    if not record:
        raise HTTPException(status_code=404)

    path, _, display_name, mimetype = _resolve_file_path(record)

    if not os.path.exists(path):
        raise HTTPException(status_code=404)

    response = FileResponse(path, media_type=mimetype)
    response.headers["Content-Disposition"] = build_content_disposition_attachment(
        display_name
    )
    return response


@router.get("/room/{room_id}", name="db_admin.room_detail")
async def room_detail(request: Request, room_id: str):
    if not _is_db_admin_authenticated(request):
        return api_error_response("forbidden", status_code=403)

    record = await _get_room_record(room_id)
    if not record:
        return api_error_response("not_found", status_code=404)

    created_at = record.get("time")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat(sep=" ")

    files = [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in _collect_room_files(record.get("room_id"))
    ]

    return api_ok_response(
        {
            "room_id": record.get("room_id"),
            "id": record.get("id"),
            "password": record.get("password"),
            "retention_days": record.get("retention_days"),
            "created_at": created_at,
            "files": files,
        }
    )


@router.get("/room/{room_id}/download", name="db_admin.room_download")
async def room_download(request: Request, room_id: str):
    if not _is_db_admin_authenticated(request):
        raise HTTPException(status_code=403)

    record = await _get_room_record(room_id)
    if not record:
        raise HTTPException(status_code=404)

    folder = _get_room_folder(record.get("room_id"))
    if not folder or not os.path.isdir(folder):
        raise HTTPException(status_code=404)

    file_entries = _collect_room_files(record.get("room_id"))
    if not file_entries:
        raise HTTPException(status_code=404)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as archive:
            archive_path = archive.name
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for entry in file_entries:
                file_path = entry.get("_path") or os.path.join(
                    folder, entry["stored_name"]
                )
                zipf.write(file_path, arcname=entry["display_name"])
    except Exception:
        if "archive_path" in locals():
            _remove_temp_file(archive_path)
        raise

    download_name = (
        secure_filename(f"{record.get('room_id')}_files.zip") or "room_files.zip"
    )
    headers = {
        "Content-Disposition": build_content_disposition_attachment(download_name)
    }
    return FileResponse(
        archive_path,
        media_type="application/zip",
        headers=headers,
        background=BackgroundTask(_remove_temp_file, archive_path),
    )


@router.get("/db/logout", name="db_admin.logout")
async def db_admin_logout(request: Request):
    clear_session_authenticated(request.session, DB_ADMIN_SESSION_KEY)
    return RedirectResponse(build_url(request, "db_admin.dashboard"), status_code=302)
