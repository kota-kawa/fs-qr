"""Session-scoped resource access tracking shared by FSQR / Note / Group.

A single hardened implementation of "remember that this browser session was
granted access to a room / resource". Each service supplies its own session
namespace and resource key (``room_id`` for Note and Group, ``secure_id`` for
FSQR) and optionally an auxiliary payload (e.g. a share token).

Stored shape, per namespace::

    session[namespace] = { "<key>": {<payload fields>}, ... }

Design notes:

* The store is capped at ``DEFAULT_MAX_ENTRIES`` most-recently-used entries so a
  long-lived session that touches many rooms cannot grow without bound.
* Every read is defensive against malformed or legacy session data. Older
  sessions that stored a bare string value per key (the previous Group format)
  are still treated as "access granted" so a deploy does not log users out.
* Re-granting an existing key bumps it to most-recently-used.

This module only records *that* access was granted; it never decides whether it
*should* be. Callers remain responsible for verifying credentials before
calling :func:`grant_access`, and for re-validating against the database when a
request must reflect live room state.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

DEFAULT_MAX_ENTRIES = 20


def _entries(session: Mapping[str, Any], namespace: str) -> dict[str, Any]:
    """Return the namespace's entry map, or an empty dict if absent/malformed."""
    raw = session.get(namespace)
    return raw if isinstance(raw, dict) else {}


def grant_access(
    session: MutableMapping[str, Any],
    namespace: str,
    key: str,
    *,
    payload: Optional[Mapping[str, Any]] = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Record that ``session`` has been granted access to ``key``.

    Any ``payload`` fields are merged into the entry (values are coerced to
    ``str``; ``None`` becomes ``""``). The key is moved to most-recently-used
    and the namespace is trimmed to ``max_entries`` entries.
    """
    entries = dict(_entries(session, namespace))
    key = str(key)

    existing = entries.pop(key, None)  # pop so re-grant bumps recency
    entry = dict(existing) if isinstance(existing, dict) else {}
    if payload:
        entry.update({k: ("" if v is None else str(v)) for k, v in payload.items()})
    entries[key] = entry

    if len(entries) > max_entries:
        entries = dict(list(entries.items())[-max_entries:])

    session[namespace] = entries


def has_access(session: Mapping[str, Any], namespace: str, key: str) -> bool:
    """Return whether ``session`` has been granted access to ``key``."""
    return str(key) in _entries(session, namespace)


def get_access(
    session: Mapping[str, Any], namespace: str, key: str
) -> Optional[dict[str, Any]]:
    """Return a copy of the stored payload for ``key``, or ``None``.

    Returns ``None`` when access was not granted or the entry is a legacy
    non-dict value (in which case there is no structured payload to read).
    """
    entry = _entries(session, namespace).get(str(key))
    return dict(entry) if isinstance(entry, dict) else None


def get_access_field(
    session: Mapping[str, Any],
    namespace: str,
    key: str,
    field: str,
    default: str = "",
) -> str:
    """Return a single string field from ``key``'s payload, or ``default``."""
    entry = get_access(session, namespace, key)
    if not entry:
        return default
    value = entry.get(field, default)
    return value if isinstance(value, str) else default


def revoke_access(session: MutableMapping[str, Any], namespace: str, key: str) -> None:
    """Forget any access previously granted to ``key`` (no-op if absent)."""
    entries = _entries(session, namespace)
    if str(key) in entries:
        entries = dict(entries)
        entries.pop(str(key), None)
        session[namespace] = entries
