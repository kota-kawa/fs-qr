"""keep deleted Group room IDs as tombstones

Revision ID: 20260919_0014
Revises: 20260821_0013
Create Date: 2026-09-19 00:00:00

Group sessions identify a room by its public room ID.  Retaining a deleted row
prevents an old session from becoming authorized for a later room that reuses
the same ID.
"""

from alembic import op


revision = "20260919_0014"
down_revision = "20260821_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _table_exists("room"):
        return
    if not _column_exists("room", "status"):
        op.execute(
            "ALTER TABLE room ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
        )
    if not _column_exists("room", "deleted_at"):
        op.execute("ALTER TABLE room ADD COLUMN deleted_at DATETIME NULL")
    if not _index_exists("room", "idx_room_expires_status"):
        op.execute(
            "ALTER TABLE room ADD INDEX idx_room_expires_status (status, expires_at)"
        )


def downgrade() -> None:
    if not _table_exists("room"):
        return
    if _index_exists("room", "idx_room_expires_status"):
        op.execute("ALTER TABLE room DROP INDEX idx_room_expires_status")
    if _column_exists("room", "deleted_at"):
        op.execute("ALTER TABLE room DROP COLUMN deleted_at")
    if _column_exists("room", "status"):
        op.execute("ALTER TABLE room DROP COLUMN status")


def _table_exists(table_name: str) -> bool:
    if table_name != "room":
        raise ValueError("Unsupported table")
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'room'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _column_exists(table_name: str, column_name: str) -> bool:
    if table_name != "room" or column_name not in {"status", "deleted_at"}:
        raise ValueError("Unsupported column")
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'room' "
        f"AND COLUMN_NAME = '{column_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _index_exists(table_name: str, index_name: str) -> bool:
    if table_name != "room" or index_name != "idx_room_expires_status":
        raise ValueError("Unsupported index")
    query = (
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'room' "
        f"AND INDEX_NAME = '{index_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
