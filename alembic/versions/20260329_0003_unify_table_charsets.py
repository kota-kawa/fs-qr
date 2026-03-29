"""unify table charsets to utf8mb4

Revision ID: 20260329_0003
Revises: 20260329_0002
Create Date: 2026-03-29 12:55:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260329_0003"
down_revision = "20260329_0002"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"fsqr", "room", "note_room", "note_content"}
_TARGET_CHARSET = "utf8mb4"


def upgrade() -> None:
    for table_name in sorted(_ALLOWED_TABLES):
        if not _table_exists(table_name):
            continue
        charset = _table_charset(table_name)
        if charset == _TARGET_CHARSET:
            continue
        op.execute(
            f"ALTER TABLE {table_name} CONVERT TO CHARACTER SET {_TARGET_CHARSET}"
        )


def downgrade() -> None:
    # NOTE:
    # UTF-8MB4 -> UTF-8 can be lossy for 4-byte characters.
    # Keep downgrade as no-op for safety.
    pass


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


def _table_charset(table_name: str) -> str | None:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = f"""
        SELECT CCSA.CHARACTER_SET_NAME
        FROM information_schema.TABLES AS T
        JOIN information_schema.COLLATION_CHARACTER_SET_APPLICABILITY AS CCSA
          ON CCSA.COLLATION_NAME = T.TABLE_COLLATION
        WHERE T.TABLE_SCHEMA = DATABASE()
          AND T.TABLE_NAME = '{table_name}'
        LIMIT 1
    """
    return op.get_bind().exec_driver_sql(query).scalar()
