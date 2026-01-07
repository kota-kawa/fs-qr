import os
from sqlalchemy import text
import logging
import log_config
from database import db_session

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC = os.path.join(BASE_DIR, 'static', 'upload')

# データベースクエリの共通実行関数
async def execute_query(query, params=None, fetch=False):
    try:
        if params:
            result = await db_session.execute(query, params)
        else:
            result = await db_session.execute(query)

        if fetch:
            return result.mappings().all()

        await db_session.commit()
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        await db_session.rollback()
        raise

# ファイルを保存
async def save_file(uid, id, password, secure_id, file_type='multiple', original_filename=None, retention_days=7):
    try:
        query = text("""
            INSERT INTO fsqr (time, uuid, id, password, secure_id, file_type, original_filename, retention_days)
            VALUES (NOW(), :uid, :id, :password, :secure_id, :file_type, :original_filename, :retention_days)
        """)
        await execute_query(query, {
            "uid": uid,
            "id": id,
            "password": password,
            "secure_id": secure_id,
            "file_type": file_type,
            "original_filename": original_filename,
            "retention_days": retention_days
        })
        logger.info("File saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise

# ログイン処理
async def try_login(id, password):
    try:
        query = text("""
            SELECT secure_id FROM fsqr WHERE id = :id AND password = :password
        """)
        result = await execute_query(query, {"id": id, "password": password}, fetch=True)
        if result:
            logger.info("Login successful.")
            return result[0]["secure_id"]
        else:
            logger.warning("Login failed: Invalid credentials.")
            return False
    except Exception as e:
        logger.error(f"Login attempt failed: {e}")
        raise

# 資格情報でデータを取得
async def get_data_by_credentials(id, password):
    try:
        query = text("""
            SELECT * FROM fsqr WHERE id = :id AND password = :password
        """)
        result = await execute_query(query, {"id": id, "password": password}, fetch=True)
        return result if result else False
    except Exception as e:
        logger.error(f"Failed to fetch data by credentials: {e}")
        raise

# データベースから任意のIDのデータを取り出す
async def get_data(secure_id):
    try:
        query = text("""
            SELECT * FROM fsqr WHERE secure_id = :secure_id
        """)
        result = await execute_query(query, {"secure_id": secure_id}, fetch=True)
        return result if result else False
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        raise

# 全てのデータを取得する
async def get_all():
    try:
        query = text("""
            SELECT * FROM fsqr ORDER BY suji DESC
        """)
        return await execute_query(query, fetch=True)
    except Exception as e:
        logger.error(f"Failed to fetch all data: {e}")
        raise

# アップロードされたファイルとメタ情報の削除
async def remove_data(secure_id):
    try:
        # まずデータベースからファイル情報を取得
        data = await get_data(secure_id)
        file_type = 'multiple'  # デフォルト値
        if data:
            file_type = data[0].get('file_type', 'multiple')
        
        # ファイルタイプに応じて削除するファイルを決定
        if file_type == 'single':
            paths = [
                os.path.join(STATIC, f"{secure_id}.enc")
            ]
        else:
            paths = [
                os.path.join(STATIC, f"{secure_id}.zip")
            ]

        for file_path in paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            else:
                logger.warning(f"File not found: {file_path}")

        query = text("""
            DELETE FROM fsqr WHERE secure_id = :secure_id
        """)
        await execute_query(query, {"secure_id": secure_id})
    except Exception as e:
        logger.error(f"Failed to remove data: {e}")
        raise

# 全てのデータを削除
async def all_remove():
    try:
        query = text("""
            DELETE FROM fsqr
        """)
        await execute_query(query)
    except Exception as e:
        logger.error(f"Failed to remove all data: {e}")
        raise

# 1週間以上経過したファイルレコードと関連ファイルを削除する関数
async def remove_expired_files():
    try:
        query = text(
            """
            SELECT secure_id
            FROM fsqr
            WHERE DATE_ADD(time, INTERVAL retention_days DAY) <= NOW()
            """
        )
        expired_records = await execute_query(query, fetch=True)
        for record in expired_records:
            secure_id = record.get("secure_id")
            if secure_id:
                await remove_data(secure_id)
                logger.info(f"Expired record removed: {secure_id}")
    except Exception as e:
        logger.error(f"Failed to remove expired files: {e}")
