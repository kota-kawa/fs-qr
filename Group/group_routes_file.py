import io
import os
import shutil
import urllib
import zipfile
from typing import Optional

from fastapi import APIRouter, File, Request, UploadFile
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from werkzeug.utils import secure_filename

from file_validation import (
    sanitize_group_upload_filename,
    validate_requested_filename,
    validate_upload_limits,
)
from settings import UPLOAD_MAX_FILES, UPLOAD_MAX_TOTAL_SIZE_BYTES, UPLOAD_MAX_TOTAL_SIZE_MB
from .group_common import UPLOAD_FOLDER, get_room_if_valid, is_safe_path
from .group_realtime import notify_group_files_updated
from web import enforce_csrf


def register_group_upload_route(router: APIRouter):
    @router.post("/group_upload/{room_id}/{password}", name="group.group_upload")
    async def group_upload(
        request: Request,
        room_id: str,
        password: str,
        upfile: Optional[list[UploadFile]] = File(None),
    ):
        await enforce_csrf(request)
        record = await get_room_if_valid(room_id, password)
        if not record:
            return JSONResponse(
                {"error": "ルームが見つからないか、パスワードが間違っています。"},
                status_code=400,
            )

        if not upfile:
            return JSONResponse(
                {"error": "ファイルがアップロードされていません。"}, status_code=400
            )

        limits_error = validate_upload_limits(
            upfile,
            max_files=UPLOAD_MAX_FILES,
            max_total_size_bytes=UPLOAD_MAX_TOTAL_SIZE_BYTES,
            max_total_size_mb=UPLOAD_MAX_TOTAL_SIZE_MB,
        )
        if limits_error:
            return JSONResponse(
                {"error": limits_error},
                status_code=400,
            )

        error_files = []
        saved_files_count = 0
        save_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        os.makedirs(save_path, exist_ok=True)

        for file in upfile:
            if file.filename == "":
                continue

            safe_filename = sanitize_group_upload_filename(file.filename)

            file_path = os.path.join(save_path, safe_filename)

            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                if os.path.getsize(file_path) == 0:
                    error_files.append(file.filename)
                    os.remove(file_path)
                else:
                    saved_files_count += 1
            except Exception:
                error_files.append(file.filename)

        if error_files:
            if saved_files_count > 0:
                await notify_group_files_updated(room_id)
            return JSONResponse(
                {
                    "status": "error",
                    "message": "以下のファイルが保存できませんでした。",
                    "files": error_files,
                },
                status_code=500,
            )

        await notify_group_files_updated(room_id)
        return JSONResponse(
            {"status": "success", "message": "ファイルが正常にアップロードされました。"}
        )


def register_group_list_files_route(router: APIRouter):
    @router.get("/check/{room_id}/{password}", name="group.list_files")
    async def list_files(request: Request, room_id: str, password: str):
        if not await get_room_if_valid(room_id, password):
            return JSONResponse(
                {"error": "ルームが見つからないか、パスワードが間違っています。"},
                status_code=404,
            )

        target_directory = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        if not os.path.exists(target_directory):
            return JSONResponse(
                {"error": "ルームIDのディレクトリが見つかりません。"}, status_code=404
            )

        if not is_safe_path(UPLOAD_FOLDER, target_directory):
            return JSONResponse(
                {"error": "不正なパスが検出されました。"}, status_code=400
            )

        try:
            files = [
                {"name": file_name}
                for file_name in os.listdir(target_directory)
                if os.path.isfile(os.path.join(target_directory, file_name))
            ]
            return JSONResponse(files)
        except Exception as e:
            return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


def register_group_download_all_route(router: APIRouter):
    @router.get("/download/all/{room_id}/{password}", name="group.download_all_files")
    async def download_all_files(request: Request, room_id: str, password: str):
        if not await get_room_if_valid(room_id, password):
            return JSONResponse(
                {"error": "ルームが見つからないか、パスワードが間違っています。"},
                status_code=404,
            )

        room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        if not os.path.exists(room_folder):
            return JSONResponse(
                {"error": "指定されたルームIDのファイルが見つかりません。"},
                status_code=404,
            )

        try:
            zip_stream = io.BytesIO()
            with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zipf:
                for filename in os.listdir(room_folder):
                    file_path = os.path.join(room_folder, filename)
                    if os.path.isfile(file_path) and is_safe_path(
                        room_folder, file_path
                    ):
                        with open(file_path, "rb") as f:
                            zipf.writestr(filename, f.read())
            zip_stream.seek(0)
            headers = {
                "Content-Disposition": f"attachment; filename={room_id}_files.zip"
            }
            return StreamingResponse(
                zip_stream, media_type="application/zip", headers=headers
            )
        except Exception as e:
            return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


def register_group_download_file_route(router: APIRouter):
    @router.get(
        "/download/{room_id}/{password}/{filename:path}", name="group.download_file"
    )
    async def download_file(
        request: Request, room_id: str, password: str, filename: str
    ):
        decoded_filename = urllib.parse.unquote(filename)

        filename_error = validate_requested_filename(decoded_filename)
        if filename_error:
            return JSONResponse({"error": filename_error}, status_code=400)

        if not await get_room_if_valid(room_id, password):
            return JSONResponse(
                {"error": "ルームが見つからないか、パスワードが間違っています。"},
                status_code=404,
            )

        room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        file_path = os.path.join(room_folder, decoded_filename)

        if not is_safe_path(room_folder, file_path):
            return JSONResponse(
                {"error": "不正なパスが検出されました。"}, status_code=400
            )

        try:
            if os.path.exists(file_path):
                return FileResponse(file_path, filename=decoded_filename)
            return JSONResponse(
                {"error": "ファイルが見つかりません。"}, status_code=404
            )
        except Exception as e:
            return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)


def register_group_delete_file_route(router: APIRouter):
    @router.delete("/delete/{room_id}/{password}/{filename}", name="group.delete_file")
    async def delete_file(request: Request, room_id: str, password: str, filename: str):
        await enforce_csrf(request)
        decoded_filename = urllib.parse.unquote(filename)

        filename_error = validate_requested_filename(decoded_filename)
        if filename_error:
            return JSONResponse({"error": filename_error}, status_code=400)

        if not await get_room_if_valid(room_id, password):
            return JSONResponse(
                {"error": "ルームが見つからないか、パスワードが間違っています。"},
                status_code=404,
            )

        room_folder = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        file_path = os.path.join(room_folder, decoded_filename)

        if not is_safe_path(room_folder, file_path):
            return JSONResponse(
                {"error": "不正なパスが検出されました。"}, status_code=400
            )

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                await notify_group_files_updated(room_id)
                return JSONResponse(
                    {"message": "ファイルが削除されました。"}, status_code=200
                )
            return JSONResponse(
                {"error": "ファイルが見つかりません。"}, status_code=404
            )
        except Exception as e:
            return JSONResponse({"error": f"エラー: {str(e)}"}, status_code=500)
