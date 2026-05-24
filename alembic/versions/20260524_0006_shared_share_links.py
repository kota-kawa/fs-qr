"""add shared share links

Revision ID: 20260524_0006
Revises: 20260524_0005
Create Date: 2026-05-24 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260524_0006"
down_revision = "20260524_0005"
branch_labels = None
depends_on = None

_ALLOWED_TABLES = {"share_links"}


def upgrade() -> None:
    if _table_exists("share_links"):
        return
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
            INDEX idx_share_links_active (service_key, scope, revoked_at, expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


def downgrade() -> None:
    if _table_exists("share_links"):
        op.execute("DROP TABLE share_links")


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
