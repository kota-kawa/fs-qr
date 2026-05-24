import hmac

from fastapi import Request
from starlette.responses import RedirectResponse

from i18n import is_language_query_only
from .group_storage import UPLOAD_FOLDER, is_safe_path
from . import group_data

GROUP_ROOM_ACCESS_SESSION_KEY = "group_room_access"


def canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def get_room_if_valid(room_id, password):
    return await group_data.get_data_by_room_credentials(room_id, password)


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
