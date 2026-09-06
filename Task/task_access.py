from __future__ import annotations

from typing import Any, MutableMapping

from fastapi import Request

from room_session import TASK_ACCESS

TASK_ROOM_ACCESS_SESSION_KEY = "task_room_access"


def remember_task_room_access(
    request: Request,
    room_id: str,
    share_token: str | None = None,
    password: str | None = None,
    can_delete: bool = False,
) -> None:
    TASK_ACCESS.remember(
        request,
        room_id,
        share_token=share_token,
        password=password,
        can_delete=can_delete,
    )


def has_task_room_access_session(
    session: MutableMapping[str, Any], room_id: str
) -> bool:
    return TASK_ACCESS.has_session(session, room_id)


def has_task_room_access(request: Request, room_id: str) -> bool:
    return has_task_room_access_session(request.session, room_id)


def get_task_room_share_token(request: Request, room_id: str) -> str:
    return TASK_ACCESS.share_token(request, room_id)


def get_task_room_password(request: Request, room_id: str) -> str:
    return TASK_ACCESS.password(request, room_id)


def can_delete_task_room(request: Request, room_id: str) -> bool:
    return TASK_ACCESS.can_delete(request, room_id)


def forget_task_room_access(request: Request, room_id: str) -> None:
    TASK_ACCESS.forget(request, room_id)
