from fastapi import Request
from starlette.responses import RedirectResponse

import room_access
from i18n import is_language_query_only
from . import group_data

GROUP_ROOM_ACCESS_SESSION_KEY = "group_room_access"


def canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def get_room_if_valid(room_id, password):
    return await group_data.get_data_by_room_credentials(room_id, password)


async def get_room_if_active(room_id):
    rows = await group_data.get_data(room_id)
    return rows[0] if rows else None


def remember_group_room_access(
    request: Request,
    room_id: str,
    share_token: str | None = None,
    password: str | None = None,
) -> None:
    payload = {}
    if share_token:
        payload["share_token"] = share_token
    if password:
        payload["password"] = password
    room_access.grant_access(
        request.session,
        GROUP_ROOM_ACCESS_SESSION_KEY,
        room_id,
        payload=payload or None,
    )


def has_group_room_access(request: Request, room_id: str) -> bool:
    return room_access.has_access(
        request.session, GROUP_ROOM_ACCESS_SESSION_KEY, room_id
    )


def get_group_room_share_token(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, GROUP_ROOM_ACCESS_SESSION_KEY, room_id, "share_token", ""
    )


def get_group_room_password(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, GROUP_ROOM_ACCESS_SESSION_KEY, room_id, "password", ""
    )
