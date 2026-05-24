from __future__ import annotations

from typing import Any, MutableMapping

from fastapi import Request

NOTE_ROOM_ACCESS_SESSION_KEY = "note_room_access"


def _access_map(session: MutableMapping[str, Any]) -> dict[str, dict[str, str]]:
    rooms = session.get(NOTE_ROOM_ACCESS_SESSION_KEY)
    if not isinstance(rooms, dict):
        rooms = {}
        session[NOTE_ROOM_ACCESS_SESSION_KEY] = rooms
    return rooms


def remember_note_room_access(
    request: Request, room_id: str, share_token: str | None = None
) -> None:
    rooms = _access_map(request.session)
    entry = rooms.get(room_id) if isinstance(rooms.get(room_id), dict) else {}
    if share_token:
        entry["share_token"] = share_token
    rooms[room_id] = entry
    request.session[NOTE_ROOM_ACCESS_SESSION_KEY] = rooms


def has_note_room_access_session(
    session: MutableMapping[str, Any], room_id: str
) -> bool:
    rooms = session.get(NOTE_ROOM_ACCESS_SESSION_KEY)
    return isinstance(rooms, dict) and room_id in rooms


def has_note_room_access(request: Request, room_id: str) -> bool:
    return has_note_room_access_session(request.session, room_id)


def get_note_room_share_token(request: Request, room_id: str) -> str:
    rooms = request.session.get(NOTE_ROOM_ACCESS_SESSION_KEY)
    if not isinstance(rooms, dict):
        return ""
    entry = rooms.get(room_id)
    if not isinstance(entry, dict):
        return ""
    token = entry.get("share_token")
    return token if isinstance(token, str) else ""
