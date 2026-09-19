import asyncio
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
from room_repository import revoke_room_links
from share_links import ServiceKey
from settings import FSQR_UPLOAD_DIR, SECRET_KEY

# ログ設定
logger = logging.getLogger(__name__)

STATIC = FSQR_UPLOAD_DIR
EXPIRATION_CLEANUP_STATUS_KEY = "fsqr:expiration_cleanup:last_result"


def _clear_storage_files() -> None:
    """Remove FSQR regular files without traversing outside its storage root."""

    if not os.path.isdir(STATIC):
        return
    for entry in os.scandir(STATIC):
        # FSQR stores flat .enc/.zip payloads.  Leave unexpected directories
        # alone rather than recursively deleting an operator-configured path.
        if entry.is_file(follow_symlinks=False) or entry.is_symlink():
            os.unlink(entry.path)


def hash_share_token(share_token: str) -> str:
    return hmac.new(
        _secret_key_bytes(), share_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def hash_password_lookup(id_val: str, password: str) -> str:
    payload = f"fsqr:{id_val}:{password}".encode("utf-8")
    return hmac.new(_secret_key_bytes(), payload, hashlib.sha256).hexdigest()


def _secret_key_bytes() -> bytes:
    if not isinstance(SECRET_KEY, str) or not SECRET_KEY.strip():
        raise RuntimeError("SECRET_KEY is required for FSQR credentials")
    return SECRET_KEY.encode("utf-8")


# ファイルを保存
async def save_file(
    uid,
    id,
    password,
    secure_id,
    file_type="multiple",
    original_filename=None,
    retention_hours=24,
    share_token=None,
    encryption_mode="password",
):
    try:
        if encryption_mode not in {"password", "raw"}:
            raise ValueError("Unsupported FSQR encryption mode")
        hashed_password = hash_password(password)
        password_lookup_hash = hash_password_lookup(id, password)
        share_token_hash = hash_share_token(share_token) if share_token else None
        query = text("""
            INSERT INTO fsqr (
                time, uuid, id, password, password_lookup_hash,
                secure_id, share_token_hash, file_type, original_filename,
                retention_days, retention_hours, expires_at, encryption_mode, status
            )
            VALUES (
                NOW(), :uid, :id, :password, :password_lookup_hash,
                :secure_id, :share_token_hash, :file_type, :original_filename,
                1, :retention_hours, DATE_ADD(NOW(), INTERVAL :retention_hours HOUR),
                :encryption_mode, 'active'
            )
        """)
        await execute_query(
            query,
            {
                "uid": uid,
                "id": id,
                "password": hashed_password,
                "password_lookup_hash": password_lookup_hash,
                "secure_id": secure_id,
                "share_token_hash": share_token_hash,
                "file_type": file_type,
                "original_filename": original_filename,
                "retention_hours": retention_hours,
                "encryption_mode": encryption_mode,
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
@cache_data(ttl=60, key_prefix="room.fsqr.login")
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
@cache_data(
    ttl=60,
    key_prefix="room.fsqr.credentials",
    strip_keys=("password", "password_lookup_hash"),
)
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


@cache_data(
    ttl=60,
    key_prefix="room.fsqr.meta",
    strip_keys=("password", "password_lookup_hash", "share_token_hash"),
)
async def get_data(secure_id):
    return await get_data_direct(secure_id)


@cache_data(
    ttl=60,
    key_prefix="room.fsqr.by_share_token",
    strip_keys=("password", "password_lookup_hash", "share_token_hash"),
)
async def get_data_by_share_token(share_token):
    try:
        token_hash = hash_share_token(share_token)
        query = text("""
            SELECT * FROM fsqr
            WHERE share_token_hash = :share_token_hash AND status = 'active'
        """)
        result = await execute_query(
            query, {"share_token_hash": token_hash}, fetch=True
        )
        return result
    except Exception as e:
        logger.error(f"Failed to fetch data by share token: {e}")
        raise


# 全てのデータを取得する
@cache_data(
    ttl=300,
    key_prefix="room.fsqr.all",
    strip_keys=("password", "password_lookup_hash", "share_token_hash"),
)
async def get_all():
    return await get_all_direct()


async def get_all_direct():
    try:
        query = text("""
            SELECT * FROM fsqr WHERE status = 'active' ORDER BY suji DESC
        """)
        return await execute_query(query, fetch=True)
    except Exception as e:
        logger.error(f"Failed to fetch all data: {e}")
        raise


# アップロードされたファイルとメタ情報の削除
async def remove_data(secure_id):
    try:
        # まずデータベースからファイル情報を取得する。deleting を含めることで
        # ファイル削除後にプロセスが落ちても、次回の掃除で再試行できる。
        data = await get_data_direct(secure_id)
        if not data:
            return False
        file_type = "multiple"  # デフォルト値
        record = data[0] if data else None
        if record.get("status", "active") == "deleted":
            return True
        if data:
            file_type = data[0].get("file_type", "multiple")

        mark_deleting_query = text("""
            UPDATE fsqr
            SET status = 'deleting', deleted_at = NOW()
            WHERE secure_id = :secure_id AND status IN ('active', 'deleting')
        """)
        await execute_query(mark_deleting_query, {"secure_id": secure_id})

        # ファイルタイプに応じて削除するファイルを決定
        if file_type == "single":
            paths = [os.path.join(STATIC, f"{secure_id}.enc")]
        else:
            paths = [os.path.join(STATIC, f"{secure_id}.zip")]

        def _delete_files():
            for file_path in paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
                else:
                    logger.warning(f"File not found: {file_path}")

        await asyncio.to_thread(_delete_files)

        query = text("""
            UPDATE fsqr
            SET status = 'deleted', deleted_at = NOW()
            WHERE secure_id = :secure_id AND status = 'deleting'
        """)
        await execute_query(query, {"secure_id": secure_id})

        # DB削除後の副作用を並列実行して高速化
        async def _invalidate_caches():
            await invalidate_cache_entry(get_data, secure_id)
            await invalidate_cache_entry(get_all)
            if record:
                await invalidate_cache_prefix(try_login)
                await invalidate_cache_prefix(get_data_by_credentials)
                await invalidate_cache_prefix(get_data_by_share_token)

        async def _revoke_links():
            await revoke_room_links(ServiceKey.FSQR, secure_id, logger=logger)

        await asyncio.gather(_invalidate_caches(), _revoke_links())
        return True
    except Exception as e:
        logger.error(f"Failed to remove data: {e}")
        raise


# 全てのデータを削除
async def all_remove():
    try:
        query = text("""
            SELECT secure_id
            FROM fsqr
            WHERE status IN ('active', 'deleting')
            ORDER BY suji DESC
        """)
        rows = await execute_query(query, fetch=True)
        failed_ids = []
        for row in rows:
            secure_id = row.get("secure_id")
            if secure_id:
                try:
                    if not await remove_data(secure_id):
                        failed_ids.append(secure_id)
                except Exception:
                    failed_ids.append(secure_id)
                    logger.exception("Failed to remove FSQR record: %s", secure_id)
        if failed_ids:
            raise RuntimeError(
                "Failed to remove FSQR records: " + ", ".join(failed_ids)
            )

        # Clear orphan payloads only after every metadata row reached the
        # deleted state.  This preserves recoverability when one delete fails.
        await asyncio.to_thread(_clear_storage_files)
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
        query = text("""
            SELECT secure_id
            FROM fsqr
            WHERE (status = 'active' AND expires_at <= NOW())
               OR status = 'deleting'
            """)
        expired_records = await execute_query(query, fetch=True)
        stats["checked"] = len(expired_records)
        for record in expired_records:
            secure_id = record.get("secure_id")
            if not secure_id:
                continue
            try:
                if not await remove_data(secure_id):
                    raise RuntimeError("record is not removable")
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
    lookup_hash = hash_password_lookup(id_val, password)
    query = text("""
        SELECT * FROM fsqr
        WHERE id = :id
          AND password_lookup_hash = :password_lookup_hash
          AND status = 'active'
        LIMIT 1
    """)
    rows = await execute_query(
        query,
        {"id": id_val, "password_lookup_hash": lookup_hash},
        fetch=True,
    )
    if rows:
        row = rows[0]
        if verify_password(row.get("password"), password):
            return row

    legacy_rows = await execute_query(
        text("""
            SELECT * FROM fsqr
            WHERE id = :id
              AND password_lookup_hash IS NULL
              AND status = 'active'
        """),
        {"id": id_val},
        fetch=True,
    )
    for row in legacy_rows:
        if not verify_password(row.get("password"), password):
            continue
        return row
    return None
