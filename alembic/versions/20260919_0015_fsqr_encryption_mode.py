"""Add FSQR deletion state and payload encryption mode.

Revision ID: 20260919_0015
Revises: 20260919_0014
Create Date: 2026-09-19 00:00:00

New browser uploads use a random AES-GCM key kept in the URL fragment.  Older
rows remain password-derived for compatibility, so the storage format must be
identified explicitly when a user tries the ID/password lookup flow.
"""

from alembic import op


revision = "20260919_0015"
down_revision = "20260919_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _table_exists():
        return

    if not _column_exists("status"):
        op.execute(
            "ALTER TABLE fsqr ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
        )
    if not _column_exists("deleted_at"):
        op.execute("ALTER TABLE fsqr ADD COLUMN deleted_at DATETIME NULL")
    if not _column_exists("encryption_mode"):
        op.execute(
            "ALTER TABLE fsqr ADD COLUMN encryption_mode VARCHAR(20) "
            "NOT NULL DEFAULT 'password'"
        )


def downgrade() -> None:
    if not _table_exists():
        return
    for column_name in ("encryption_mode", "deleted_at", "status"):
        if _column_exists(column_name):
            op.execute(f"ALTER TABLE fsqr DROP COLUMN {column_name}")


def _table_exists() -> bool:
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fsqr'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _column_exists(column_name: str) -> bool:
    # The caller supplies only the fixed column names listed in upgrade/downgrade.
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fsqr' "
        f"AND COLUMN_NAME = '{column_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
