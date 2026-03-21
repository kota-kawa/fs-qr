import logging
from typing import Any, Tuple

from fastapi import Request

logger = logging.getLogger(__name__)


def session_get(request: Request, key: str, default: Any = None) -> Tuple[bool, Any]:
    try:
        return True, request.session.get(key, default)
    except Exception as exc:
        logger.warning(
            "Failed to read session key %s on %s %s: %s",
            key,
            request.method,
            request.url.path,
            exc,
        )
        return False, default


def session_set(request: Request, key: str, value: Any) -> bool:
    try:
        request.session[key] = value
        return True
    except Exception as exc:
        logger.warning(
            "Failed to write session key %s on %s %s: %s",
            key,
            request.method,
            request.url.path,
            exc,
        )
        return False


def session_pop(request: Request, key: str, default: Any = None) -> Tuple[bool, Any]:
    try:
        return True, request.session.pop(key, default)
    except Exception as exc:
        logger.warning(
            "Failed to pop session key %s on %s %s: %s",
            key,
            request.method,
            request.url.path,
            exc,
        )
        return False, default
