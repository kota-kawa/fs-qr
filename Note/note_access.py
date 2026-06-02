from __future__ import annotations

from typing import Any, MutableMapping

from fastapi import Request

import room_access

NOTE_ROOM_ACCESS_SESSION_KEY = "note_room_access"


def remember_note_room_access(
    request: Request,
    room_id: str,
    share_token: str | None = None,
    password: str | None = None,
    can_delete: bool = False,
) -> None:
    payload = {}
    if share_token:
        payload["share_token"] = share_token
    if password:
        payload["password"] = password
    if can_delete:
        payload["can_delete"] = "1"
    room_access.grant_access(
        request.session,
        NOTE_ROOM_ACCESS_SESSION_KEY,
        room_id,
        payload=payload or None,
    )


def has_note_room_access_session(
    session: MutableMapping[str, Any], room_id: str
) -> bool:
    return room_access.has_access(session, NOTE_ROOM_ACCESS_SESSION_KEY, room_id)


def has_note_room_access(request: Request, room_id: str) -> bool:
    return has_note_room_access_session(request.session, room_id)


def get_note_room_share_token(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, NOTE_ROOM_ACCESS_SESSION_KEY, room_id, "share_token", ""
    )


def get_note_room_password(request: Request, room_id: str) -> str:
    return room_access.get_access_field(
        request.session, NOTE_ROOM_ACCESS_SESSION_KEY, room_id, "password", ""
    )


def can_delete_note_room(request: Request, room_id: str) -> bool:
    return (
        room_access.get_access_field(
            request.session, NOTE_ROOM_ACCESS_SESSION_KEY, room_id, "can_delete", ""
        )
        == "1"
    )


def forget_note_room_access(request: Request, room_id: str) -> None:
    room_access.revoke_access(request.session, NOTE_ROOM_ACCESS_SESSION_KEY, room_id)
