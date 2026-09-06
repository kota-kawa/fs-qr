from fastapi import Request
from web import canonical_redirect as shared_canonical_redirect

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
    """互換用の再エクスポート。正規 URL 化は web.py に集約する。"""
    return shared_canonical_redirect(request)


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
