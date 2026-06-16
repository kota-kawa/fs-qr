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
from .group_realtime import hub as group_ws_hub
from .group_storage import iter_room_folders

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, "static/qrcode")
STATIC = os.path.join(BASE_DIR, "static/upload")


# グループの部屋の作成
async def create_room(id, password, room_id, retention_days=7):
    hashed_password = hash_password(password)
    query = text("""
        INSERT INTO room (time, id, password, room_id, retention_days)
        VALUES (NOW(), :id, :password, :room_id, :retention_days)
    """)
    await execute_query(
        query,
        {
            "id": id,
            "password": hashed_password,
            "room_id": room_id,
            "retention_days": retention_days,
        },
    )
    await invalidate_cache_entry(pich_room_id, id, password)
    await invalidate_cache_entry(get_data, room_id)
    await invalidate_cache_entry(get_all)


# ログイン処理
async def pich_room_id_direct(id, password) -> Optional[str]:
    query = text("""
        SELECT room_id, password FROM room WHERE id = :id
    """)
    result = await execute_query(query, {"id": id}, fetch=True)
    for row in result:
        stored_password = row.get("password")
        if not verify_password(stored_password, password):
            continue
        return row["room_id"]
    return None


@cache_data(ttl=60)
async def pich_room_id(id, password):
    return await pich_room_id_direct(id, password)


# データベースから任意のIDのデータを取り出す
async def get_data_direct(secure_id):
    query = text("""
        SELECT * FROM room WHERE room_id = :secure_id
    """)
    result = await execute_query(query, {"secure_id": secure_id}, fetch=True)
    return result


async def get_data_by_room_credentials(room_id: str, password: str):
    rows = await get_data_direct(room_id)
    if not rows:
        return None
    record = rows[0]
    stored_password = record.get("password")
    if not verify_password(stored_password, password):
        return None
    return record


@cache_data(ttl=60, strip_keys=("password",))
async def get_data(secure_id):
    return await get_data_direct(secure_id)


# 全てのデータを取得する
@cache_data(ttl=300, strip_keys=("password",))
async def get_all():
    return await get_all_direct()


async def get_all_direct():
    query = text("""
        SELECT * FROM room ORDER BY suji DESC
    """)
    return await execute_query(query, fetch=True)


# アップロードされたファイルとメタ情報の削除
async def remove_data(secure_id):
    """
    指定されたルームのデータベースレコードと、
    関連するアップロードフォルダおよびその他のファイル（ZIPファイル、QRコード画像など）を削除します。
    """
    room_data = await get_data_direct(secure_id)
    room_record = room_data[0] if room_data else None

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
            "ファイル削除に失敗したためDBレコードを保持します: room_id=%s",
            secure_id,
        )
        return False

    # データベースから該当ルームのレコードを削除
    query = text("""
        DELETE FROM room WHERE room_id = :secure_id
    """)
    await execute_query(query, {"secure_id": secure_id})

    # DB削除後の副作用を並列実行して高速化
    async def _revoke_links():
        try:
            from share_links import ServiceKey, revoke_resource_links

            await revoke_resource_links(service_key=ServiceKey.GROUP, resource_id=secure_id)
        except Exception:
            logger.warning(
                "Failed to revoke Group share links: room_id=%s",
                secure_id,
                exc_info=True,
            )

    async def _invalidate_caches():
        await invalidate_cache_entry(get_data, secure_id)
        await invalidate_cache_entry(get_all)
        if room_record:
            await invalidate_cache_prefix(pich_room_id)

    await asyncio.gather(
        _revoke_links(),
        group_ws_hub.close_room(secure_id, code=1001),
        _invalidate_caches(),
    )
    return True


# 全てのデータを削除
async def all_remove():
    rooms = await get_all_direct()
    all_removed = True

    for room in rooms:
        room_id = room.get("room_id")
        if not room_id:
            continue
        removed = await remove_data(room_id)
        all_removed = all_removed and removed
    return all_removed


# 1週間以上経過したルームを削除する関数
async def remove_expired_rooms():
    # 1週間以上前のルームを取得するクエリ（MySQLの場合）
    query = text(
        """
        SELECT room_id
        FROM room
        WHERE DATE_ADD(time, INTERVAL retention_days DAY) <= NOW()
    """
    )
    expired_rooms = await execute_query(query, fetch=True)
    for room in expired_rooms:
        room_id = room.get("room_id")
        if room_id:
            await remove_data(room_id)
            # ログ出力など必要に応じて追加
