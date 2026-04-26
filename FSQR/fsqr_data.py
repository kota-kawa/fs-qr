import os
from typing import Optional
from sqlalchemy import text
import logging

import log_config  # noqa: F401
from password_security import hash_password, verify_password
from database import execute_query
from cache_utils import cache_data, invalidate_cache_entry, invalidate_cache_prefix

# ログ設定
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC = os.path.join(BASE_DIR, "static", "upload")


# ファイルを保存
async def save_file(
    uid,
    id,
    password,
    secure_id,
    file_type="multiple",
    original_filename=None,
    retention_days=7,
):
    try:
        hashed_password = hash_password(password)
        query = text("""
            INSERT INTO fsqr (time, uuid, id, password, secure_id, file_type, original_filename, retention_days)
            VALUES (NOW(), :uid, :id, :password, :secure_id, :file_type, :original_filename, :retention_days)
        """)
        await execute_query(
            query,
            {
                "uid": uid,
                "id": id,
                "password": hashed_password,
                "secure_id": secure_id,
                "file_type": file_type,
                "original_filename": original_filename,
                "retention_days": retention_days,
            },
        )
        await invalidate_cache_entry("try_login", id, password)
        await invalidate_cache_entry("get_data_by_credentials", id, password)
        await invalidate_cache_entry("get_data", secure_id)
        await invalidate_cache_entry("get_all")
        logger.info("File saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise


# ログイン処理
@cache_data(ttl=60)
async def try_login(id, password) -> Optional[str]:
    try:
        record = await _find_record_by_credentials(id, password)
        if record:
            logger.info("Login successful.")
            return record["secure_id"]
        logger.warning("Login failed: Invalid credentials.")
        return None
    except Exception as e:
        logger.error(f"Login attempt failed: {e}")
        raise


# 資格情報でデータを取得
@cache_data(ttl=60)
async def get_data_by_credentials(id, password):
    try:
        record = await _find_record_by_credentials(id, password)
        return [record] if record else []
    except Exception as e:
        logger.error(f"Failed to fetch data by credentials: {e}")
        raise


# データベースから任意のIDのデータを取り出す
async def get_data_direct(secure_id):
    try:
        query = text("""
            SELECT * FROM fsqr WHERE secure_id = :secure_id
        """)
        result = await execute_query(query, {"secure_id": secure_id}, fetch=True)
        return result
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        raise


@cache_data(ttl=60)
async def get_data(secure_id):
    return await get_data_direct(secure_id)


# 全てのデータを取得する
@cache_data(ttl=300)
async def get_all():
    return await get_all_direct()


async def get_all_direct():
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
        data = await get_data_direct(secure_id)
        file_type = "multiple"  # デフォルト値
        record = data[0] if data else None
        if data:
            file_type = data[0].get("file_type", "multiple")

        # ファイルタイプに応じて削除するファイルを決定
        if file_type == "single":
            paths = [os.path.join(STATIC, f"{secure_id}.enc")]
        else:
            paths = [os.path.join(STATIC, f"{secure_id}.zip")]

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
        await invalidate_cache_entry("get_data", secure_id)
        await invalidate_cache_entry("get_all")
        if record:
            await invalidate_cache_prefix("try_login")
            await invalidate_cache_prefix("get_data_by_credentials")
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
        await invalidate_cache_prefix("try_login")
        await invalidate_cache_prefix("get_data_by_credentials")
        await invalidate_cache_prefix("get_data")
        await invalidate_cache_prefix("get_all")
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


async def _find_record_by_credentials(id_val: str, password: str):
    query = text("""
        SELECT * FROM fsqr WHERE id = :id
    """)
    rows = await execute_query(query, {"id": id_val}, fetch=True)
    for row in rows:
        stored_password = row.get("password")
        if not verify_password(stored_password, password):
            continue
        return row
    return None
