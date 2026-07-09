"""add scalable search lookup columns

Revision ID: 20260710_0008
Revises: 20260611_0007
Create Date: 2026-07-10 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260710_0008"
down_revision = "20260611_0007"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr", "room"}


def upgrade() -> None:
    if _table_exists("fsqr"):
        _add_column_if_missing(
            "fsqr",
            "password_lookup_hash",
            "ALTER TABLE fsqr ADD COLUMN password_lookup_hash VARCHAR(64) NULL",
        )
        _add_column_if_missing(
            "fsqr",
            "expires_at",
            "ALTER TABLE fsqr ADD COLUMN expires_at DATETIME NULL",
        )
        op.execute("""
            UPDATE fsqr
            SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY)
            WHERE expires_at IS NULL
            """)
        op.execute("ALTER TABLE fsqr MODIFY expires_at DATETIME NOT NULL")
        _add_index_if_missing(
            "fsqr",
            "idx_fsqr_id_password_lookup",
            "ALTER TABLE fsqr ADD INDEX idx_fsqr_id_password_lookup (id, password_lookup_hash)",
        )
        _add_index_if_missing(
            "fsqr",
            "idx_fsqr_expires_at",
            "ALTER TABLE fsqr ADD INDEX idx_fsqr_expires_at (expires_at)",
        )

    if _table_exists("room"):
        _add_column_if_missing(
            "room",
            "expires_at",
            "ALTER TABLE room ADD COLUMN expires_at DATETIME NULL",
        )
        op.execute("""
            UPDATE room
            SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY)
            WHERE expires_at IS NULL
            """)
        op.execute("ALTER TABLE room MODIFY expires_at DATETIME NOT NULL")
        _add_index_if_missing(
            "room",
            "idx_room_expires_at",
            "ALTER TABLE room ADD INDEX idx_room_expires_at (expires_at)",
        )


def downgrade() -> None:
    _drop_index_if_exists("room", "idx_room_expires_at")
    _drop_column_if_exists("room", "expires_at")
    _drop_index_if_exists("fsqr", "idx_fsqr_expires_at")
    _drop_index_if_exists("fsqr", "idx_fsqr_id_password_lookup")
    _drop_column_if_exists("fsqr", "expires_at")
    _drop_column_if_exists("fsqr", "password_lookup_hash")


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


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, column_name):
        return
    op.execute(ddl)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, column_name):
        return
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")


def _add_index_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _index_exists(table_name, index_name):
        return
    op.execute(ddl)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _index_exists(table_name, index_name):
        return
    op.execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")
