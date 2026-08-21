"""add persisted Yjs state for Note collaboration

Revision ID: 20260821_0013
Revises: 20260821_0012
Create Date: 2026-08-21 00:00:00

既存の LONGTEXT 本文は保持し、Hocuspocus が初回ロード時に同じ本文から Yjs state を
生成する。旧コードとの Blue-Green 共存中も既存列は削除しない。

Existing LONGTEXT content remains intact. Hocuspocus lazily creates the Yjs
state from it on first load, keeping the migration expand-only and reversible.
"""

from alembic import op

revision = "20260821_0013"
down_revision = "20260821_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _column_exists("yjs_state"):
        op.execute("ALTER TABLE note_content ADD COLUMN yjs_state LONGBLOB NULL")


def downgrade() -> None:
    if _column_exists("yjs_state"):
        op.execute("ALTER TABLE note_content DROP COLUMN yjs_state")


def _column_exists(column_name: str) -> bool:
    if not column_name.isidentifier():
        raise ValueError("Unsupported column")
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'note_content' "
        f"AND COLUMN_NAME = '{column_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
