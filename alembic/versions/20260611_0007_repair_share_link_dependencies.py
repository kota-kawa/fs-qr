"""repair share link dependencies

Revision ID: 20260611_0007
Revises: 20260524_0006
Create Date: 2026-06-11 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260611_0007"
down_revision = "20260524_0006"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr", "room", "share_links"}


def upgrade() -> None:
    _ensure_fsqr_upload_columns()
    _ensure_group_room_columns()
    _ensure_share_links_table()


def downgrade() -> None:
    # This revision is a production repair migration. Dropping repaired columns
    # or the shared link table would break existing share URLs.
    pass


def _ensure_fsqr_upload_columns() -> None:
    _add_column_if_missing(
        "fsqr",
        "share_token_hash",
        "ALTER TABLE fsqr ADD COLUMN share_token_hash VARCHAR(64) DEFAULT NULL",
    )
    _add_column_if_missing(
        "fsqr",
        "file_type",
        "ALTER TABLE fsqr ADD COLUMN file_type VARCHAR(20) DEFAULT 'multiple'",
    )
    _add_column_if_missing(
        "fsqr",
        "original_filename",
        "ALTER TABLE fsqr ADD COLUMN original_filename VARCHAR(255) DEFAULT NULL",
    )
    _add_column_if_missing(
        "fsqr",
        "retention_days",
        "ALTER TABLE fsqr ADD COLUMN retention_days INT NOT NULL DEFAULT 7",
    )
    _add_index_if_missing(
        "fsqr",
        "idx_fsqr_secure_id",
        "ALTER TABLE fsqr ADD INDEX idx_fsqr_secure_id (secure_id)",
    )


def _ensure_group_room_columns() -> None:
    _add_column_if_missing(
        "room",
        "retention_days",
        "ALTER TABLE room ADD COLUMN retention_days INT NOT NULL DEFAULT 7",
    )
    _add_unique_if_missing(
        "room",
        "uq_room_room_id",
        "ALTER TABLE room ADD UNIQUE KEY uq_room_room_id (room_id)",
    )


def _ensure_share_links_table() -> None:
    if not _table_exists("share_links"):
        op.execute("""
            CREATE TABLE share_links (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                service_key VARCHAR(20) NOT NULL,
                resource_id VARCHAR(255) NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                scope VARCHAR(50) NOT NULL DEFAULT 'read',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NULL,
                revoked_at DATETIME NULL,
                metadata JSON NULL,
                UNIQUE KEY uq_share_links_token_hash (token_hash),
                INDEX idx_share_links_resource (service_key, resource_id),
                INDEX idx_share_links_expires_at (expires_at),
                INDEX idx_share_links_active (
                    service_key, scope, revoked_at, expires_at
                )
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        return

    _add_column_if_missing(
        "share_links",
        "service_key",
        "ALTER TABLE share_links ADD COLUMN service_key VARCHAR(20) NULL",
    )
    _add_column_if_missing(
        "share_links",
        "resource_id",
        "ALTER TABLE share_links ADD COLUMN resource_id VARCHAR(255) NULL",
    )
    _add_column_if_missing(
        "share_links",
        "token_hash",
        "ALTER TABLE share_links ADD COLUMN token_hash VARCHAR(64) NULL",
    )
    _add_column_if_missing(
        "share_links",
        "scope",
        "ALTER TABLE share_links ADD COLUMN scope VARCHAR(50) NOT NULL DEFAULT 'read'",
    )
    _add_column_if_missing(
        "share_links",
        "created_at",
        (
            "ALTER TABLE share_links ADD COLUMN created_at DATETIME NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP"
        ),
    )
    _add_column_if_missing(
        "share_links",
        "expires_at",
        "ALTER TABLE share_links ADD COLUMN expires_at DATETIME NULL",
    )
    _add_column_if_missing(
        "share_links",
        "revoked_at",
        "ALTER TABLE share_links ADD COLUMN revoked_at DATETIME NULL",
    )
    _add_column_if_missing(
        "share_links",
        "metadata",
        "ALTER TABLE share_links ADD COLUMN metadata JSON NULL",
    )
    _add_unique_if_missing(
        "share_links",
        "uq_share_links_token_hash",
        "ALTER TABLE share_links ADD UNIQUE KEY uq_share_links_token_hash (token_hash)",
    )
    _add_index_if_missing(
        "share_links",
        "idx_share_links_resource",
        "ALTER TABLE share_links ADD INDEX idx_share_links_resource (service_key, resource_id)",
    )
    _add_index_if_missing(
        "share_links",
        "idx_share_links_expires_at",
        "ALTER TABLE share_links ADD INDEX idx_share_links_expires_at (expires_at)",
    )
    _add_index_if_missing(
        "share_links",
        "idx_share_links_active",
        (
            "ALTER TABLE share_links ADD INDEX idx_share_links_active "
            "(service_key, scope, revoked_at, expires_at)"
        ),
    )


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
    if _table_exists(table_name) and not _column_exists(table_name, column_name):
        op.execute(ddl)


def _add_index_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    if _table_exists(table_name) and not _index_exists(table_name, index_name):
        op.execute(ddl)


def _add_unique_if_missing(table_name: str, index_name: str, ddl: str) -> None:
    _add_index_if_missing(table_name, index_name, ddl)
