"""database.execute_query の再試行境界を検証する。"""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError


def _load_database_module():
    module_path = Path(__file__).parents[1] / "database.py"
    spec = importlib.util.spec_from_file_location(
        "database_retry_behavior", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine"),
        patch("sqlalchemy.ext.asyncio.async_sessionmaker"),
        patch("sqlalchemy.ext.asyncio.async_scoped_session"),
    ):
        spec.loader.exec_module(module)
    return module


def _connection_error():
    return OperationalError("SELECT 1", {}, Exception("lost connection"))


def test_fresh_schema_contains_columns_used_by_cleanup_queries():
    schema = (Path(__file__).parents[1] / "db_init/create_tables.sql").read_text(
        encoding="utf-8"
    )

    room_schema = schema.split("CREATE TABLE room", 1)[1].split(
        "CREATE TABLE note_room", 1
    )[0]
    room_status = room_schema.index("status VARCHAR(20) NOT NULL DEFAULT 'active'")
    room_status_index = room_schema.index("idx_room_expires_status")
    assert room_status < room_status_index
    assert "deleted_at DATETIME NULL" in schema
    assert "encryption_mode VARCHAR(20) NOT NULL DEFAULT 'password'" in schema


def test_existing_fsqr_migration_adds_deletion_and_encryption_columns():
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/20260919_0015_fsqr_encryption_mode.py"
    ).read_text(encoding="utf-8")

    assert '"status"' in migration
    assert '"deleted_at"' in migration
    assert '"encryption_mode"' in migration


@pytest.mark.asyncio
async def test_execute_query_does_not_retry_dml_after_connection_loss():
    database = _load_database_module()
    session = MagicMock()
    session.execute = AsyncMock(side_effect=_connection_error())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.remove = AsyncMock()
    database.db_session = session

    with pytest.raises(OperationalError):
        await database.execute_query("DELETE FROM task_item WHERE item_id = :id")

    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_query_retries_read_only_fetches():
    database = _load_database_module()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [{"value": 1}]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[_connection_error(), result])
    session.rollback = AsyncMock()
    database.db_session = session

    assert await database.execute_query("SELECT 1", fetch=True) == [{"value": 1}]
    assert session.execute.await_count == 2
    # One rollback clears the failed connection before retry; the successful
    # read is rolled back as well to end its transaction cleanly.
    assert session.rollback.await_count == 2
