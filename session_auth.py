import time
from typing import MutableMapping, Any

from settings import AUTH_SESSION_TIMEOUT_SECONDS


def _session_auth_timestamp_key(auth_key: str) -> str:
    return f"{auth_key}_authenticated_at"


def mark_session_authenticated(
    session: MutableMapping[str, Any], auth_key: str
) -> None:
    session[auth_key] = True
    session[_session_auth_timestamp_key(auth_key)] = int(time.time())


def clear_session_authenticated(
    session: MutableMapping[str, Any], auth_key: str
) -> None:
    session.pop(auth_key, None)
    session.pop(_session_auth_timestamp_key(auth_key), None)


def is_session_authenticated(
    session: MutableMapping[str, Any], auth_key: str
) -> bool:
    if not session.get(auth_key):
        return False

    authenticated_at = session.get(_session_auth_timestamp_key(auth_key))
    if not isinstance(authenticated_at, (int, float)):
        clear_session_authenticated(session, auth_key)
        return False

    if time.time() - float(authenticated_at) > AUTH_SESSION_TIMEOUT_SECONDS:
        clear_session_authenticated(session, auth_key)
        return False

    return True
