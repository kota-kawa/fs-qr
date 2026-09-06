"""ルーム ID とパスワードの生成・検証を全サービスで共有するヘルパー。

Shared helpers for generating and validating room ids / passwords used by
FSQR, Group, Note and Task. Service modules should import from here instead of
keeping their own copies of the six-character alphanumeric rules.
"""

from __future__ import annotations

import secrets
import string
from typing import Any, Awaitable, Callable

from pydantic import ValidationError

from models import ROOM_ID_LENGTH, ROOM_ID_RE, RoomInputError, RoomSearchInput

__all__ = [
    "ROOM_ID_ATTEMPTS",
    "ROOM_ID_CHARS",
    "ROOM_ID_LENGTH",
    "RoomInputError",
    "allocate_unique_room_id",
    "generate_room_id",
    "generate_room_password",
    "is_valid_room_id",
    "validate_room_credentials",
]

ROOM_ID_CHARS = string.ascii_letters + string.digits
# 自動生成 ID が既存ルームと衝突したときの再試行回数。
# How many random ids to try before giving up on auto allocation.
ROOM_ID_ATTEMPTS = 10


def generate_room_id() -> str:
    """暗号論的に安全な乱数で 6 文字の半角英数字 ID を生成する。"""
    return "".join(secrets.choice(ROOM_ID_CHARS) for _ in range(ROOM_ID_LENGTH))


def generate_room_password() -> str:
    """6 桁の数字パスワードを生成する（先頭ゼロも許可）。"""
    return str(secrets.randbelow(10**6)).zfill(6)


def is_valid_room_id(value: str | None) -> bool:
    """値が 6 文字の半角英数字 ID かどうかを返す。空文字や None は False。"""
    return bool(value) and bool(ROOM_ID_RE.match(str(value)))


async def allocate_unique_room_id(
    exists: Callable[[str], Awaitable[Any]], attempts: int = ROOM_ID_ATTEMPTS
) -> str | None:
    """既存ルームと重複しない ID を生成する。

    ``exists(room_id)`` が真を返す限り再試行し、``attempts`` 回すべて衝突した
    場合は ``None`` を返す。Returns ``None`` when every candidate collided.
    """
    for _ in range(attempts):
        candidate = generate_room_id()
        if not await exists(candidate):
            return candidate
    return None


def _first_validation_error(exc: ValidationError) -> dict[str, Any]:
    errors = exc.errors()
    return errors[0] if errors else {}


def validate_room_credentials(room_id: str, password: str) -> tuple[str, str]:
    """検索・ログインフォームの ID とパスワードを検証して正規化する。

    失敗時は ``RoomInputError`` (ValueError の派生) を送出する。従来どおり
    ``str(exc)`` で日本語文言が得られ、``exc.message_key`` で翻訳キーが分かる。
    """
    try:
        credentials = RoomSearchInput(room_id=room_id, password=password)
    except ValidationError as exc:
        first_error = _first_validation_error(exc)
        # field_validator 内で送出した RoomInputError は ctx.error に保持される。
        # Pydantic keeps the original exception under ``ctx.error``.
        original = (first_error.get("ctx") or {}).get("error")
        if isinstance(original, RoomInputError):
            raise RoomInputError(str(original), key=original.message_key) from exc
        message = str(first_error.get("msg") or "IDまたはパスワードが不正です。")
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        raise RoomInputError(message, key="invalid_credentials") from exc
    return credentials.room_id, credentials.password
