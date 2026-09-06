"""共通ルーム部品をサービス横断で検証するテスト。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from Group.group_data import pich_room_id_direct as group_lookup
from i18n import current_language_ctx
from Note.note_data import pick_room_id_direct as note_lookup
from Task.task_data import pick_room_id_direct as task_lookup
from password_security import hash_password
from rate_limit import get_block_message
from room_cleanup import expired_room_ids, run_cleanup
from room_create import RoomIdConflict, select_room_id
from room_delete import delete_owned_room
from room_repository import (
    GROUP_ROOMS,
    NOTE_ROOMS,
    TASK_ROOMS,
)
from room_session import RoomSessionAccess


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    ("table", "active_fragment", "expired_fragment"),
    (
        (GROUP_ROOMS, "expires_at > NOW()", "expires_at <= NOW()"),
        (
            NOTE_ROOMS,
            "status = 'active' AND expires_at > NOW()",
            "status = 'active' AND expires_at <= NOW()",
        ),
        (
            TASK_ROOMS,
            "status = 'active' AND expires_at > NOW()",
            "status = 'active' AND expires_at <= NOW()",
        ),
    ),
)
def test_room_repository_uses_one_active_and_expired_predicate(
    table, active_fragment, expired_fragment
):
    assert active_fragment in str(table.active_select())
    assert expired_fragment in str(table.expired_ids_select())


@pytest.mark.parametrize(
    ("lookup", "table"),
    (
        (group_lookup, GROUP_ROOMS),
        (note_lookup, NOTE_ROOMS),
        (task_lookup, TASK_ROOMS),
    ),
)
def test_service_credential_lookups_share_password_verification(lookup, table):
    hashed = hash_password("123456")

    async def execute(query, params=None, fetch=False):
        assert fetch is True
        assert f"FROM {table.name}" in str(query)
        assert params == {"id": "public"}
        return [{"room_id": "abc123", "password": hashed}]

    async def scenario():
        assert await lookup("public", "123456") == "abc123"
        assert await lookup("public", "bad") is None

    # The service wrappers intentionally retain their module-local execute_query
    # patch point while the algorithm itself is shared in room_repository.
    module = lookup.__module__
    target = f"{module}.execute_query"
    from unittest.mock import patch

    with patch(target, new=execute):
        run(scenario())


@pytest.mark.parametrize(
    "namespace",
    ("group_room_access", "note_room_access", "task_room_access", "fsqr_upload_access"),
)
def test_room_session_access_preserves_legacy_namespace_and_payload(namespace):
    access = RoomSessionAccess(namespace)
    request = SimpleNamespace(session={})

    access.remember(
        request, "abc123", share_token="token", password="123456", can_delete=True
    )
    access.remember(request, "abc123", password="123456")

    assert access.has(request, "abc123")
    assert access.share_token(request, "abc123") == "token"
    assert access.password(request, "abc123") == "123456"
    assert access.can_delete(request, "abc123") is True
    access.forget(request, "abc123")
    assert not access.has(request, "abc123")


def test_select_room_id_distinguishes_manual_conflict_from_auto_retry():
    async def exists(room_id):
        return room_id == "abc123"

    async def scenario():
        with pytest.raises(RoomIdConflict):
            await select_room_id("abc123", "manual", exists)

        auto_conflict = await select_room_id("abc123", "auto", exists)
        assert auto_conflict.room_id is None
        assert auto_conflict.retry_auto is True

        selected = await select_room_id(
            "",
            "auto",
            exists,
            attempts=1,
            generator=lambda: "def456",
        )
        assert selected.room_id == "def456"

    run(scenario())


@pytest.mark.parametrize("outcome_name", ("not_found", "forbidden", "deleted"))
def test_delete_owned_room_has_one_service_independent_outcome_contract(outcome_name):
    request = SimpleNamespace(session={})
    remove = AsyncMock(return_value=True)

    def forget(req, room_id):
        req.session.pop(room_id, None)

    async def get_active(room_id):
        return None if outcome_name == "not_found" else {"room_id": room_id}

    def can_delete(req, room_id, record):
        return outcome_name != "forbidden"

    result = run(
        delete_owned_room(
            request,
            "abc123",
            get_active=get_active,
            can_delete=can_delete,
            remove=remove,
            forget=forget,
        )
    )

    assert result.status == outcome_name
    if outcome_name == "deleted":
        remove.assert_awaited_once_with("abc123")
    else:
        remove.assert_not_awaited()


def test_room_cleanup_normalizes_legacy_return_shapes_and_always_resets():
    reset = AsyncMock()
    after = AsyncMock()
    cleaner = AsyncMock(return_value={"expired_room_ids": ["abc123"]})

    result = run(run_cleanup(cleaner, after=after, reset=reset))

    assert result == {"expired_room_ids": ["abc123"]}
    after.assert_awaited_once_with(result)
    reset.assert_awaited_once()
    assert expired_room_ids(result) == ["abc123"]
    assert expired_room_ids(["def456", ""]) == ["def456"]


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    (("en", "1 day"), ("fr", "1 jour"), ("ja", "1日間")),
)
def test_rate_limit_message_uses_the_current_locale(language, expected_fragment):
    token = current_language_ctx.set(language)
    try:
        message = get_block_message("1日")
    finally:
        current_language_ctx.reset(token)

    assert expected_fragment in message
