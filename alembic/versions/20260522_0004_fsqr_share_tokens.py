"""add hashed FSQR share tokens

Revision ID: 20260522_0004
Revises: 20260329_0003
Create Date: 2026-05-22 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260522_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr"}


def upgrade() -> None:
    _add_column_if_missing(
        table_name="fsqr",
        column_name="share_token_hash",
        ddl=(
            "ALTER TABLE fsqr ADD COLUMN share_token_hash VARCHAR(64) DEFAULT NULL "
            "COMMENT 'Hash of bearer share token for FSQR share URLs'"
        ),
    )
    _add_unique_if_missing(
        table_name="fsqr",
        index_name="uq_fsqr_share_token_hash",
        ddl=(
            "ALTER TABLE fsqr ADD UNIQUE KEY uq_fsqr_share_token_hash "
            "(share_token_hash)"
        ),
    )


def downgrade() -> None:
    _drop_index_if_exists(table_name="fsqr", index_name="uq_fsqr_share_token_hash")
    _drop_column_if_exists(table_name="fsqr", column_name="share_token_hash")


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


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, column_name):
        return
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
