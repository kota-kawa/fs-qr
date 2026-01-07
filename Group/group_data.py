import asyncio
import os
import shutil
import logging
import log_config
from sqlalchemy import text
from werkzeug.utils import secure_filename
from database import db_session, is_retryable_db_error, reset_db_connection
from cache_utils import cache_data

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, 'static/qrcode')
STATIC = os.path.join(BASE_DIR, 'static/upload')

# データベースクエリの共通実行関数
async def execute_query(query, params=None, fetch=False, retries=2):
    for attempt in range(retries + 1):
        try:
            result = await db_session.execute(query, params or {})
            if fetch:
                return result.mappings().all()
            await db_session.commit()
            return None
        except Exception as e:
            if is_retryable_db_error(e) and attempt < retries:
                logger.warning("Database connection lost, retrying (%s/%s)", attempt + 1, retries)
                await reset_db_connection()
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            logger.error("Database query failed: %s", e)
            try:
                await db_session.rollback()
            except Exception:
                pass
            raise

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

# ログイン処理
async def pich_room_id_direct(id, password):
    query = text("""
        SELECT room_id FROM room WHERE id = :id AND password = :password
    """)
    result = await execute_query(query, {"id": id, "password": password}, fetch=True)
    return result[0]["room_id"] if result else False


@cache_data(ttl=60)
async def pich_room_id(id, password):
    return await pich_room_id_direct(id, password)

# データベースから任意のIDのデータを取り出す
async def get_data_direct(secure_id):
    query = text("""
        SELECT * FROM room WHERE room_id = :secure_id
    """)
    result = await execute_query(query, {"secure_id": secure_id}, fetch=True)
    return result if result else False


@cache_data(ttl=60)
async def get_data(secure_id):
    return await get_data_direct(secure_id)

# 全てのデータを取得する
@cache_data(ttl=300)
async def get_all():
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
    group_uploads = os.path.join(PARENT_DIR, 'static', 'group_uploads')
    room_folder = os.path.join(group_uploads, secure_filename(secure_id))
    
    # ルームに紐づくアップロードフォルダを削除
    if os.path.exists(room_folder):
        try:
            shutil.rmtree(room_folder)
        except Exception as e:
            logger.error("アップロードフォルダの削除に失敗しました: %s. エラー: %s", room_folder, e)

    # データベースから該当ルームのレコードを削除
    query = text("""
        DELETE FROM room WHERE room_id = :secure_id
    """)
    await execute_query(query, {"secure_id": secure_id})

# 全てのデータを削除
async def all_remove():
    # 全ルーム情報を取得（get_all() は全件取得を行います）
    rooms = await get_all()
    
    # グループアップロードフォルダのパス（group_app.py と同じパスを想定）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    group_uploads = os.path.join(PARENT_DIR, 'static', 'group_uploads')

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
                logger.error("アップロードフォルダの削除に失敗しました: %s. エラー: %s", room_folder, e)
    
    # 最後に、データベースから全ルームのレコードを削除
    query = text("DELETE FROM room")
    await execute_query(query)



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
