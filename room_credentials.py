from __future__ import annotations

import secrets

from pydantic import ValidationError

from models import RoomSearchInput


def generate_room_password() -> str:
    return str(secrets.randbelow(10**6)).zfill(6)


def validate_room_credentials(room_id: str, password: str) -> tuple[str, str]:
    try:
        credentials = RoomSearchInput(room_id=room_id, password=password)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        message = str(first_error.get("msg") or "IDまたはパスワードが不正です。")
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        raise ValueError(message) from exc
    return credentials.room_id, credentials.password
