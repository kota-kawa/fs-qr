from fastapi import Request
from starlette.responses import RedirectResponse

from i18n import is_language_query_only

from .task_access import (
    can_delete_task_room,
    forget_task_room_access,
    get_task_room_password,
    get_task_room_share_token,
    has_task_room_access,
    remember_task_room_access,
)
from .task_data import get_room_meta_direct


def canonical_redirect(request: Request):
    # 言語選択だけのクエリはページ表示に必要なため、正規 URL へ戻さない。
    if request.url.query and not is_language_query_only(request):
        return RedirectResponse(str(request.url.replace(query="")), status_code=301)
    return None


async def get_room_if_active(room_id: str):
    return await get_room_meta_direct(room_id)


async def get_room_if_valid(room_id: str, password: str):
    return await get_room_meta_direct(room_id, password)


__all__ = [
    "canonical_redirect",
    "get_room_if_active",
    "get_room_if_valid",
    "can_delete_task_room",
    "forget_task_room_access",
    "get_task_room_password",
    "get_task_room_share_token",
    "has_task_room_access",
    "remember_task_room_access",
]
