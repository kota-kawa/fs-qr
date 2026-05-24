import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
import logging

import log_config  # noqa: F401
from password_security import hash_password, verify_password
from database import execute_query
from cache_utils import (
    cache_data,
    invalidate_cache_entry,
    invalidate_cache_prefix,
    redis_client,
)
from settings import FSQR_UPLOAD_DIR, SECRET_KEY

# ログ設定
logger = logging.getLogger(__name__)

STATIC = FSQR_UPLOAD_DIR
EXPIRATION_CLEANUP_STATUS_KEY = "fsqr:expiration_cleanup:last_result"


def hash_share_token(share_token: str) -> str:
    secret = (SECRET_KEY or "").encode("utf-8")
    if secret:
        return hmac.new(secret, share_token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(share_token.encode("utf-8")).hexdigest()


# ファイルを保存
async def save_file(
    uid,
    id,
    password,
    secure_id,
    file_type="multiple",
    original_filename=None,
    retention_days=7,
    share_token=None,
):
    try:
        hashed_password = hash_password(password)
        share_token_hash = hash_share_token(share_token) if share_token else None
        query = text("""
            INSERT INTO fsqr (
                time, uuid, id, password, secure_id, share_token_hash,
                file_type, original_filename, retention_days
            )
            VALUES (
                NOW(), :uid, :id, :password, :secure_id, :share_token_hash,
                :file_type, :original_filename, :retention_days
            )
        """)
        await execute_query(
            query,
            {
                "uid": uid,
                "id": id,
                "password": hashed_password,
                "secure_id": secure_id,
                "share_token_hash": share_token_hash,
                "file_type": file_type,
                "original_filename": original_filename,
                "retention_days": retention_days,
            },
        )
        await invalidate_cache_entry(try_login, id, password)
        await invalidate_cache_entry(get_data_by_credentials, id, password)
        await invalidate_cache_entry(get_data, secure_id)
        if share_token:
            await invalidate_cache_entry(get_data_by_share_token, share_token)
        await invalidate_cache_entry(get_all)
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
@cache_data(ttl=60, strip_keys=("password",))
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


@cache_data(ttl=60, strip_keys=("password", "share_token_hash"))
async def get_data(secure_id):
    return await get_data_direct(secure_id)


@cache_data(ttl=60, strip_keys=("password", "share_token_hash"))
async def get_data_by_share_token(share_token):
    try:
        token_hash = hash_share_token(share_token)
        query = text("""
            SELECT * FROM fsqr WHERE share_token_hash = :share_token_hash
        """)
        result = await execute_query(
            query, {"share_token_hash": token_hash}, fetch=True
        )
        return result
    except Exception as e:
        logger.error(f"Failed to fetch data by share token: {e}")
        raise


# 全てのデータを取得する
@cache_data(ttl=300, strip_keys=("password", "share_token_hash"))
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
        from share_links import ServiceKey, revoke_resource_links

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
        await invalidate_cache_entry(get_data, secure_id)
        await invalidate_cache_entry(get_all)
        if record:
            await invalidate_cache_prefix(try_login)
            await invalidate_cache_prefix(get_data_by_credentials)
            await invalidate_cache_prefix(get_data_by_share_token)
        try:
            await revoke_resource_links(
                service_key=ServiceKey.FSQR, resource_id=secure_id
            )
        except Exception:
            logger.warning(
                "Failed to revoke FSQR share links: secure_id=%s",
                secure_id,
                exc_info=True,
            )
    except Exception as e:
        logger.error(f"Failed to remove data: {e}")
        raise


# 全てのデータを削除
async def all_remove():
    try:
        from share_links import ServiceKey, revoke_resource_links

        rows = await get_all_direct()
        query = text("""
            DELETE FROM fsqr
        """)
        await execute_query(query)
        for row in rows:
            secure_id = row.get("secure_id")
            if secure_id:
                await revoke_resource_links(
                    service_key=ServiceKey.FSQR, resource_id=secure_id
                )
        await invalidate_cache_prefix(try_login)
        await invalidate_cache_prefix(get_data_by_credentials)
        await invalidate_cache_prefix(get_data_by_share_token)
        await invalidate_cache_prefix(get_data)
        await invalidate_cache_prefix(get_all)
    except Exception as e:
        logger.error(f"Failed to remove all data: {e}")
        raise


async def remove_expired_files():
    stats = {
        "checked": 0,
        "removed": 0,
        "failed": 0,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        query = text(
            """
            SELECT secure_id
            FROM fsqr
            WHERE DATE_ADD(time, INTERVAL retention_days DAY) <= NOW()
            """
        )
        expired_records = await execute_query(query, fetch=True)
        stats["checked"] = len(expired_records)
        for record in expired_records:
            secure_id = record.get("secure_id")
            if not secure_id:
                continue
            try:
                await remove_data(secure_id)
                stats["removed"] += 1
                logger.info(f"Expired record removed: {secure_id}")
            except Exception:
                stats["failed"] += 1
                logger.exception("Failed to remove expired FSQR record: %s", secure_id)
        await record_expiration_cleanup_status(stats)
        if stats["failed"]:
            raise RuntimeError(
                f"Failed to remove {stats['failed']} expired FSQR record(s)"
            )
        return stats
    except Exception:
        if not stats["failed"]:
            stats["failed"] = 1
        await record_expiration_cleanup_status(stats)
        logger.exception("Failed to remove expired files")
        raise


async def record_expiration_cleanup_status(stats):
    try:
        await redis_client.setex(
            EXPIRATION_CLEANUP_STATUS_KEY,
            7 * 86400,
            json.dumps(stats, ensure_ascii=False, sort_keys=True),
        )
    except Exception:
        logger.warning("Failed to record FSQR expiration cleanup status", exc_info=True)


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
