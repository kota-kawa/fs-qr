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


def remember_group_room_access(request: Request, room_id: str) -> None:
    # Record only that this session entered the room. The password is not
    # stored: callers (e.g. file delete) re-validate the supplied password
    # against the database on every request, so persisting it would add a
    # plaintext credential to the session store for no security benefit.
    room_access.grant_access(request.session, GROUP_ROOM_ACCESS_SESSION_KEY, room_id)


def has_group_room_access(request: Request, room_id: str) -> bool:
    return room_access.has_access(
        request.session, GROUP_ROOM_ACCESS_SESSION_KEY, room_id
    )
