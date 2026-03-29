"""bootstrap schema

Revision ID: 20260329_0001
Revises:
Create Date: 2026-03-29 01:20:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260329_0001"
down_revision = None
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr", "room", "note_room", "note_content"}


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fsqr (
            suji INT AUTO_INCREMENT PRIMARY KEY,
            time DATETIME NOT NULL,
            uuid VARCHAR(255) NOT NULL,
            id VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            secure_id VARCHAR(255) NOT NULL,
            file_type VARCHAR(20) DEFAULT 'multiple',
            original_filename VARCHAR(255) DEFAULT NULL,
            retention_days INT NOT NULL DEFAULT 7,
            UNIQUE KEY uq_fsqr_uuid (uuid),
            INDEX idx_fsqr_id_password (id, password),
            INDEX idx_fsqr_secure_id (secure_id),
            INDEX idx_fsqr_time (time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS room (
            suji INT AUTO_INCREMENT PRIMARY KEY,
            time DATETIME NOT NULL,
            id VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            room_id VARCHAR(255) NOT NULL,
            retention_days INT NOT NULL DEFAULT 7,
            UNIQUE KEY uq_room_room_id (room_id),
            INDEX idx_room_id_password (id, password),
            INDEX idx_room_room_id (room_id),
            INDEX idx_room_time (time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS note_room (
            suji INT AUTO_INCREMENT PRIMARY KEY,
            time DATETIME NOT NULL,
            id VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            room_id VARCHAR(255) NOT NULL,
            retention_days INT NOT NULL DEFAULT 7,
            UNIQUE KEY uq_note_room_room_id (room_id),
            INDEX idx_note_room_id_password (id, password),
            INDEX idx_note_room_room_id_password (room_id, password),
            INDEX idx_note_room_time (time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS note_content (
            room_id VARCHAR(255) PRIMARY KEY,
            content LONGTEXT,
            updated_at DATETIME(6),
            INDEX idx_note_content_updated_at (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    _add_column_if_missing(
        table_name="fsqr",
        column_name="file_type",
        ddl=(
            "ALTER TABLE fsqr ADD COLUMN file_type VARCHAR(20) DEFAULT 'multiple' "
            "COMMENT 'File type: single or multiple'"
        ),
    )
    _add_column_if_missing(
        table_name="fsqr",
        column_name="original_filename",
        ddl=(
            "ALTER TABLE fsqr ADD COLUMN original_filename VARCHAR(255) DEFAULT NULL "
            "COMMENT 'Original filename for single files'"
        ),
    )
    _add_column_if_missing(
        table_name="fsqr",
        column_name="retention_days",
        ddl=(
            "ALTER TABLE fsqr ADD COLUMN retention_days INT NOT NULL DEFAULT 7 "
            "COMMENT 'Number of days before automatic deletion'"
        ),
    )
    _add_column_if_missing(
        table_name="room",
        column_name="retention_days",
        ddl=(
            "ALTER TABLE room ADD COLUMN retention_days INT NOT NULL DEFAULT 7 "
            "COMMENT 'Number of days before automatic deletion'"
        ),
    )
    _add_column_if_missing(
        table_name="note_room",
        column_name="retention_days",
        ddl=(
            "ALTER TABLE note_room ADD COLUMN retention_days INT NOT NULL DEFAULT 7 "
            "COMMENT 'Number of days before automatic deletion'"
        ),
    )

    op.execute("ALTER TABLE note_content MODIFY updated_at DATETIME(6)")

    _add_index_if_missing(
        table_name="fsqr",
        index_name="idx_fsqr_id_password",
        ddl="ALTER TABLE fsqr ADD INDEX idx_fsqr_id_password (id, password)",
    )
    _add_unique_if_missing(
        table_name="fsqr",
        index_name="uq_fsqr_uuid",
        ddl="ALTER TABLE fsqr ADD UNIQUE KEY uq_fsqr_uuid (uuid)",
    )
    _add_index_if_missing(
        table_name="fsqr",
        index_name="idx_fsqr_secure_id",
        ddl="ALTER TABLE fsqr ADD INDEX idx_fsqr_secure_id (secure_id)",
    )
    _add_index_if_missing(
        table_name="fsqr",
        index_name="idx_fsqr_time",
        ddl="ALTER TABLE fsqr ADD INDEX idx_fsqr_time (time)",
    )
    _add_index_if_missing(
        table_name="room",
        index_name="idx_room_id_password",
        ddl="ALTER TABLE room ADD INDEX idx_room_id_password (id, password)",
    )
    _add_unique_if_missing(
        table_name="room",
        index_name="uq_room_room_id",
        ddl="ALTER TABLE room ADD UNIQUE KEY uq_room_room_id (room_id)",
    )
    _add_index_if_missing(
        table_name="room",
        index_name="idx_room_room_id",
        ddl="ALTER TABLE room ADD INDEX idx_room_room_id (room_id)",
    )
    _add_index_if_missing(
        table_name="room",
        index_name="idx_room_time",
        ddl="ALTER TABLE room ADD INDEX idx_room_time (time)",
    )
    _add_index_if_missing(
        table_name="note_room",
        index_name="idx_note_room_id_password",
        ddl="ALTER TABLE note_room ADD INDEX idx_note_room_id_password (id, password)",
    )
    _add_unique_if_missing(
        table_name="note_room",
        index_name="uq_note_room_room_id",
        ddl="ALTER TABLE note_room ADD UNIQUE KEY uq_note_room_room_id (room_id)",
    )
    _add_index_if_missing(
        table_name="note_room",
        index_name="idx_note_room_room_id_password",
        ddl=(
            "ALTER TABLE note_room ADD INDEX idx_note_room_room_id_password "
            "(room_id, password)"
        ),
    )
    _add_index_if_missing(
        table_name="note_room",
        index_name="idx_note_room_time",
        ddl="ALTER TABLE note_room ADD INDEX idx_note_room_time (time)",
    )
    _add_index_if_missing(
        table_name="note_content",
        index_name="idx_note_content_updated_at",
        ddl="ALTER TABLE note_content ADD INDEX idx_note_content_updated_at (updated_at)",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note_content")
    op.execute("DROP TABLE IF EXISTS note_room")
    op.execute("DROP TABLE IF EXISTS room")
    op.execute("DROP TABLE IF EXISTS fsqr")


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


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, column_name):
        return
    op.execute(ddl)


def _add_index_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _index_exists(table_name, index_name):
        return
    op.execute(ddl)


def _add_unique_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if not _table_exists(table_name):
        return
    if _unique_index_exists(table_name, index_name):
        return
    op.execute(ddl)
