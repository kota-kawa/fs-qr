"""即時作成と作成者向けの期限変更に関する回帰テスト。"""

import asyncio
import re
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from conftest import MockSessionMiddleware
from models import GroupRoomCreateInput, RoomRetentionInput
from room_repository import (
    GROUP_ROOMS,
    NOTE_ROOMS,
    TASK_ROOMS,
    update_room_retention,
)
from room_settings import room_retention_options


@pytest.mark.parametrize("value", [0, -1, 25, 721, 1440, None, True, 24.5, [], "24.0"])
def test_invalid_retention_is_rejected_without_defaulting(value):
    with pytest.raises(ValidationError):
        RoomRetentionInput(retention_hours=value)


def test_group_creation_supports_thirty_days_without_changing_the_default():
    assert GroupRoomCreateInput().retention_hours == 24
    assert GroupRoomCreateInput(retention_hours=720).retention_hours == 720
    assert GroupRoomCreateInput(retention_hours=721).retention_hours == 24


def test_settings_options_are_anchored_to_creation_and_exclude_elapsed_dates():
    created = datetime.now() - timedelta(days=2)
    options = room_retention_options({"time": created})
    assert [option["hours"] for option in options] == [168, 720]
    assert options[-1]["deletion_date"] == (created + timedelta(days=30)).strftime(
        "%Y-%m-%d %H:%M"
    )


@pytest.mark.parametrize(
    ("service", "table"),
    [("group", GROUP_ROOMS), ("note", NOTE_ROOMS), ("task", TASK_ROOMS)],
)
@pytest.mark.parametrize("hours", [1, 24, 168, 720])
def test_room_and_share_links_are_updated_in_one_transaction(service, table, hours):
    session = MagicMock()
    created = datetime.now()
    record = {"expires_at": created + timedelta(hours=hours)}
    selected = MagicMock()
    selected.mappings.return_value.one.return_value = record
    session.execute = AsyncMock(
        side_effect=[MagicMock(rowcount=1), selected, MagicMock()]
    )
    result = asyncio.run(
        update_room_retention(session, table, service, "abc123", hours)
    )
    assert result == record
    calls = session.execute.await_args_list
    query, params = calls[0].args
    sql = str(query)
    assert f"UPDATE {table.name}" in sql
    assert "status = 'active' AND expires_at > NOW()" in sql
    assert "DATE_ADD(time, INTERVAL :retention_hours HOUR) > NOW()" in sql
    assert ":retention_hours <= :max_retention_hours" in sql
    assert params["max_retention_hours"] == 720
    assert params["retention_hours"] == hours
    link_query, link_params = calls[2].args
    assert "UPDATE share_links" in str(link_query)
    assert "revoked_at IS NULL" in str(link_query)
    assert link_params["expires_at"] == record["expires_at"]
    assert link_params["service_key"] == service
    session.begin.return_value.__aenter__.assert_awaited_once()
    session.begin.return_value.__aexit__.assert_awaited_once_with(None, None, None)


def test_expired_deleted_or_elapsed_updates_never_touch_share_links():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    assert (
        asyncio.run(update_room_retention(session, GROUP_ROOMS, "group", "abc123", 720))
        is None
    )
    assert session.execute.await_count == 1


def test_share_link_failure_rolls_back_the_room_update():
    session = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.one.return_value = {"expires_at": datetime.now()}
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(rowcount=1),
            selected,
            RuntimeError("link update failed"),
        ]
    )
    with pytest.raises(RuntimeError, match="link update failed"):
        asyncio.run(update_room_retention(session, NOTE_ROOMS, "note", "abc123", 168))
    assert session.begin.return_value.__aexit__.await_args.args[0] is RuntimeError


def _set_access(client, service, owner):
    client.get(f"/{service}")
    session_id = client.cookies.get(MockSessionMiddleware._cookie_name)
    session = MockSessionMiddleware._sessions[session_id]
    session[f"{service}_room_access"] = {"abc123": {"can_delete": "1"} if owner else {}}


@pytest.mark.parametrize("service", ["group", "note", "task"])
@pytest.mark.parametrize(
    ("case", "expected"),
    [("owner", 200), ("participant", 403), ("invalid", 400), ("expired", 409)],
)
def test_settings_requires_owner_valid_period_and_active_room(
    test_client, service, case, expected
):
    _set_access(test_client, service, case != "participant")
    update = AsyncMock(
        return_value=None
        if case == "expired"
        else {"expires_at": datetime.now() + timedelta(days=30)}
    )
    with patch(f"{service.title()}.{service}_data.update_room_retention", update):
        response = test_client.post(
            f"/{service}/r/abc123/settings",
            json={"retention_hours": 721 if case == "invalid" else 720},
            headers={"Accept": "application/json"},
        )
    assert response.status_code == expected
    if case in ("owner", "expired"):
        update.assert_awaited_once_with("abc123", 720)
    else:
        update.assert_not_awaited()


@pytest.mark.parametrize("service", ["group", "note", "task"])
def test_settings_form_works_without_javascript_and_requires_csrf(test_client, service):
    _set_access(test_client, service, True)
    update = AsyncMock(return_value={"expires_at": datetime.now() + timedelta(days=7)})
    with patch(f"{service.title()}.{service}_data.update_room_retention", update):
        rejected = test_client.post(
            f"/{service}/r/abc123/settings",
            data={"retention_hours": "168"},
            headers={"X-CSRF-Token": "invalid"},
        )
        update.assert_not_awaited()
        accepted = test_client.post(
            f"/{service}/r/abc123/settings", data={"retention_hours": "168"}
        )
    assert rejected.status_code == 403
    assert accepted.status_code == 303
    assert accepted.headers["location"] == f"/{service}/r/abc123"


@pytest.mark.parametrize("service", ["group", "note", "task"])
def test_settings_respects_rate_limit_and_reports_update_failure(test_client, service):
    _set_access(test_client, service, True)
    update = AsyncMock(side_effect=RuntimeError("update failed"))
    with (
        patch(f"{service.title()}.{service}_data.update_room_retention", update),
        patch(
            "room_settings.check_rate_limit", AsyncMock(return_value=(False, None, ""))
        ),
    ):
        response = test_client.post(
            f"/{service}/r/abc123/settings", json={"retention_hours": 720}
        )
    assert response.status_code == 429
    update.assert_not_awaited()
    with patch(f"{service.title()}.{service}_data.update_room_retention", update):
        response = test_client.post(
            f"/{service}/r/abc123/settings", json={"retention_hours": 720}
        )
    assert response.status_code == 500


@pytest.mark.parametrize("service", ["group", "note", "task"])
def test_one_click_creation_uses_auto_id_and_default_period(test_client, service):
    module = {
        "group": "Group.group_routes_room",
        "note": "Note.note_app",
        "task": "Task.task_routes_room",
    }[service]
    create = AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(patch(f"{module}._generate_room_id", return_value="abc123"))
        stack.enter_context(
            patch(f"{service.title()}.{service}_data.create_room", create)
        )
        stack.enter_context(
            patch(f"{module}.create_share_link", AsyncMock(return_value="test-token"))
        )
        if service == "note":
            stack.enter_context(
                patch(f"{module}._room_id_exists", AsyncMock(return_value=False))
            )
            stack.enter_context(
                patch(
                    f"{module}._get_room_if_valid",
                    AsyncMock(
                        return_value={"expires_at": datetime.now() + timedelta(days=1)}
                    ),
                )
            )
        elif service == "group":
            stack.enter_context(
                patch(f"{module}._group_room_exists", AsyncMock(return_value=False))
            )
            stack.enter_context(patch(f"{module}.os.makedirs"))
        response = test_client.post(f"/create_{service}_room", data={})
    assert response.status_code == 302
    assert response.headers["location"] == f"/{service}/r/abc123"
    args, kwargs = create.await_args
    if service == "task":
        assert args[0] == "abc123"
        assert args[3] == 24
    else:
        assert kwargs["retention_hours"] == 24
        assert (kwargs.get("room_id") or args[0]) == "abc123"


@pytest.mark.parametrize("service", ["group", "note", "task"])
def test_entry_has_immediate_creation_without_id_or_expiry_fields(test_client, service):
    response = test_client.get(f"/{service}?lang=en")
    match = re.search(r"<form[^>]+data-room-create\b.*?</form>", response.text, re.S)
    assert match
    form = match.group()
    assert f'action="/create_{service}_room"' in form
    assert not re.search(r'name="(?:id|idMode|retention_hours)"', form)
    assert "24 hours" in form


@pytest.mark.parametrize("service", ["group", "note", "task"])
@pytest.mark.parametrize("owner", [True, False])
def test_room_only_shows_localized_settings_to_its_creator(test_client, service, owner):
    _set_access(test_client, service, owner)
    created = datetime.now()
    record = {
        "id": "abc123",
        "time": created,
        "expires_at": created + timedelta(hours=24),
        "retention_hours": 24,
    }
    lookup = {
        "group": "Group.group_routes_room.get_room_if_active",
        "note": "Note.note_app._get_room_if_valid",
        "task": "Task.task_routes_room.get_room_if_active",
    }[service]
    with (
        patch(lookup, AsyncMock(return_value=record)),
        patch("Note.note_data.get_row", AsyncMock(return_value={"content": "draft"})),
    ):
        response = test_client.get(f"/{service}/r/abc123?lang=en")
    assert response.status_code == 200
    if owner:
        settings = re.search(
            r'<details class="room-settings">.*?</details>', response.text, re.S
        ).group()
        assert "30 days" in settings
        assert 'value="720"' in settings
        assert not re.search(r"[ぁ-ゖァ-ヺ]", settings)
    else:
        assert "data-room-settings" not in response.text


@pytest.mark.parametrize("service", ["group", "note", "task"])
def test_retention_updates_invalidate_service_caches(service):
    from importlib import import_module

    module = import_module(f"{service.title()}.{service}_data")
    record = {"expires_at": datetime.now() + timedelta(days=30)}
    with (
        patch.object(module, "update_retention", AsyncMock(return_value=record)),
        patch.object(module, "invalidate_cache_prefix", AsyncMock()) as prefix,
        patch.object(
            module, "invalidate_cache_entry", AsyncMock(), create=True
        ) as entry,
    ):
        result = asyncio.run(module.update_room_retention("abc123", 720))
    assert result == record
    assert prefix.await_count >= 1
    if service == "group":
        assert entry.await_count == 2
