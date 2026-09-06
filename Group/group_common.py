from fastapi import Request

from room_session import GROUP_ACCESS
from . import group_data

GROUP_ROOM_ACCESS_SESSION_KEY = "group_room_access"


def canonical_redirect(request: Request):
    """互換用の再エクスポート。正規化処理は web.py に集約する。"""
    from web import canonical_redirect as shared_canonical_redirect

    return shared_canonical_redirect(request)


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
    can_delete: bool = False,
) -> None:
    GROUP_ACCESS.remember(
        request,
        room_id,
        share_token=share_token,
        password=password,
        can_delete=can_delete,
    )


def has_group_room_access(request: Request, room_id: str) -> bool:
    return GROUP_ACCESS.has(request, room_id)


def get_group_room_share_token(request: Request, room_id: str) -> str:
    return GROUP_ACCESS.share_token(request, room_id)


def get_group_room_password(request: Request, room_id: str) -> str:
    return GROUP_ACCESS.password(request, room_id)


def can_delete_group_room(request: Request, room_id: str) -> bool:
    return GROUP_ACCESS.can_delete(request, room_id)


def forget_group_room_access(request: Request, room_id: str) -> None:
    GROUP_ACCESS.forget(request, room_id)
