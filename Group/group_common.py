import os

from fastapi import Request
from starlette.responses import RedirectResponse

from . import group_data

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(PARENT_DIR, "static")

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "group_uploads")


def is_safe_path(base_path, target_path):
    return os.path.commonprefix(
        [os.path.abspath(target_path), os.path.abspath(base_path)]
    ) == os.path.abspath(base_path)


def canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def get_room_if_valid(room_id, password):
    room_data = await group_data.get_data_direct(room_id)
    if not room_data:
        return None
    record = room_data[0]
    if record.get("password") != password:
        return None
    return record
