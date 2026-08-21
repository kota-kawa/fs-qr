"""replace task_item.category with per-room task tags

Revision ID: 20260821_0012
Revises: 20260816_0011
Create Date: 2026-08-21 00:00:00

タスクの分類を「カテゴリ（1タスク1件の文字列）」から「タグ（1タスクに複数、
ルーム単位で自由に追加・削除できる）」へ統一する。既存の category は同名の
タグへ移し替えてから列を落とすため、稼働中のボードでも分類が失われない。

Unifies task classification on tags: existing category values are migrated into
per-room tags (and linked to their items) before the column is dropped, so no
running board loses its labels.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260821_0012"
down_revision = "20260816_0011"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"task_item", "task_tag", "task_item_tag"}


def upgrade() -> None:
    if not _table_exists("task_item"):
        return

    if not _table_exists("task_tag"):
        op.execute("""
            CREATE TABLE task_tag (
                tag_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                room_id VARCHAR(255) NOT NULL,
                name VARCHAR(40) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                UNIQUE KEY uq_task_tag_room_name (room_id, name),
                CONSTRAINT fk_task_tag_room_id FOREIGN KEY (room_id)
                    REFERENCES task_room(room_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    if not _table_exists("task_item_tag"):
        op.execute("""
            CREATE TABLE task_item_tag (
                item_id BIGINT NOT NULL,
                tag_id BIGINT NOT NULL,
                PRIMARY KEY (item_id, tag_id),
                INDEX idx_task_item_tag_tag (tag_id),
                CONSTRAINT fk_task_item_tag_item FOREIGN KEY (item_id)
                    REFERENCES task_item(item_id) ON DELETE CASCADE,
                CONSTRAINT fk_task_item_tag_tag FOREIGN KEY (tag_id)
                    REFERENCES task_tag(tag_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    if _column_exists("task_item", "category"):
        # 既存のカテゴリをルームごとのタグへ移し替えてから列を落とす。
        # Move existing categories into per-room tags before dropping the column.
        op.execute("""
            INSERT IGNORE INTO task_tag (room_id, name, created_at)
            SELECT DISTINCT room_id, TRIM(category), NOW(6)
            FROM task_item
            WHERE category IS NOT NULL AND TRIM(category) <> ''
        """)
        op.execute("""
            INSERT IGNORE INTO task_item_tag (item_id, tag_id)
            SELECT i.item_id, t.tag_id
            FROM task_item i
            JOIN task_tag t ON t.room_id = i.room_id AND t.name = TRIM(i.category)
            WHERE i.category IS NOT NULL AND TRIM(i.category) <> ''
        """)
        op.execute("ALTER TABLE task_item DROP COLUMN category")


def downgrade() -> None:
    if not _table_exists("task_item"):
        return

    if not _column_exists("task_item", "category"):
        op.execute(
            "ALTER TABLE task_item ADD COLUMN category VARCHAR(40) NULL AFTER priority"
        )

    if _table_exists("task_tag") and _table_exists("task_item_tag"):
        # カテゴリは1件しか持てないため、名前順で先頭のタグだけを書き戻す。
        # A category holds a single value, so only the first tag by name is restored.
        op.execute("""
            UPDATE task_item i
            SET category = (
                SELECT t.name FROM task_item_tag it
                JOIN task_tag t ON t.tag_id = it.tag_id
                WHERE it.item_id = i.item_id
                ORDER BY t.name LIMIT 1
            )
        """)

    if _table_exists("task_item_tag"):
        op.execute("DROP TABLE task_item_tag")
    if _table_exists("task_tag"):
        op.execute("DROP TABLE task_tag")


def _table_exists(table_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError("Unsupported table")
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME = '{table_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def _column_exists(table_name: str, column_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES or not column_name.isidentifier():
        raise ValueError("Unsupported column")
    query = (
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME = '{table_name}' "
        f"AND COLUMN_NAME = '{column_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())
