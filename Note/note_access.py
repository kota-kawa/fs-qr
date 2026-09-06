from __future__ import annotations

from typing import Any, MutableMapping

from fastapi import Request

from room_session import NOTE_ACCESS

NOTE_ROOM_ACCESS_SESSION_KEY = "note_room_access"


def remember_note_room_access(
    request: Request,
    room_id: str,
    share_token: str | None = None,
    password: str | None = None,
    can_delete: bool = False,
) -> None:
    NOTE_ACCESS.remember(
        request,
        room_id,
        share_token=share_token,
        password=password,
        can_delete=can_delete,
    )


def has_note_room_access_session(
    session: MutableMapping[str, Any], room_id: str
) -> bool:
    return NOTE_ACCESS.has_session(session, room_id)


def has_note_room_access(request: Request, room_id: str) -> bool:
    return has_note_room_access_session(request.session, room_id)


def get_note_room_share_token(request: Request, room_id: str) -> str:
    return NOTE_ACCESS.share_token(request, room_id)


def get_note_room_password(request: Request, room_id: str) -> str:
    return NOTE_ACCESS.password(request, room_id)


def can_delete_note_room(request: Request, room_id: str) -> bool:
    return NOTE_ACCESS.can_delete(request, room_id)


def forget_note_room_access(request: Request, room_id: str) -> None:
    NOTE_ACCESS.forget(request, room_id)
