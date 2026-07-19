"""limit shared content retention to 24 hours

Revision ID: 20260719_0009
Revises: 20260710_0008
Create Date: 2026-07-19 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260719_0009"
down_revision = "20260710_0008"
branch_labels = None
depends_on = None

_TABLES = ("fsqr", "room", "note_room")
_SERVICE_KEYS = {"fsqr": "fsqr", "room": "group", "note_room": "note"}
_RESOURCE_COLUMNS = {"fsqr": "secure_id", "room": "room_id", "note_room": "room_id"}


def upgrade() -> None:
    """Add hour-level retention and expire all existing shared data at 24 hours."""
    for table_name in _TABLES:
        if not _table_exists(table_name):
            continue
        if not _column_exists(table_name, "retention_hours"):
            op.execute(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN retention_hours INT NULL AFTER retention_days"
            )
        op.execute(
            f"UPDATE {table_name} SET retention_hours = 24 "
            "WHERE retention_hours IS NULL"
        )
        op.execute(
            f"ALTER TABLE {table_name} MODIFY retention_hours INT NOT NULL DEFAULT 24"
        )
        # 旧データも作成時刻から最大24時間に統一する。
        op.execute(
            f"UPDATE {table_name} "
            "SET retention_days = 1, "
            "expires_at = DATE_ADD(time, INTERVAL retention_hours HOUR)"
        )
        _shorten_share_link_expiry(table_name)


def downgrade() -> None:
    """Remove hour-level retention; expired records are intentionally not restored."""
    for table_name in _TABLES:
        if not _table_exists(table_name):
            continue
        op.execute(f"UPDATE {table_name} SET retention_days = 1")
        if _column_exists(table_name, "retention_hours"):
            op.execute(f"ALTER TABLE {table_name} DROP COLUMN retention_hours")


def _shorten_share_link_expiry(table_name: str) -> None:
    """共有リンクも対象データの期限を超えて有効にならないよう同期する。"""
    if not _table_exists("share_links"):
        return
    service_key = _SERVICE_KEYS[table_name]
    resource_column = _RESOURCE_COLUMNS[table_name]
    op.execute(
        "UPDATE share_links AS links "
        f"JOIN {table_name} AS resource "
        f"ON links.resource_id = resource.{resource_column} "
        "SET links.expires_at = resource.expires_at "
        f"WHERE links.service_key = '{service_key}'"
    )


def _table_exists(table_name: str) -> bool:
    if table_name not in {*_TABLES, "share_links"}:
        raise ValueError(f"Unsupported table name: {table_name}")
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME = '{table_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _column_exists(table_name: str, column_name: str) -> bool:
    if table_name not in _TABLES or column_name != "retention_hours":
        raise ValueError("Unsupported table or column")
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME = '{table_name}' "
        f"AND COLUMN_NAME = '{column_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
