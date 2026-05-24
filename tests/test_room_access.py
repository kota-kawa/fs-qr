"""Unit tests for the shared session-scoped access store (room_access)."""

import room_access

NS = "ns"


def test_grant_then_has_and_get():
    session: dict = {}
    room_access.grant_access(session, NS, "room1", payload={"share_token": "tok"})

    assert room_access.has_access(session, NS, "room1") is True
    assert room_access.get_access(session, NS, "room1") == {"share_token": "tok"}
    assert room_access.get_access_field(session, NS, "room1", "share_token") == "tok"


def test_has_access_false_for_unknown_key_and_namespace():
    session: dict = {}
    assert room_access.has_access(session, NS, "missing") is False
    room_access.grant_access(session, NS, "room1")
    assert room_access.has_access(session, NS, "room2") is False
    assert room_access.has_access(session, "other_ns", "room1") is False


def test_grant_without_payload_creates_empty_entry():
    session: dict = {}
    room_access.grant_access(session, NS, "room1")
    assert room_access.has_access(session, NS, "room1") is True
    assert room_access.get_access(session, NS, "room1") == {}
    assert room_access.get_access_field(session, NS, "room1", "share_token") == ""


def test_payload_values_coerced_to_str_and_none_becomes_empty():
    session: dict = {}
    room_access.grant_access(session, NS, "room1", payload={"n": 123, "blank": None})
    entry = room_access.get_access(session, NS, "room1")
    assert entry == {"n": "123", "blank": ""}


def test_regrant_merges_payload():
    session: dict = {}
    room_access.grant_access(session, NS, "room1", payload={"a": "1"})
    room_access.grant_access(session, NS, "room1", payload={"b": "2"})
    assert room_access.get_access(session, NS, "room1") == {"a": "1", "b": "2"}


def test_key_is_coerced_to_str():
    session: dict = {}
    room_access.grant_access(session, NS, 42)  # type: ignore[arg-type]
    assert room_access.has_access(session, NS, "42") is True
    assert room_access.has_access(session, NS, 42) is True  # type: ignore[arg-type]


def test_cap_keeps_only_most_recent_entries():
    session: dict = {}
    for i in range(25):
        room_access.grant_access(session, NS, f"room{i}", max_entries=20)

    stored = session[NS]
    assert len(stored) == 20
    # Oldest five evicted, newest retained.
    assert "room4" not in stored
    assert "room5" in stored
    assert "room24" in stored


def test_regrant_bumps_recency_and_survives_trim():
    session: dict = {}
    for i in range(20):
        room_access.grant_access(session, NS, f"room{i}", max_entries=20)
    # Re-grant the oldest key: it should now be most-recently-used.
    room_access.grant_access(session, NS, "room0", max_entries=20)
    # Push one more new key, forcing a single eviction.
    room_access.grant_access(session, NS, "roomNew", max_entries=20)

    stored = session[NS]
    assert len(stored) == 20
    assert "room0" in stored  # bumped, so retained
    assert "room1" not in stored  # became the oldest, evicted


def test_legacy_string_value_still_counts_as_access():
    # Previous Group format stored a bare password string per room.
    session = {NS: {"room1": "654321"}}
    assert room_access.has_access(session, NS, "room1") is True
    # No structured payload available for a legacy value.
    assert room_access.get_access(session, NS, "room1") is None
    assert room_access.get_access_field(session, NS, "room1", "x", "def") == "def"


def test_legacy_value_upgraded_on_regrant():
    session = {NS: {"room1": "654321"}}
    room_access.grant_access(session, NS, "room1", payload={"share_token": "t"})
    assert room_access.get_access(session, NS, "room1") == {"share_token": "t"}


def test_malformed_namespace_is_tolerated():
    session = {NS: "not-a-dict"}
    assert room_access.has_access(session, NS, "room1") is False
    assert room_access.get_access(session, NS, "room1") is None
    # Granting recovers a clean dict namespace.
    room_access.grant_access(session, NS, "room1")
    assert room_access.has_access(session, NS, "room1") is True


def test_get_access_field_default_when_field_missing_or_non_str():
    session: dict = {}
    room_access.grant_access(session, NS, "room1", payload={"a": "1"})
    assert room_access.get_access_field(session, NS, "room1", "missing", "d") == "d"


def test_revoke_access():
    session: dict = {}
    room_access.grant_access(session, NS, "room1")
    room_access.grant_access(session, NS, "room2")
    room_access.revoke_access(session, NS, "room1")
    assert room_access.has_access(session, NS, "room1") is False
    assert room_access.has_access(session, NS, "room2") is True
    # Revoking an unknown key is a no-op.
    room_access.revoke_access(session, NS, "room1")
    room_access.revoke_access(session, "missing_ns", "room2")


def test_get_access_returns_copy_not_reference():
    session: dict = {}
    room_access.grant_access(session, NS, "room1", payload={"a": "1"})
    entry = room_access.get_access(session, NS, "room1")
    assert entry is not None
    entry["a"] = "mutated"
    assert room_access.get_access(session, NS, "room1") == {"a": "1"}
