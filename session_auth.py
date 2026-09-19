import time
from secrets import compare_digest
from typing import MutableMapping, Any

from settings import AUTH_SESSION_TIMEOUT_SECONDS

try:
    from starsessions import regenerate_session_id as _regenerate_session_id
except ImportError:  # pragma: no cover - dependency is required in production
    _regenerate_session_id = None


def _session_auth_timestamp_key(auth_key: str) -> str:
    return f"{auth_key}_authenticated_at"


def mark_session_authenticated(
    session: MutableMapping[str, Any], auth_key: str
) -> None:
    session[auth_key] = True
    session[_session_auth_timestamp_key(auth_key)] = int(time.time())


def rotate_session_id(connection: Any) -> None:
    """Rotate the server-side session identifier after privilege elevation."""

    if _regenerate_session_id is not None:
        _regenerate_session_id(connection)


def clear_session_authenticated(
    session: MutableMapping[str, Any], auth_key: str
) -> None:
    session.pop(auth_key, None)
    session.pop(_session_auth_timestamp_key(auth_key), None)


def is_session_authenticated(session: MutableMapping[str, Any], auth_key: str) -> bool:
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


def secure_compare_secret(provided: object, expected: object) -> bool:
    """Compare configured login secrets without content-dependent timing."""
    provided_text = provided if isinstance(provided, str) else ""
    expected_text = expected if isinstance(expected, str) else ""
    # An unset secret must never authenticate an empty form value.  This also
    # protects deployments where an environment variable was omitted.
    if not provided_text or not expected_text:
        return False
    return compare_digest(provided_text, expected_text)
