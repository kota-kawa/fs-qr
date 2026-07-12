from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from sqlalchemy import text

from database import execute_query
from settings import SECRET_KEY
from web import build_url


class ServiceKey(str, Enum):
    FSQR = "fsqr"
    NOTE = "note"
    GROUP = "group"


@dataclass(frozen=True)
class ShareLink:
    service_key: ServiceKey
    resource_id: str
    token: str
    url: str


SHARE_ROUTE_NAMES = {
    ServiceKey.FSQR: "fsqr.share_entry",
    ServiceKey.NOTE: "note.share_entry",
    ServiceKey.GROUP: "group.share_entry",
}


ROOM_ROUTE_NAMES = {
    ServiceKey.NOTE: "note.note_room",
    ServiceKey.GROUP: "group.group_room",
}


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    secret = (SECRET_KEY or "").encode("utf-8")
    if secret:
        return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a process-wide Fernet derived from SECRET_KEY."""
    global _fernet
    if _fernet is None:
        digest = hashlib.sha256((SECRET_KEY or "").encode("utf-8")).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet


def encrypt_share_password(password: str) -> str:
    """Encrypt a room password for at-rest storage in share link metadata."""
    if not password:
        return ""
    return _get_fernet().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_share_password(token: str) -> str:
    """Decrypt a password produced by :func:`encrypt_share_password`."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken, ValueError, TypeError:
        return ""


def build_share_url(
    request: Request,
    *,
    service_key: ServiceKey,
    token: str,
    fragment: str = "",
) -> str:
    url = build_url(
        request,
        SHARE_ROUTE_NAMES[service_key],
        token=token,
        _external=True,
    )
    return f"{url}#{fragment}" if fragment else url


def build_room_url(
    request: Request, *, service_key: ServiceKey, resource_id: str
) -> str:
    return build_url(
        request,
        ROOM_ROUTE_NAMES[service_key],
        room_id=resource_id,
    )


async def create_share_link(
    *,
    service_key: ServiceKey,
    resource_id: str,
    expires_at: Any = None,
    scope: str = "read",
    metadata: Mapping[str, Any] | None = None,
) -> str:
    token = generate_token()
    query = text("""
        INSERT INTO share_links (
            service_key, resource_id, token_hash, scope,
            expires_at, metadata, created_at
        )
        VALUES (
            :service_key, :resource_id, :token_hash, :scope,
            :expires_at, :metadata, NOW()
        )
    """)
    await execute_query(
        query,
        {
            "service_key": service_key.value,
            "resource_id": resource_id,
            "token_hash": hash_token(token),
            "scope": scope,
            "expires_at": expires_at,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        },
    )
    return token


async def resolve_share_link(
    token: str, *, service_key: ServiceKey | None = None, scope: str = "read"
):
    token = (token or "").strip()
    if len(token) < 32:
        return None

    query = text("""
        SELECT service_key, resource_id, scope, expires_at, metadata
        FROM share_links
        WHERE token_hash = :token_hash
          AND revoked_at IS NULL
          AND scope = :scope
          AND (expires_at IS NULL OR expires_at > NOW())
        LIMIT 1
    """)
    rows = await execute_query(
        query,
        {"token_hash": hash_token(token), "scope": scope},
        fetch=True,
    )
    if not rows:
        return None
    row = dict(rows[0])
    if service_key and row.get("service_key") != service_key.value:
        return None
    return row


def share_link_metadata(link: Mapping[str, Any] | None) -> dict:
    """Return a share link's metadata as a dict.

    The ``metadata`` column is stored as JSON and may be returned by the driver
    either as an already-decoded mapping or as a raw JSON string. Normalize both
    cases and fall back to an empty dict when absent or malformed.
    """
    if not link:
        return {}
    raw = link.get("metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
        except ValueError, TypeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def share_link_password(link: Mapping[str, Any] | None) -> str:
    """Return the decrypted room password stored in a share link's metadata.

    The password is persisted encrypted under ``password_enc``; only holders of
    the share token (who already have room access) can have it resolved here.
    """
    enc = share_link_metadata(link).get("password_enc")
    return decrypt_share_password(enc) if isinstance(enc, str) else ""


async def revoke_resource_links(*, service_key: ServiceKey, resource_id: str) -> None:
    query = text("""
        UPDATE share_links
        SET revoked_at = NOW()
        WHERE service_key = :service_key
          AND resource_id = :resource_id
          AND revoked_at IS NULL
    """)
    await execute_query(
        query,
        {"service_key": service_key.value, "resource_id": resource_id},
    )
