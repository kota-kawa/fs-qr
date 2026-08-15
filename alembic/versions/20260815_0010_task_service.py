"""add Task service tables

Revision ID: 20260815_0010
Revises: 20260719_0009
Create Date: 2026-08-15 00:00:00
"""

from alembic import op

revision = "20260815_0010"
down_revision = "20260719_0009"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"task_room", "task_item"}


def _table_exists(table_name: str) -> bool:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError("Unsupported table")
    query = (
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME = '{table_name}'"
    )
    return bool(op.get_bind().exec_driver_sql(query).scalar())


def upgrade() -> None:
    if not _table_exists("task_room"):
        op.execute("""
            CREATE TABLE task_room (
                suji INT AUTO_INCREMENT PRIMARY KEY, time DATETIME NOT NULL,
                id VARCHAR(255) NOT NULL, password VARCHAR(255) NOT NULL,
                room_id VARCHAR(255) NOT NULL, retention_days INT NOT NULL DEFAULT 1,
                retention_hours INT NOT NULL DEFAULT 24, expires_at DATETIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active', deleted_at DATETIME NULL,
                share_token_hash VARCHAR(64) DEFAULT NULL,
                UNIQUE KEY uq_task_room_room_id (room_id),
                UNIQUE KEY uq_task_room_share_token_hash (share_token_hash),
                INDEX idx_task_room_id_password (id, password), INDEX idx_task_room_time (time),
                INDEX idx_task_room_expires_status (status, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    if not _table_exists("task_item"):
        op.execute("""
            CREATE TABLE task_item (
                item_id BIGINT AUTO_INCREMENT PRIMARY KEY, room_id VARCHAR(255) NOT NULL,
                title VARCHAR(200) NOT NULL, note VARCHAR(500) NULL,
                board_status VARCHAR(16) NOT NULL DEFAULT 'todo', priority VARCHAR(8) NOT NULL DEFAULT 'normal',
                category VARCHAR(40) NULL, due_date DATE NULL, position INT NOT NULL DEFAULT 0,
                created_at DATETIME(6) NOT NULL, updated_at DATETIME(6) NOT NULL,
                version INT NOT NULL DEFAULT 0,
                INDEX idx_task_item_room_board (room_id, board_status, position),
                INDEX idx_task_item_room_due (room_id, due_date),
                CONSTRAINT fk_task_item_room_id FOREIGN KEY (room_id)
                    REFERENCES task_room(room_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


def downgrade() -> None:
    if _table_exists("task_item"):
        op.execute("DROP TABLE task_item")
    if _table_exists("task_room"):
        op.execute("DROP TABLE task_room")
