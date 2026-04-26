import os
import hmac

from fastapi import Request
from starlette.responses import RedirectResponse

from . import group_data

# 一つ上のディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(PARENT_DIR, "static")

# アップロード先フォルダ
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "group_uploads")
GROUP_ROOM_ACCESS_SESSION_KEY = "group_room_access"


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


def remember_group_room_access(request: Request, room_id: str, password: str) -> None:
    rooms = request.session.get(GROUP_ROOM_ACCESS_SESSION_KEY)
    if not isinstance(rooms, dict):
        rooms = {}
    rooms[str(room_id)] = str(password)
    if len(rooms) > 20:
        rooms = dict(list(rooms.items())[-20:])
    request.session[GROUP_ROOM_ACCESS_SESSION_KEY] = rooms


def has_group_room_access(request: Request, room_id: str, password: str) -> bool:
    rooms = request.session.get(GROUP_ROOM_ACCESS_SESSION_KEY)
    if not isinstance(rooms, dict):
        return False
    stored_password = rooms.get(str(room_id))
    if not isinstance(stored_password, str):
        return False
    return hmac.compare_digest(stored_password, str(password))
