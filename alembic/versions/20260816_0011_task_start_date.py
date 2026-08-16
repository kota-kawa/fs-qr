"""add start_date column to task_item

Revision ID: 20260816_0011
Revises: 20260815_0010
Create Date: 2026-08-16 00:00:00

`feature/task-start-date`（コミット f3e3f20）で task_item.start_date を
参照するコードが追加されたが、対応する Alembic マイグレーションが
作られていなかった。20260815_0010 は task_item テーブルが存在しない
場合のみ CREATE TABLE するため、既に稼働中の環境（task_item が
先に作られていたルーム）では start_date カラムが追加されず、
`SELECT ... start_date ... FROM task_item` が
`Unknown column 'start_date' in 'field list'` で失敗し、
`GET /api/task/{room_id}/items` が 500 を返し続けていた。
このマイグレーションでカラムを冪等に追加して解消する。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260816_0011"
down_revision = "20260815_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _table_exists():
        return
    if _column_exists():
        return
    # db_init/create_tables.sql の列順（category, start_date, due_date）に合わせる。
    op.execute("ALTER TABLE task_item ADD COLUMN start_date DATE NULL AFTER category")


def downgrade() -> None:
    if not _table_exists():
        return
    if not _column_exists():
        return
    op.execute("ALTER TABLE task_item DROP COLUMN start_date")


def _table_exists() -> bool:
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = 'task_item'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _column_exists() -> bool:
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = 'task_item' "
        "AND COLUMN_NAME = 'start_date'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
