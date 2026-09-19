import asyncio
import os
import shutil
import logging
from typing import Optional

import log_config  # noqa: F401
from sqlalchemy import text

from password_security import hash_password, verify_password
from database import execute_query
from cache_utils import cache_data, invalidate_cache_entry, invalidate_cache_prefix
from .group_realtime import notify_group_room_closed
from .group_storage import UPLOAD_FOLDER, async_room_upload_lock, iter_room_folders
from room_repository import (
    GROUP_ROOMS,
    find_room_id_by_credentials,
    get_active_room,
    revoke_room_links,
    room_id_exists,
)
from share_links import ServiceKey

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, "static/qrcode")
STATIC = os.path.join(BASE_DIR, "static/upload")


# グループの部屋の作成
async def create_room(id, password, room_id, retention_hours=24):
    hashed_password = hash_password(password)
    query = text("""
        INSERT INTO room (
            time, id, password, room_id, retention_days, retention_hours, expires_at,
            status, deleted_at
        )
        VALUES (
            NOW(), :id, :password, :room_id, 1, :retention_hours,
            DATE_ADD(NOW(), INTERVAL :retention_hours HOUR), 'active', NULL
        )
    """)
    await execute_query(
        query,
        {
            "id": id,
            "password": hashed_password,
            "room_id": room_id,
            "retention_hours": retention_hours,
        },
    )
    await invalidate_cache_entry(pich_room_id, id, password)
    await invalidate_cache_entry(get_data, room_id)
    await invalidate_cache_entry(get_all)


# ログイン処理
async def pich_room_id_direct(id, password) -> Optional[str]:
    return await find_room_id_by_credentials(execute_query, GROUP_ROOMS, id, password)


@cache_data(ttl=60, key_prefix="room.group.credentials")
async def pich_room_id(id, password):
    return await pich_room_id_direct(id, password)


# データベースから任意のIDのデータを取り出す
async def get_data_direct(secure_id):
    record = await get_active_room(execute_query, GROUP_ROOMS, secure_id)
    return [record] if record else []


async def get_data_by_room_credentials(room_id: str, password: str):
    rows = await get_data_direct(room_id)
    if not rows:
        return None
    record = rows[0]
    stored_password = record.get("password")
    if not verify_password(stored_password, password):
        return None
    return record


async def room_id_is_reserved(room_id: str) -> bool:
    """Check active and deleted rows when allocating a Group room ID."""

    return await room_id_exists(execute_query, GROUP_ROOMS, room_id)


@cache_data(ttl=60, key_prefix="room.group.meta", strip_keys=("password",))
async def get_data(secure_id):
    return await get_data_direct(secure_id)


# 全てのデータを取得する
@cache_data(ttl=300, key_prefix="room.group.all", strip_keys=("password",))
async def get_all():
    return await get_all_direct()


async def get_all_direct():
    query = text("""
        SELECT * FROM room
        WHERE status = 'active' AND expires_at > NOW()
        ORDER BY suji DESC
    """)
    return await execute_query(query, fetch=True)


async def _get_cleanup_room(secure_id):
    """Return an active/deleting room so interrupted cleanup can be retried."""

    query = text("""
        SELECT * FROM room
        WHERE room_id = :secure_id AND status IN ('active', 'deleting')
    """)
    rows = await execute_query(query, {"secure_id": secure_id}, fetch=True)
    return rows[0] if rows else None


async def _list_cleanup_room_ids(*, expired_only=False):
    if expired_only:
        query = text("""
            SELECT room_id FROM room
            WHERE status = 'deleting'
               OR (status = 'active' AND expires_at <= NOW())
            ORDER BY suji DESC
        """)
    else:
        query = text("""
            SELECT room_id FROM room
            WHERE status IN ('active', 'deleting')
            ORDER BY suji DESC
        """)
    rows = await execute_query(query, fetch=True)
    return [row.get("room_id") for row in rows if row.get("room_id")]


# アップロードされたファイルとメタ情報の削除
async def remove_data(secure_id):
    """
    指定されたルームのデータベースレコードと、
    関連するアップロードフォルダおよびその他のファイル（ZIPファイル、QRコード画像など）を削除します。
    """
    room_data = await get_data_direct(secure_id)
    room_record = room_data[0] if room_data else None
    if not room_record:
        room_record = await _get_cleanup_room(secure_id)
    if not room_record:
        return False

    # The same lock is used by uploads and per-file deletes.  Marking the room
    # as deleting before touching disk makes a failed cleanup retryable while
    # preventing a racing upload from recreating files after rmtree.
    async with async_room_upload_lock(secure_id, primary_root=UPLOAD_FOLDER):
        query = text("""
            UPDATE room
            SET status = 'deleting', deleted_at = NOW()
            WHERE room_id = :secure_id AND status IN ('active', 'deleting')
        """)
        await execute_query(query, {"secure_id": secure_id})

        deletion_failed = False
        for _, room_folder in iter_room_folders(secure_id):
            if not os.path.exists(room_folder):
                continue
            try:
                await asyncio.to_thread(shutil.rmtree, room_folder)
            except Exception as e:
                deletion_failed = True
                logger.error(
                    "アップロードフォルダの削除に失敗しました: %s. エラー: %s",
                    room_folder,
                    e,
                )

        if deletion_failed:
            logger.error(
                "ファイル削除に失敗したためdeleting状態を保持します: room_id=%s",
                secure_id,
            )
            return False

        # Keep a tombstone so a stale session can never reach a later room
        # reusing the same public ID.
        query = text("""
            UPDATE room
            SET status = 'deleted', deleted_at = NOW()
            WHERE room_id = :secure_id AND status = 'deleting'
        """)
        await execute_query(query, {"secure_id": secure_id})

    # DB削除後の副作用を並列実行して高速化
    async def _revoke_links():
        await revoke_room_links(ServiceKey.GROUP, secure_id, logger=logger)

    async def _invalidate_caches():
        await invalidate_cache_entry(get_data, secure_id)
        await invalidate_cache_entry(get_all)
        if room_record:
            await invalidate_cache_prefix(pich_room_id)

    await asyncio.gather(
        _revoke_links(),
        notify_group_room_closed(secure_id, code=1001),
        _invalidate_caches(),
    )
    return True


# 全てのデータを削除
async def all_remove():
    room_ids = await _list_cleanup_room_ids()
    all_removed = True

    for room_id in room_ids:
        removed = await remove_data(room_id)
        all_removed = all_removed and removed
    return all_removed


# 1週間以上経過したルームを削除する関数
async def remove_expired_rooms():
    expired_ids = await _list_cleanup_room_ids(expired_only=True)
    for room_id in expired_ids:
        await remove_data(room_id)
    return expired_ids
