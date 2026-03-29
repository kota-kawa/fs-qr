"""add unique constraints for business keys

Revision ID: 20260329_0002
Revises: 20260329_0001
Create Date: 2026-03-29 02:35:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260329_0002"
down_revision = "20260329_0001"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr", "room", "note_room"}


def upgrade() -> None:
    _add_unique_if_missing(
        table_name="fsqr",
        index_name="uq_fsqr_uuid",
        ddl="ALTER TABLE fsqr ADD UNIQUE KEY uq_fsqr_uuid (uuid)",
    )
    _add_unique_if_missing(
        table_name="room",
        index_name="uq_room_room_id",
        ddl="ALTER TABLE room ADD UNIQUE KEY uq_room_room_id (room_id)",
    )
    _add_unique_if_missing(
        table_name="note_room",
        index_name="uq_note_room_room_id",
        ddl="ALTER TABLE note_room ADD UNIQUE KEY uq_note_room_room_id (room_id)",
    )


def downgrade() -> None:
    _drop_index_if_exists(table_name="note_room", index_name="uq_note_room_room_id")
    _drop_index_if_exists(table_name="room", index_name="uq_room_room_id")
    _drop_index_if_exists(table_name="fsqr", index_name="uq_fsqr_uuid")


def _table_exists(table_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = f"""
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}'
    """
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _unique_index_exists(table_name: str, index_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = f"""
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}'
          AND INDEX_NAME = '{index_name}'
          AND NON_UNIQUE = 0
    """
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _add_unique_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _unique_index_exists(table_name, index_name):
        return
    op.execute(ddl)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _unique_index_exists(table_name, index_name):
        return
    op.execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")
