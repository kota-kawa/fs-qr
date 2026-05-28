import io
import mimetypes
import os
import shutil
import urllib
import zipfile
from typing import Optional

from fastapi import APIRouter, File, Request, UploadFile
from starlette.responses import Response, StreamingResponse
from werkzeug.utils import secure_filename

from api_response import api_error_response, api_ok_response
from file_validation import (
    build_content_disposition_attachment,
    build_content_disposition_inline,
    sanitize_group_upload_filename,
    validate_upload_file_content,
    validate_requested_filename,
    validate_upload_limits,
)
from settings import (
    UPLOAD_MAX_FILES,
    UPLOAD_MAX_TOTAL_SIZE_BYTES,
    UPLOAD_MAX_TOTAL_SIZE_MB,
)
from rate_limit import (
    SCOPE_GROUP_FILE_DELETE,
    check_exponential_backoff,
    clear_exponential_backoff,
    get_client_ip,
    register_exponential_backoff_failure,
)
from .group_common import (
    get_room_if_active,
    has_group_room_access,
)
from .group_storage import (
    UPLOAD_FOLDER,
    collect_room_files,
    existing_room_folders,
    is_safe_path,
    resolve_room_file,
    room_folder,
    unique_room_filename,
)
from .group_realtime import notify_group_files_updated
from web import enforce_csrf


_PREVIEW_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/json": "text",
    "image/apng": "image",
    "image/avif": "image",
    "image/bmp": "image",
    "image/gif": "image",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "text/csv": "text",
    "text/markdown": "text",
    "text/plain": "text",
}

_PREVIEW_EXTENSIONS = {
    ".apng": ("image/apng", "image"),
    ".avif": ("image/avif", "image"),
    ".bmp": ("image/bmp", "image"),
    ".csv": ("text/csv", "text"),
    ".gif": ("image/gif", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".jpg": ("image/jpeg", "image"),
    ".json": ("application/json", "text"),
    ".md": ("text/markdown", "text"),
    ".pdf": ("application/pdf", "pdf"),
    ".png": ("image/png", "image"),
    ".txt": ("text/plain", "text"),
    ".webp": ("image/webp", "image"),
}


def get_preview_metadata(filename: str) -> dict[str, str | bool]:
    _, extension = os.path.splitext(filename.lower())
    if extension in _PREVIEW_EXTENSIONS:
        media_type, preview_type = _PREVIEW_EXTENSIONS[extension]
        return {
            "previewable": True,
            "preview_type": preview_type,
            "preview_mime_type": media_type,
        }

    guessed_type, _ = mimetypes.guess_type(filename)
    preview_type = _PREVIEW_MIME_TYPES.get(guessed_type or "")
    if preview_type:
        return {
            "previewable": True,
            "preview_type": preview_type,
            "preview_mime_type": guessed_type,
        }

    return {
        "previewable": False,
        "preview_type": "",
        "preview_mime_type": "",
    }


def register_group_upload_route(router: APIRouter):
    @router.post("/group_upload/{room_id}", name="group.group_upload")
    async def group_upload(
        request: Request,
        room_id: str,
        upfile: Optional[list[UploadFile]] = File(None),
    ):
        await enforce_csrf(request)
        if not has_group_room_access(request, room_id):
            return api_error_response(
                "ルームセッションが確認できません。共有URLから入り直してください。",
                status_code=403,
            )
        if not await get_room_if_active(room_id):
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )

        if not upfile:
            return api_error_response(
                "ファイルがアップロードされていません。", status_code=400
            )

        limits_error = validate_upload_limits(
            upfile,
            max_files=UPLOAD_MAX_FILES,
            max_total_size_bytes=UPLOAD_MAX_TOTAL_SIZE_BYTES,
            max_total_size_mb=UPLOAD_MAX_TOTAL_SIZE_MB,
        )
        if limits_error:
            return api_error_response(
                limits_error,
                status_code=400,
            )

        error_files = []
        rejected_files = []
        saved_files = []
        save_path = room_folder(room_id, root=UPLOAD_FOLDER)
        os.makedirs(save_path, exist_ok=True)

        for file in upfile:
            if file.filename == "":
                continue

            content_error = validate_upload_file_content(file)
            if content_error:
                rejected_files.append(file.filename)
                continue

            safe_filename = unique_room_filename(
                room_id,
                sanitize_group_upload_filename(file.filename),
                primary_root=UPLOAD_FOLDER,
            )

            file_path = os.path.join(save_path, safe_filename)

            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                if os.path.getsize(file_path) == 0:
                    error_files.append(file.filename)
                    os.remove(file_path)
                else:
                    saved_files.append(safe_filename)
            except Exception:
                error_files.append(file.filename)

        if rejected_files:
            if saved_files:
                await notify_group_files_updated(room_id)
            return api_error_response(
                "HTML/SVG ファイルはアップロードできません。",
                status_code=400,
                data={"files": rejected_files},
            )

        if error_files:
            if saved_files:
                await notify_group_files_updated(room_id)
            return api_error_response(
                "以下のファイルが保存できませんでした。",
                status_code=500,
                data={"files": error_files},
            )

        await notify_group_files_updated(room_id)
        return api_ok_response(
            {
                "message": "ファイルが正常にアップロードされました。",
                "saved_files": saved_files,
            }
        )


def register_group_list_files_route(router: APIRouter):
    @router.get("/check/{room_id}", name="group.list_files")
    async def list_files(request: Request, room_id: str):
        if not has_group_room_access(request, room_id):
            return api_error_response(
                "ルームセッションが確認できません。共有URLから入り直してください。",
                status_code=403,
            )
        if not await get_room_if_active(room_id):
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )

        room_files = collect_room_files(room_id, primary_root=UPLOAD_FOLDER)
        if not room_files and not existing_room_folders(
            room_id, primary_root=UPLOAD_FOLDER
        ):
            return api_error_response(
                "ルームIDのディレクトリが見つかりません。", status_code=404
            )

        try:
            files = [
                {"name": file_name, **get_preview_metadata(file_name)}
                for file_name in sorted(room_files.keys(), key=str.lower)
            ]
            return api_ok_response({"files": files})
        except Exception as e:
            return api_error_response(f"エラー: {str(e)}", status_code=500)


def register_group_download_all_route(router: APIRouter):
    @router.get("/download/all/{room_id}", name="group.download_all_files")
    async def download_all_files(request: Request, room_id: str):
        if not has_group_room_access(request, room_id):
            return api_error_response(
                "ルームセッションが確認できません。共有URLから入り直してください。",
                status_code=403,
            )
        if not await get_room_if_active(room_id):
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )

        room_files = collect_room_files(room_id, primary_root=UPLOAD_FOLDER)
        if not room_files:
            return api_error_response(
                "指定されたルームIDのファイルが見つかりません。",
                status_code=404,
            )

        try:
            zip_stream = io.BytesIO()
            with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zipf:
                for filename, file_path in room_files.items():
                    with open(file_path, "rb") as f:
                        zipf.writestr(filename, f.read())
            zip_stream.seek(0)
            download_name = secure_filename(f"{room_id}_files.zip") or "room_files.zip"
            headers = {
                "Content-Disposition": build_content_disposition_attachment(
                    download_name
                )
            }
            return StreamingResponse(
                zip_stream, media_type="application/zip", headers=headers
            )
        except Exception as e:
            return api_error_response(f"エラー: {str(e)}", status_code=500)


def register_group_download_file_route(router: APIRouter):
    @router.get("/download/{room_id}/{filename:path}", name="group.download_file")
    async def download_file(request: Request, room_id: str, filename: str):
        decoded_filename = urllib.parse.unquote(filename)

        filename_error = validate_requested_filename(decoded_filename)
        if filename_error:
            return api_error_response(filename_error, status_code=400)

        if not has_group_room_access(request, room_id):
            return api_error_response(
                "ルームセッションが確認できません。共有URLから入り直してください。",
                status_code=403,
            )
        if not await get_room_if_active(room_id):
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )

        source_folder, file_path = resolve_room_file(
            room_id, decoded_filename, primary_root=UPLOAD_FOLDER
        )

        if not source_folder or not file_path:
            return api_error_response("ファイルが見つかりません。", status_code=404)

        if not is_safe_path(source_folder, file_path):
            return api_error_response("不正なパスが検出されました。", status_code=400)

        try:
            headers = {
                "Content-Disposition": build_content_disposition_attachment(
                    decoded_filename
                ),
                "Content-Length": str(os.path.getsize(file_path)),
            }
            with open(file_path, "rb") as file:
                return Response(
                    content=file.read(),
                    media_type="application/octet-stream",
                    headers=headers,
                )
        except Exception as e:
            return api_error_response(f"エラー: {str(e)}", status_code=500)


def register_group_preview_file_route(router: APIRouter):
    @router.get("/preview/{room_id}/{filename:path}", name="group.preview_file")
    async def preview_file(request: Request, room_id: str, filename: str):
        decoded_filename = urllib.parse.unquote(filename)

        filename_error = validate_requested_filename(decoded_filename)
        if filename_error:
            return api_error_response(filename_error, status_code=400)

        if not has_group_room_access(request, room_id):
            return api_error_response(
                "ルームセッションが確認できません。共有URLから入り直してください。",
                status_code=403,
            )
        if not await get_room_if_active(room_id):
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )

        preview_metadata = get_preview_metadata(decoded_filename)
        if not preview_metadata["previewable"]:
            return api_error_response(
                "このファイル形式はプレビューできません。",
                status_code=415,
            )

        source_folder, file_path = resolve_room_file(
            room_id, decoded_filename, primary_root=UPLOAD_FOLDER
        )

        if not source_folder or not file_path:
            return api_error_response("ファイルが見つかりません。", status_code=404)

        if not is_safe_path(source_folder, file_path):
            return api_error_response("不正なパスが検出されました。", status_code=400)

        try:
            headers = {
                "Content-Disposition": build_content_disposition_inline(
                    decoded_filename
                ),
                "Content-Length": str(os.path.getsize(file_path)),
                "X-Content-Type-Options": "nosniff",
            }
            with open(file_path, "rb") as file:
                return Response(
                    content=file.read(),
                    media_type=str(preview_metadata["preview_mime_type"]),
                    headers=headers,
                )
        except Exception as e:
            return api_error_response(f"エラー: {str(e)}", status_code=500)


def register_group_delete_file_route(router: APIRouter):
    @router.delete("/delete/{room_id}/{filename}", name="group.delete_file")
    async def delete_file(request: Request, room_id: str, filename: str):
        await enforce_csrf(request)
        decoded_filename = urllib.parse.unquote(filename)

        filename_error = validate_requested_filename(decoded_filename)
        if filename_error:
            return api_error_response(filename_error, status_code=400)

        ip = get_client_ip(request)
        backoff_key = f"{ip}:{room_id}"
        allowed, _, _ = await check_exponential_backoff(
            SCOPE_GROUP_FILE_DELETE, backoff_key
        )
        if not allowed:
            return api_error_response(
                "試行回数が多いため、一時的に制限しています。時間をおいて再度お試しください。",
                status_code=429,
            )

        if not has_group_room_access(request, room_id):
            await register_exponential_backoff_failure(
                SCOPE_GROUP_FILE_DELETE, backoff_key
            )
            return api_error_response(
                "ルームセッションが確認できません。ルームに入り直してください。",
                status_code=403,
            )

        if not await get_room_if_active(room_id):
            await register_exponential_backoff_failure(
                SCOPE_GROUP_FILE_DELETE, backoff_key
            )
            return api_error_response(
                "ルームが見つかりません。",
                status_code=404,
            )
        await clear_exponential_backoff(SCOPE_GROUP_FILE_DELETE, backoff_key)

        source_folder, file_path = resolve_room_file(
            room_id, decoded_filename, primary_root=UPLOAD_FOLDER
        )

        if not source_folder or not file_path:
            return api_error_response("ファイルが見つかりません。", status_code=404)

        if not is_safe_path(source_folder, file_path):
            return api_error_response("不正なパスが検出されました。", status_code=400)

        try:
            os.remove(file_path)
            await notify_group_files_updated(room_id)
            return api_ok_response(
                {"message": "ファイルが削除されました。"}, status_code=200
            )
        except Exception as e:
            return api_error_response(f"エラー: {str(e)}", status_code=500)
