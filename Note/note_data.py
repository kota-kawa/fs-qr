import asyncio
import hashlib
import logging
from typing import Optional

import log_config  # noqa: F401
from sqlalchemy import text

from password_security import hash_password, verify_password
from database import db_session, execute_query
from cache_utils import cache_data, invalidate_cache_entry, invalidate_cache_prefix

# ログ設定
logger = logging.getLogger(__name__)


# note_app.py などから使用するエイリアス関数
_exec = execute_query

# テーブル定義
CREATE_NOTE_ROOM = """
CREATE TABLE IF NOT EXISTS note_room(
  suji INT AUTO_INCREMENT PRIMARY KEY,
  time DATETIME NOT NULL,
  id VARCHAR(255) NOT NULL,
  password VARCHAR(255) NOT NULL,
  room_id VARCHAR(255) NOT NULL,
  retention_days INT NOT NULL DEFAULT 7,
  expires_at DATETIME NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  deleted_at DATETIME NULL,
  share_token_hash VARCHAR(64) DEFAULT NULL,
  UNIQUE KEY uq_note_room_room_id (room_id),
  UNIQUE KEY uq_note_room_share_token_hash (share_token_hash),
  INDEX idx_note_room_id_password (id, password),
  INDEX idx_note_room_room_id_password (room_id, password),
  INDEX idx_note_room_time (time),
  INDEX idx_note_room_expires_status (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

CREATE_NOTE_CONTENT = """
CREATE TABLE IF NOT EXISTS note_content(
  room_id VARCHAR(255) PRIMARY KEY,
  content LONGTEXT,
  updated_at DATETIME(6),
  version BIGINT NOT NULL DEFAULT 0,
  INDEX idx_note_content_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


ADD_NOTE_ROOM_IDX_ID_PASSWORD = """
ALTER TABLE note_room
ADD INDEX idx_note_room_id_password (id, password)
"""  # noqa: S105

ADD_NOTE_ROOM_IDX_ROOM_ID_PASSWORD = """
ALTER TABLE note_room
ADD INDEX idx_note_room_room_id_password (room_id, password)
"""  # noqa: S105

ADD_NOTE_ROOM_IDX_TIME = """
ALTER TABLE note_room
ADD INDEX idx_note_room_time (time)
"""

ADD_NOTE_CONTENT_IDX_UPDATED_AT = """
ALTER TABLE note_content
ADD INDEX idx_note_content_updated_at (updated_at)
"""

ADD_NOTE_ROOM_IDX_EXPIRES_STATUS = """
ALTER TABLE note_room
ADD INDEX idx_note_room_expires_status (status, expires_at)
"""

INDEX_CHECK_SQL = """
SELECT COUNT(*) AS cnt
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name = :table_name
  AND index_name = :index_name
"""

UNIQUE_CHECK_SQL = """
SELECT COUNT(*) AS cnt
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name = :table_name
  AND index_name = :index_name
  AND non_unique = 0
"""


async def ensure_index(table_name: str, index_name: str, ddl: str):
    rows = await execute_query(
        INDEX_CHECK_SQL,
        {"table_name": table_name, "index_name": index_name},
        fetch=True,
    )
    exists = bool(rows and rows[0].get("cnt"))
    if exists:
        return
    await execute_query(ddl)


async def ensure_unique_key(table_name: str, index_name: str, ddl: str):
    rows = await execute_query(
        UNIQUE_CHECK_SQL,
        {"table_name": table_name, "index_name": index_name},
        fetch=True,
    )
    exists = bool(rows and rows[0].get("cnt"))
    if exists:
        return
    await execute_query(ddl)


async def ensure_column(table_name: str, column_name: str, ddl: str):
    rows = await execute_query(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = :table_name
          AND column_name = :column_name
        """,
        {"table_name": table_name, "column_name": column_name},
        fetch=True,
    )
    exists = bool(rows and rows[0].get("cnt"))
    if exists:
        return
    await execute_query(ddl)


# テーブル作成チェック
async def ensure_tables():
    await execute_query(CREATE_NOTE_ROOM)
    await execute_query(CREATE_NOTE_CONTENT)
    await ensure_column(
        "note_room",
        "expires_at",
        "ALTER TABLE note_room ADD COLUMN expires_at DATETIME NULL",
    )
    await execute_query(
        "UPDATE note_room SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY) "
        "WHERE expires_at IS NULL"
    )
    await execute_query("ALTER TABLE note_room MODIFY expires_at DATETIME NOT NULL")
    await ensure_column(
        "note_room",
        "status",
        "ALTER TABLE note_room ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'",
    )
    await ensure_column(
        "note_room",
        "deleted_at",
        "ALTER TABLE note_room ADD COLUMN deleted_at DATETIME NULL",
    )
    await ensure_column(
        "note_room",
        "share_token_hash",
        "ALTER TABLE note_room ADD COLUMN share_token_hash VARCHAR(64) DEFAULT NULL",
    )
    await ensure_column(
        "note_content",
        "version",
        "ALTER TABLE note_content ADD COLUMN version BIGINT NOT NULL DEFAULT 0",
    )
    await ensure_unique_key(
        "note_room",
        "uq_note_room_room_id",
        "ALTER TABLE note_room ADD UNIQUE KEY uq_note_room_room_id (room_id)",
    )
    await ensure_unique_key(
        "note_room",
        "uq_note_room_share_token_hash",
        "ALTER TABLE note_room ADD UNIQUE KEY uq_note_room_share_token_hash (share_token_hash)",
    )
    # 既存テーブルをマイクロ秒精度に更新
    try:
        await execute_query("ALTER TABLE note_content MODIFY updated_at DATETIME(6)")
    except Exception:  # noqa: S110
        pass
    await ensure_index(
        "note_room", "idx_note_room_id_password", ADD_NOTE_ROOM_IDX_ID_PASSWORD
    )
    await ensure_index(
        "note_room",
        "idx_note_room_room_id_password",
        ADD_NOTE_ROOM_IDX_ROOM_ID_PASSWORD,
    )
    await ensure_index("note_room", "idx_note_room_time", ADD_NOTE_ROOM_IDX_TIME)
    await ensure_index(
        "note_room",
        "idx_note_room_expires_status",
        ADD_NOTE_ROOM_IDX_EXPIRES_STATUS,
    )
    await ensure_index(
        "note_content",
        "idx_note_content_updated_at",
        ADD_NOTE_CONTENT_IDX_UPDATED_AT,
    )
    logger.info("note tables checked/created")


def hash_share_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ────────────────────────────────────────────
# ノートルーム作成
# ────────────────────────────────────────────
async def create_room(id_, password, room_id, retention_days=7, share_token_hash=None):
    hashed_password = hash_password(password)
    async with db_session.begin():
        await db_session.execute(
            text("""
            INSERT INTO note_room(
                time, id, password, room_id, retention_days,
                expires_at, status, share_token_hash
            )
            VALUES(
                NOW(), :i, :p, :r, :retention,
                DATE_ADD(NOW(), INTERVAL :retention DAY), 'active', :share_token_hash
            )
            """),
            {
                "i": id_,
                "p": hashed_password,
                "r": room_id,
                "retention": retention_days,
                "share_token_hash": share_token_hash,
            },
        )
        await db_session.execute(
            text("""
            INSERT INTO note_content(room_id, content, updated_at, version)
            VALUES(:r, '', NOW(6), 0)
            """),
            {"r": room_id},
        )
    await invalidate_cache_entry(get_room_meta, room_id)
    await invalidate_cache_entry(get_room_meta, room_id, password=password)
    await invalidate_cache_entry(pick_room_id, id_, password)


# ────────────────────────────────────────────
# ルームメタ情報取得
# ────────────────────────────────────────────
async def get_room_meta_direct(room_id, password=None):
    rows = await execute_query(
        """
        SELECT room_id, id, password, time, retention_days, expires_at, status, deleted_at
        FROM note_room
        WHERE room_id=:r
          AND status = 'active'
          AND expires_at > NOW()
        """,
        {"r": room_id},
        fetch=True,
    )
    if not rows:
        return None
    row = rows[0]
    if password is None:
        return row
    stored_password = row.get("password")
    if not verify_password(stored_password, password):
        return None
    return row


@cache_data(ttl=60, strip_keys=("password",))
async def get_room_meta(room_id, password=None):
    return await get_room_meta_direct(room_id, password=password)


async def get_room_meta_by_share_token_hash(share_token_hash: str):
    rows = await execute_query(
        """
        SELECT room_id, id, time, retention_days, expires_at, status, deleted_at
        FROM note_room
        WHERE share_token_hash=:h
          AND status = 'active'
          AND expires_at > NOW()
        """,
        {"h": share_token_hash},
        fetch=True,
    )
    return rows[0] if rows else None


# ────────────────────────────────────────────
# ID とパスワードで room_id を取得
# ────────────────────────────────────────────
async def pick_room_id_direct(id_, password) -> Optional[str]:
    rows = await execute_query(
        "SELECT room_id, password FROM note_room WHERE id=:i",
        {"i": id_},
        fetch=True,
    )
    for row in rows:
        stored_password = row.get("password")
        if not verify_password(stored_password, password):
            continue
        return row["room_id"]
    return None


@cache_data(ttl=60)
async def pick_room_id(id_, password):
    return await pick_room_id_direct(id_, password)


# エイリアス（タイポ呼び出し対応）
pich_room_id = pick_room_id


# ────────────────────────────────────────────
# コンテンツ取得 or 初期レコード作成
# ────────────────────────────────────────────
async def get_row(room_id):
    rows = await execute_query(
        """
        SELECT nc.room_id, nc.content, nc.updated_at, nc.version
        FROM note_content nc
        JOIN note_room nr ON nr.room_id = nc.room_id
        WHERE nc.room_id=:r
          AND nr.status = 'active'
          AND nr.expires_at > NOW()
        """,
        {"r": room_id},
        fetch=True,
    )
    if rows:
        return rows[0]
    return None


# get_row のエイリアス（他プログラム互換）
fetch_note = get_row


# ────────────────────────────────────────────
# コンテンツ保存
# ────────────────────────────────────────────
async def save_content(room_id, content, expected_version):
    query = text("""
        UPDATE note_content nc
        JOIN note_room nr ON nr.room_id = nc.room_id
        SET nc.content=:c, nc.updated_at=NOW(6), nc.version=nc.version + 1
        WHERE nc.room_id=:r
          AND nc.version=:expected_version
          AND nr.status = 'active'
          AND nr.expires_at > NOW()
    """)
    params = {"c": content, "r": room_id, "expected_version": expected_version}
    return await execute_query(query, params)


# save_content のエイリアス
store_content = save_content


async def remove_room(room_id: str, status: str = "deleted") -> None:
    await execute_query(
        """
        UPDATE note_room
        SET status = :status, deleted_at = NOW()
        WHERE room_id = :r
        """,
        {"r": room_id, "status": status},
    )
    await execute_query("DELETE FROM note_content WHERE room_id = :r", {"r": room_id})

    # DB削除後の副作用を並列実行して高速化
    async def _revoke_links():
        try:
            from share_links import ServiceKey, revoke_resource_links

            await revoke_resource_links(
                service_key=ServiceKey.NOTE, resource_id=room_id
            )
        except Exception:
            logger.warning(
                "Failed to revoke Note share links: room_id=%s",
                room_id,
                exc_info=True,
            )

    async def _invalidate_caches():
        await invalidate_cache_entry(get_room_meta, room_id)
        await invalidate_cache_prefix(get_room_meta)
        await invalidate_cache_prefix(pick_room_id)

    await asyncio.gather(_revoke_links(), _invalidate_caches())


# ────────────────────────────────────────────
# １週間以上経過したノートルームを削除
# ────────────────────────────────────────────
async def remove_expired_rooms():
    expired_room_ids = []
    try:
        rows = await execute_query(
            """
            SELECT room_id
            FROM note_room
            WHERE status = 'active'
              AND expires_at <= NOW()
            """,
            fetch=True,
        )
        for r in rows:
            rid = r["room_id"]
            async with db_session.begin():
                await db_session.execute(
                    text("""
                    UPDATE note_room
                    SET status = 'expired', deleted_at = NOW()
                    WHERE room_id = :r AND status = 'active'
                    """),
                    {"r": rid},
                )
                await db_session.execute(
                    text("DELETE FROM note_content WHERE room_id = :r"), {"r": rid}
                )
            try:
                from share_links import ServiceKey, revoke_resource_links

                await revoke_resource_links(
                    service_key=ServiceKey.NOTE, resource_id=rid
                )
            except Exception:
                logger.warning(
                    "Failed to revoke Note share links: room_id=%s",
                    rid,
                    exc_info=True,
                )
            await invalidate_cache_entry(get_room_meta, rid)
            expired_room_ids.append(rid)
            logger.info(f"Expired note room removed: {rid}")
        await invalidate_cache_prefix(get_room_meta)
        await invalidate_cache_prefix(pick_room_id)
        return {
            "expired_count": len(expired_room_ids),
            "expired_room_ids": expired_room_ids,
        }
    except Exception as e:
        logger.error(f"Failed to remove expired note rooms: {e}")
        return {"expired_count": 0, "expired_room_ids": [], "error": str(e)}
