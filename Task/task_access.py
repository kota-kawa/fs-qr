from __future__ import annotations

from typing import Any, MutableMapping

from fastapi import Request

import room_access

TASK_ROOM_ACCESS_SESSION_KEY = "task_room_access"


def remember_task_room_access(
    request: Request,
    room_id: str,
    share_token: str | None = None,
    password: str | None = None,
    can_delete: bool = False,
) -> None:
    payload: dict[str, str] = {}
    if share_token:
        payload["share_token"] = share_token
    if password:
        payload["password"] = password
    if can_delete:
        payload["can_delete"] = "1"
    room_access.grant_access(
        request.session,
        TASK_ROOM_ACCESS_SESSION_KEY,
        room_id,
        payload=payload or None,
    )


def has_task_room_access_session(
    session: MutableMapping[str, Any], room_id: str
) -> bool:
    return room_access.has_access(session, TASK_ROOM_ACCESS_SESSION_KEY, room_id)


def has_task_room_access(request: Request, room_id: str) -> bool:
    return has_task_room_access_session(request.session, room_id)


def get_task_room_share_token(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, TASK_ROOM_ACCESS_SESSION_KEY, room_id, "share_token", ""
    )


def get_task_room_password(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, TASK_ROOM_ACCESS_SESSION_KEY, room_id, "password", ""
    )


def can_delete_task_room(request: Request, room_id: str) -> bool:
    return (
        room_access.get_access_field(
            request.session, TASK_ROOM_ACCESS_SESSION_KEY, room_id, "can_delete", ""
        )
        == "1"
    )


def forget_task_room_access(request: Request, room_id: str) -> None:
    room_access.revoke_access(request.session, TASK_ROOM_ACCESS_SESSION_KEY, room_id)
