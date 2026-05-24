import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from Note import note_data


class AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_remove_room_revokes_shared_links_and_invalidates_cache():
    execute_mock = AsyncMock()
    revoke_mock = AsyncMock()
    invalidate_entry_mock = AsyncMock()
    invalidate_prefix_mock = AsyncMock()

    with (
        patch("Note.note_data.execute_query", execute_mock),
        patch("share_links.revoke_resource_links", revoke_mock),
        patch("Note.note_data.invalidate_cache_entry", invalidate_entry_mock),
        patch("Note.note_data.invalidate_cache_prefix", invalidate_prefix_mock),
    ):
        asyncio.run(note_data.remove_room("abc123"))

    assert execute_mock.await_count == 2
    revoke_mock.assert_awaited_once()
    assert revoke_mock.await_args.kwargs["resource_id"] == "abc123"
    invalidate_entry_mock.assert_awaited_once()
    assert invalidate_prefix_mock.await_count == 2


def test_remove_room_keeps_cleanup_going_when_revoke_fails():
    with (
        patch("Note.note_data.execute_query", AsyncMock()),
        patch(
            "share_links.revoke_resource_links",
            AsyncMock(side_effect=RuntimeError("revoke failed")),
        ),
        patch("Note.note_data.invalidate_cache_entry", AsyncMock()) as entry_mock,
        patch("Note.note_data.invalidate_cache_prefix", AsyncMock()) as prefix_mock,
    ):
        asyncio.run(note_data.remove_room("abc123", status="expired"))

    entry_mock.assert_awaited_once()
    assert prefix_mock.await_count == 2


def test_remove_expired_rooms_revokes_links_and_returns_removed_ids():
    db_session = MagicMock()
    db_session.begin.return_value = AsyncContext()
    db_session.execute = AsyncMock()
    revoke_mock = AsyncMock()

    with (
        patch(
            "Note.note_data.execute_query",
            AsyncMock(return_value=[{"room_id": "room1"}, {"room_id": "room2"}]),
        ),
        patch("Note.note_data.db_session", db_session),
        patch("share_links.revoke_resource_links", revoke_mock),
        patch("Note.note_data.invalidate_cache_entry", AsyncMock()) as entry_mock,
        patch("Note.note_data.invalidate_cache_prefix", AsyncMock()) as prefix_mock,
    ):
        result = asyncio.run(note_data.remove_expired_rooms())

    assert result == {"expired_count": 2, "expired_room_ids": ["room1", "room2"]}
    assert db_session.execute.await_count == 4
    assert revoke_mock.await_count == 2
    assert entry_mock.await_count == 2
    assert prefix_mock.await_count == 2


def test_remove_expired_rooms_returns_error_payload_on_failure():
    with patch(
        "Note.note_data.execute_query",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    ):
        result = asyncio.run(note_data.remove_expired_rooms())

    assert result["expired_count"] == 0
    assert result["expired_room_ids"] == []
    assert "database unavailable" in result["error"]


def test_get_room_meta_by_share_token_hash_returns_row_or_none():
    row = {"room_id": "abc123", "id": "abc123"}
    execute_mock = AsyncMock(return_value=[row])

    with patch("Note.note_data.execute_query", execute_mock):
        result = asyncio.run(note_data.get_room_meta_by_share_token_hash("hash-value"))

    assert result == row
    assert execute_mock.await_args.args[1] == {"h": "hash-value"}

    with patch("Note.note_data.execute_query", AsyncMock(return_value=[])):
        assert (
            asyncio.run(note_data.get_room_meta_by_share_token_hash("missing-hash"))
            is None
        )


def test_remove_expired_rooms_continues_when_revoke_fails():
    db_session = MagicMock()
    db_session.begin.return_value = AsyncContext()
    db_session.execute = AsyncMock()

    with (
        patch(
            "Note.note_data.execute_query",
            AsyncMock(return_value=[{"room_id": "room1"}]),
        ),
        patch("Note.note_data.db_session", db_session),
        patch(
            "share_links.revoke_resource_links",
            AsyncMock(side_effect=RuntimeError("revoke failed")),
        ),
        patch("Note.note_data.invalidate_cache_entry", AsyncMock()),
        patch("Note.note_data.invalidate_cache_prefix", AsyncMock()),
    ):
        result = asyncio.run(note_data.remove_expired_rooms())

    assert result == {"expired_count": 1, "expired_room_ids": ["room1"]}
