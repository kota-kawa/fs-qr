import io
import os
import random
import re
import shutil
import urllib
import zipfile
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, File, Request, UploadFile
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from werkzeug.utils import secure_filename

from rate_limit import (
    SCOPE_GROUP,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, flash_message, render_template
from . import group_data

router = APIRouter()

# .envファイルの読み込み
from settings import MANAGEMENT_PASSWORD as management_password

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(PARENT_DIR, "static")

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "group_uploads")


def is_safe_path(base_path, target_path):
    return os.path.commonprefix([os.path.abspath(target_path), os.path.abspath(base_path)]) == os.path.abspath(base_path)


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


@router.get("/group_menu", name="group.group")
async def group(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "group.html")


async def _get_room_if_valid(room_id, password):
    room_data = await group_data.get_data(room_id)
    if not room_data:
        return None
    record = room_data[0]
    if record.get("password") != password:
        return None
    return record


@router.get("/group", name="group.group_list")
async def group_list(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "group_room_access.html")


@router.get("/group/{room_id}/{password}", name="group.group_room")
async def group_room(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
    if not allowed:
        return room_msg(request, get_block_message(block_label), status_code=429)

    record = await _get_room_if_valid(room_id, password)
    if not record:
        _, block_label = await register_failure(SCOPE_GROUP, ip)
        if block_label:
            return room_msg(request, get_block_message(block_label), status_code=429)
        return room_msg(request, "指定されたルームが見つからないか、パスワードが違います", status_code=404)

    await register_success(SCOPE_GROUP, ip)

    user_id = record.get("id", "不明")
    retention_days = record.get("retention_days", 7)
    created_at = record.get("time")
    deletion_date = None
    if created_at:
        try:
            deletion_date = (created_at + timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            deletion_date = None

    return render_template(
        request,
        "group_room.html",
        room_id=room_id,
        user_id=user_id,
        password=password,
        retention_days=retention_days,
        deletion_date=deletion_date,
    )


@router.get("/create_room", name="group.create_room")
async def create_room(request: Request):
    return render_template(request, "create_group_room.html")


@router.post("/create_group_room", name="group.create_group_room")
async def create_group_room(request: Request):
    json_data = {}
    form_data = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            json_data = await request.json() or {}
        except Exception:
            json_data = {}
    else:
        form_data = await request.form()

    id_candidates = []
    if form_data and hasattr(form_data, "getlist"):
        id_candidates = form_data.getlist("id")
    if not id_candidates:
        id_candidates = [json_data.get("id", "")]
    id_val = next((str(v).strip() for v in id_candidates if str(v).strip()), "")
    id_mode = (form_data.get("idMode") if form_data else None) or json_data.get("idMode", "auto")

    retention_value = form_data.get("retention_days") if form_data else None
    if retention_value is None:
        retention_value = json_data.get("retention_days", 7)
    try:
        retention_days = int(retention_value)
    except (TypeError, ValueError):
        retention_days = 7

    if retention_days not in (1, 7, 30):
        retention_days = 7

    if not id_val:
        return JSONResponse({"error": "IDが指定されていません。"}, status_code=400)

    if not re.match(r"^[a-zA-Z0-9]+$", id_val):
        return JSONResponse({"error": "IDに無効な文字が含まれています。半角英数字のみ使用してください。"}, status_code=400)
    if len(id_val) != 6:
        return JSONResponse({"error": "IDは6文字の半角英数字で入力してください。"}, status_code=400)

    room_id = id_val
    existing_room = await group_data.get_data(room_id)

    if existing_room:
        if id_mode == "auto":
            return JSONResponse(
                {"error": "生成されたIDが重複しています。新しいIDで再試行してください。", "retry_auto": True},
                status_code=409,
            )
        return JSONResponse({"error": "このIDは既に使用されています。別のIDを使用してください。"}, status_code=409)

    password = str(random.randrange(10**5, 10**6))

    folder_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    os.makedirs(folder_path, exist_ok=True)

    await group_data.create_room(id=room_id, password=password, room_id=room_id, retention_days=retention_days)
    return RedirectResponse(
        build_url(request, "group.group_room", room_id=room_id, password=password), status_code=302
    )


@router.post("/group_upload/{room_id}/{password}", name="group.group_upload")
async def group_upload(
    request: Request,
    room_id: str,
    password: str,
    upfile: Optional[list[UploadFile]] = File(None),
):
    record = await _get_room_if_valid(room_id, password)
    if not record:
        return JSONResponse({"error": "ルームが見つからないか、パスワードが間違っています。"}, status_code=400)

    if not upfile:
        return JSONResponse({"error": "ファイルがアップロードされていません。"}, status_code=400)

    if len(upfile) > 10:
        return JSONResponse({"error": "ファイル数は最大10個までです。"}, status_code=400)

    total_size = 0
    max_total_size = 50 * 1024 * 1024

    for file in upfile:
        if file.filename:
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)
            total_size += file_size

    if total_size > max_total_size:
        return JSONResponse({"error": "ファイルの合計サイズは50MBまでです。"}, status_code=400)

    error_files = []
    save_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    os.makedirs(save_path, exist_ok=True)

    for file in upfile:
        if file.filename == "":
            continue

        safe_filename = file.filename

        if any(char in file.filename for char in ["..", "/", "\\", "\0"]):
            safe_filename = secure_filename(file.filename)

        if not safe_filename or safe_filename.startswith("."):
            import time

            _, ext = os.path.splitext(file.filename)
            safe_filename = f"file_{{int(time.time())}}{ext}"

        file_path = os.path.join(save_path, safe_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            if os.path.getsize(file_path) == 0:
                error_files.append(file.filename)
                os.remove(file_path)
        except Exception:
            error_files.append(file.filename)

    if error_files:
        return JSONResponse(
            {"status": "error", "message": "以下のファイルが保存できませんでした。", "files": error_files},
            status_code=500,
        )

    return JSONResponse({"status": "success", "message": "ファイルが正常にアップロードされました。"})


@router.get("/check/{room_id}/{password}", name="group.list_files")
async def list_files(request: Request, room_id: str, password: str):
    if not await _get_room_if_valid(room_id, password):
        return JSONResponse({"error": "ルームが見つからないか、パスワードが間違っています。"}, status_code=404)

    target_directory = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    if not os.path.exists(target_directory):
        return JSONResponse({"error": "ルームIDのディレクトリが見つかりません。"}, status_code=404)

    if not is_safe_path(UPLOAD_FOLDER, target_directory):
        return JSONResponse({"error": "不正なパスが検出されました。"}, status_code=400)

    try:
        files = [
            {"name": file_name}
            for file_name in os.listdir(target_directory)
            if os.path.isfile(os.path.join(target_directory, file_name))
        ]
        return JSONResponse(files)
    except Exception as e:
        return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


@router.get("/download/all/{room_id}/{password}", name="group.download_all_files")
async def download_all_files(request: Request, room_id: str, password: str):
    if not await _get_room_if_valid(room_id, password):
        return JSONResponse({"error": "ルームが見つからないか、パスワードが間違っています。"}, status_code=404)

    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    if not os.path.exists(room_folder):
        return JSONResponse({"error": "指定されたルームIDのファイルが見つかりません。"}, status_code=404)

    try:
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zipf:
            for filename in os.listdir(room_folder):
                file_path = os.path.join(room_folder, filename)
                if os.path.isfile(file_path) and is_safe_path(room_folder, file_path):
                    with open(file_path, "rb") as f:
                        zipf.writestr(filename, f.read())
        zip_stream.seek(0)
        headers = {"Content-Disposition": f"attachment; filename={room_id}_files.zip"}
        return StreamingResponse(zip_stream, media_type="application/zip", headers=headers)
    except Exception as e:
        return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


@router.get("/download/{room_id}/{password}/{filename:path}", name="group.download_file")
async def download_file(request: Request, room_id: str, password: str, filename: str):
    decoded_filename = urllib.parse.unquote(filename)

    if any(dangerous_pattern in decoded_filename for dangerous_pattern in ["..", "/", "\\", "\0"]):
        return JSONResponse({"error": "不正なファイル名が検出されました。"}, status_code=400)

    if not decoded_filename.strip():
        return JSONResponse({"error": "無効なファイル名です。"}, status_code=400)

    if not await _get_room_if_valid(room_id, password):
        return JSONResponse({"error": "ルームが見つからないか、パスワードが間違っています。"}, status_code=404)

    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    file_path = os.path.join(room_folder, decoded_filename)

    if not is_safe_path(room_folder, file_path):
        return JSONResponse({"error": "不正なパスが検出されました。"}, status_code=400)

    try:
        if os.path.exists(file_path):
            return FileResponse(file_path, filename=decoded_filename)
        return JSONResponse({"error": "ファイルが見つかりません。"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


@router.delete("/delete/{room_id}/{password}/{filename}", name="group.delete_file")
async def delete_file(request: Request, room_id: str, password: str, filename: str):
    decoded_filename = urllib.parse.unquote(filename)

    if any(dangerous_pattern in decoded_filename for dangerous_pattern in ["..", "/", "\\", "\0"]):
        return JSONResponse({"error": "不正なファイル名が検出されました。"}, status_code=400)

    if not decoded_filename.strip():
        return JSONResponse({"error": "無効なファイル名です。"}, status_code=400)

    if not await _get_room_if_valid(room_id, password):
        return JSONResponse({"error": "ルームが見つからないか、パスワードが間違っています。"}, status_code=404)

    room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
    file_path = os.path.join(room_folder, decoded_filename)

    if not is_safe_path(room_folder, file_path):
        return JSONResponse({"error": "不正なパスが検出されました。"}, status_code=400)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return JSONResponse({"message": "ファイルが削除されました。"}, status_code=200)
        return JSONResponse({"error": "ファイルが見つかりません。"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


@router.get("/search_group", name="group.search_room_page")
async def search_room_page(request: Request):
    return render_template(request, "search_room.html")


@router.post("/search_group_process", name="group.search_room")
async def search_room(request: Request):
    form = await request.form()
    id_val = (form.get("id") or "").strip()
    password = (form.get("password") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
    if not allowed:
        return _group_block_response(request, block_label)

    if not re.match(r"^[a-zA-Z0-9]+$", id_val) or not re.match(r"^[0-9]+$", password):
        _, block_label = await register_failure(SCOPE_GROUP, ip)
        if block_label:
            return _group_block_response(request, block_label)
        return JSONResponse({"error": "IDまたはパスワードに不正な値が含まれています。"}, status_code=400)

    room_id = await group_data.pich_room_id(id_val, password)
    if not room_id:
        _, block_label = await register_failure(SCOPE_GROUP, ip)
        if block_label:
            return _group_block_response(request, block_label)
        return room_msg(request, "IDかパスワードが間違っています", status_code=404)
    await register_success(SCOPE_GROUP, ip)
    return RedirectResponse(build_url(request, "group.group_room", room_id=room_id, password=password), status_code=302)


@router.get("/group_direct/{room_id}/{password}", name="group.group_direct_access")
async def group_direct_access(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
    if not allowed:
        return room_msg(request, get_block_message(block_label), status_code=429)

    record = await _get_room_if_valid(room_id, password)
    if not record:
        _, block_label = await register_failure(SCOPE_GROUP, ip)
        if block_label:
            return room_msg(request, get_block_message(block_label), status_code=429)
        return room_msg(request, "指定されたルームが見つかりません", status_code=404)

    await register_success(SCOPE_GROUP, ip)

    return RedirectResponse(build_url(request, "group.group_room", room_id=room_id, password=password), status_code=302)


@router.get("/manage_rooms", name="group.manage_rooms")
@router.post("/manage_rooms", name="group.manage_rooms_post")
async def manage_rooms(request: Request):
    if request.method == "POST":
        form = await request.form()
        password = form.get("password")
        if password == management_password:
            request.session["management_authenticated"] = True
        else:
            flash_message(request, "パスワードが違います。 সন")
            return render_template(request, "manage_rooms_login.html")

    if not request.session.get("management_authenticated"):
        return render_template(request, "manage_rooms_login.html")

    rooms = await group_data.get_all()
    return render_template(request, "manage_rooms.html", rooms=rooms)


@router.get("/logout_management", name="group.logout_management")
async def logout_management(request: Request):
    request.session.pop("management_authenticated", None)
    return RedirectResponse("/manage_rooms", status_code=302)


@router.post("/delete_room/{room_id}", name="group.delete_room")
async def delete_room(request: Request, room_id: str):
    await group_data.remove_data(room_id)
    return RedirectResponse("/manage_rooms", status_code=302)


@router.post("/delete_all_rooms", name="group.delete_all_rooms")
async def delete_all_rooms(request: Request):
    await group_data.all_remove()
    return RedirectResponse("/manage_rooms", status_code=302)


def room_msg(request: Request, message: str, status_code: int = 200):
    response = render_template(request, "error.html", message=message)
    response.status_code = status_code
    return response


def _group_block_response(request: Request, block_label):
    message = get_block_message(block_label)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse({"error": message}, status_code=429)
    return room_msg(request, message, status_code=429)
