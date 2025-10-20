"""Simple in-memory IP based rate limiting for authentication-like endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Optional, Tuple

THRESHOLDS = (
    (50, timedelta(days=1), "1日"),
    (10, timedelta(minutes=30), "30分"),
)

SCOPE_QR = "qr"
SCOPE_NOTE = "note"
SCOPE_GROUP = "group"


class _AttemptState:
    __slots__ = ("count", "block_until", "block_label")

    def __init__(self) -> None:
        self.count: int = 0
        self.block_until: Optional[datetime] = None
        self.block_label: Optional[str] = None


_attempts: Dict[str, Dict[str, _AttemptState]] = {}
_lock = Lock()


def _get_state(scope: str, ip: str) -> _AttemptState:
    scope_bucket = _attempts.setdefault(scope, {})
    state = scope_bucket.get(ip)
    if state is None:
        state = _AttemptState()
        scope_bucket[ip] = state
    return state


def _reset_state(scope: str, ip: str, state: _AttemptState) -> None:
    state.count = 0
    state.block_until = None
    state.block_label = None
    scope_bucket = _attempts.get(scope)
    if scope_bucket is not None:
        scope_bucket[ip] = state
        if not state.count and state.block_until is None:
            # Keep dictionary from growing unbounded
            # by removing entries that are completely reset.
            scope_bucket.pop(ip, None)


def check_rate_limit(scope: str, ip: str) -> Tuple[bool, Optional[datetime], Optional[str]]:
    """Check whether the given IP is currently blocked for the scope."""
    now = datetime.utcnow()
    with _lock:
        scope_bucket = _attempts.get(scope)
        if not scope_bucket:
            return True, None, None
        state = scope_bucket.get(ip)
        if state is None:
            return True, None, None
        block_until = state.block_until
        if block_until and now < block_until:
            return False, block_until, state.block_label
        if block_until and now >= block_until:
            _reset_state(scope, ip, state)
    return True, None, None


def register_failure(scope: str, ip: str) -> Tuple[Optional[datetime], Optional[str]]:
    """Record a failed attempt. Returns block information when a block is active."""
    now = datetime.utcnow()
    with _lock:
        state = _get_state(scope, ip)
        block_until = state.block_until
        if block_until and now < block_until:
            return block_until, state.block_label
        if block_until and now >= block_until:
            _reset_state(scope, ip, state)
            state = _get_state(scope, ip)
        state.count += 1
        for threshold, duration, label in THRESHOLDS:
            if state.count >= threshold:
                state.block_until = now + duration
                state.block_label = label
                return state.block_until, state.block_label
        state.block_until = None
        state.block_label = None
        return None, None


def register_success(scope: str, ip: str) -> None:
    """Reset counters after a successful attempt."""
    with _lock:
        scope_bucket = _attempts.get(scope)
        if not scope_bucket:
            return
        state = scope_bucket.get(ip)
        if not state:
            return
        _reset_state(scope, ip, state)


def get_block_message(label: Optional[str]) -> str:
    if label == "1日":
        return "一定回数以上の失敗があったため、この機能へのアクセスを1日間ブロックしています。時間をおいて再度お試しください。"
    if label == "30分":
        return "一定回数以上の失敗があったため、この機能へのアクセスを30分間ブロックしています。時間をおいて再度お試しください。"
    return "一定回数以上の失敗があったため、この機能へのアクセスを制限しています。時間をおいて再度お試しください。"


def get_client_ip() -> str:
    from flask import request

    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.remote_addr or "unknown"

