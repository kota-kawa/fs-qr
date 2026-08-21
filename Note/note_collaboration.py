"""Hocuspocus 接続用の短寿命トークンを発行する。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from settings import SECRET_KEY

TOKEN_TTL_SECONDS = 60 * 60


def create_collaboration_token(room_id: str, *, now: int | None = None) -> str:
    """Create a signed token scoped to one Note room / 1ルーム限定トークンを作る。"""
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is required for Note collaboration")
    issued_at = int(time.time()) if now is None else now
    payload = _base64url(
        json.dumps(
            {"room": room_id, "exp": issued_at + TOKEN_TTL_SECONDS},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        str(SECRET_KEY).encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload}.{_base64url(signature)}"


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
