"""tokenized note rooms with versioned content

Revision ID: 20260524_0005
Revises: 20260522_0004
Create Date: 2026-05-24 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260524_0005"
down_revision = "20260522_0004"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"note_room", "note_content"}


def upgrade() -> None:
    _add_column_if_missing(
        "note_room",
        "expires_at",
        "ALTER TABLE note_room ADD COLUMN expires_at DATETIME NULL",
    )
    op.execute(
        "UPDATE note_room SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY) "
        "WHERE expires_at IS NULL"
    )
    op.execute("ALTER TABLE note_room MODIFY expires_at DATETIME NOT NULL")
    _add_column_if_missing(
        "note_room",
        "status",
        "ALTER TABLE note_room ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'",
    )
    _add_column_if_missing(
        "note_room",
        "deleted_at",
        "ALTER TABLE note_room ADD COLUMN deleted_at DATETIME NULL",
    )
    _add_column_if_missing(
        "note_room",
        "share_token_hash",
        "ALTER TABLE note_room ADD COLUMN share_token_hash VARCHAR(64) DEFAULT NULL",
    )
    _add_column_if_missing(
        "note_content",
        "version",
        "ALTER TABLE note_content ADD COLUMN version BIGINT NOT NULL DEFAULT 0",
    )

    _add_unique_if_missing(
        "note_room",
        "uq_note_room_share_token_hash",
        "ALTER TABLE note_room ADD UNIQUE KEY uq_note_room_share_token_hash (share_token_hash)",
    )
    _add_index_if_missing(
        "note_room",
        "idx_note_room_expires_status",
        "ALTER TABLE note_room ADD INDEX idx_note_room_expires_status (status, expires_at)",
    )

    op.execute(
        "DELETE nc FROM note_content nc "
        "LEFT JOIN note_room nr ON nr.room_id = nc.room_id "
        "WHERE nr.room_id IS NULL"
    )
    _add_foreign_key_if_missing(
        "fk_note_content_room_id",
        "ALTER TABLE note_content ADD CONSTRAINT fk_note_content_room_id "
        "FOREIGN KEY (room_id) REFERENCES note_room(room_id) ON DELETE CASCADE",
    )


def downgrade() -> None:
    _drop_foreign_key_if_exists("fk_note_content_room_id")
    _drop_index_if_exists("note_room", "idx_note_room_expires_status")
    _drop_index_if_exists("note_room", "uq_note_room_share_token_hash")
    _drop_column_if_exists("note_content", "version")
    _drop_column_if_exists("note_room", "share_token_hash")
    _drop_column_if_exists("note_room", "deleted_at")
    _drop_column_if_exists("note_room", "status")
    _drop_column_if_exists("note_room", "expires_at")


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


def _column_exists(table_name: str, column_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = f"""
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}'
          AND COLUMN_NAME = '{column_name}'
    """
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _index_exists(table_name: str, index_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = f"""
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}'
          AND INDEX_NAME = '{index_name}'
    """
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _foreign_key_exists(name: str) -> bool:
    query = f"""
        SELECT COUNT(*)
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
          AND CONSTRAINT_NAME = '{name}'
          AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    """
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    if _table_exists(table_name) and not _column_exists(table_name, column_name):
        op.execute(ddl)


def _add_unique_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if _table_exists(table_name) and not _index_exists(table_name, index_name):
        op.execute(ddl)


def _add_index_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if _table_exists(table_name) and not _index_exists(table_name, index_name):
        op.execute(ddl)


def _add_foreign_key_if_missing(name: str, ddl: str) -> None:
    if (
        _table_exists("note_content")
        and _table_exists("note_room")
        and not _foreign_key_exists(name)
    ):
        op.execute(ddl)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _table_exists(table_name) and _index_exists(table_name, index_name):
        op.execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")


def _drop_foreign_key_if_exists(name: str) -> None:
    if _table_exists("note_content") and _foreign_key_exists(name):
        op.execute(f"ALTER TABLE note_content DROP FOREIGN KEY {name}")


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _table_exists(table_name) and _column_exists(table_name, column_name):
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
