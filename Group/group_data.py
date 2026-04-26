import os
import shutil
import logging
from typing import Optional
import log_config  # noqa: F401
from sqlalchemy import text
from werkzeug.utils import secure_filename
from database import execute_query
from cache_utils import cache_data, invalidate_cache_entry, invalidate_cache_prefix
from .group_realtime import hub as group_ws_hub

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, "static/qrcode")
STATIC = os.path.join(BASE_DIR, "static/upload")


# グループの部屋の作成
async def create_room(id, password, room_id, retention_days=7):
    query = text("""
        INSERT INTO room (time, id, password, room_id, retention_days)
        VALUES (NOW(), :id, :password, :room_id, :retention_days)
    """)
    await execute_query(
        query,
        {
            "id": id,
            "password": password,
            "room_id": room_id,
            "retention_days": retention_days,
        },
    )
    await invalidate_cache_entry("pich_room_id", id, password)
    await invalidate_cache_entry("get_data", room_id)
    await invalidate_cache_entry("get_all")


# ログイン処理
async def pich_room_id_direct(id, password) -> Optional[str]:
    query = text("""
        SELECT room_id FROM room WHERE id = :id AND password = :password
    """)
    result = await execute_query(query, {"id": id, "password": password}, fetch=True)
    return result[0]["room_id"] if result else None


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


@cache_data(ttl=60)
async def get_data(secure_id):
    return await get_data_direct(secure_id)


# 全てのデータを取得する
@cache_data(ttl=300)
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
    # secure_id の検証は room_id にハイフンなどが含まれることがあるため、ここでは省略

    # グループアップロードフォルダのパスを計算（group_app.py と同様の処理）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    group_uploads = os.path.join(PARENT_DIR, "static", "group_uploads")
    room_folder = os.path.join(group_uploads, secure_filename(secure_id))

    room_data = await get_data_direct(secure_id)
    room_record = room_data[0] if room_data else None

    # ルームに紐づくアップロードフォルダを削除
    if os.path.exists(room_folder):
        try:
            shutil.rmtree(room_folder)
        except Exception as e:
            logger.error(
                "アップロードフォルダの削除に失敗しました: %s. エラー: %s",
                room_folder,
                e,
            )

    # データベースから該当ルームのレコードを削除
    query = text("""
        DELETE FROM room WHERE room_id = :secure_id
    """)
    await execute_query(query, {"secure_id": secure_id})
    await group_ws_hub.close_room(secure_id, code=1001)
    await invalidate_cache_entry("get_data", secure_id)
    await invalidate_cache_entry("get_all")
    if room_record:
        await invalidate_cache_entry(
            "pich_room_id", room_record.get("id"), room_record.get("password")
        )


# 全てのデータを削除
async def all_remove():
    # 全ルーム情報を取得
    rooms = await get_all_direct()

    # グループアップロードフォルダのパス（group_app.py と同じパスを想定）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    group_uploads = os.path.join(PARENT_DIR, "static", "group_uploads")

    for room in rooms:
        room_id = room.get("room_id")
        if not room_id:
            continue

        # ルームに対応するアップロードフォルダの削除
        room_folder = os.path.join(group_uploads, secure_filename(room_id))
        if os.path.exists(room_folder):
            try:
                shutil.rmtree(room_folder)
            except Exception as e:
                logger.error(
                    "アップロードフォルダの削除に失敗しました: %s. エラー: %s",
                    room_folder,
                    e,
                )
        await group_ws_hub.close_room(room_id, code=1001)

    # 最後に、データベースから全ルームのレコードを削除
    query = text("DELETE FROM room")
    await execute_query(query)
    await invalidate_cache_prefix("pich_room_id")
    await invalidate_cache_prefix("get_data")
    await invalidate_cache_prefix("get_all")


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
