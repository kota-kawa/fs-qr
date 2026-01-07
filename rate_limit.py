"""Redis-based rate limiting for authentication-like endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import redis.asyncio as redis

from settings import REDIS_URL

logger = logging.getLogger(__name__)

THRESHOLDS = (
    (50, timedelta(days=1), "1日"),
    (10, timedelta(minutes=30), "30分"),
)

SCOPE_QR = "qr"
SCOPE_NOTE = "note"
SCOPE_GROUP = "group"

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        # decode_responses=True so we get strings instead of bytes
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def check_rate_limit(scope: str, ip: str) -> Tuple[bool, Optional[datetime], Optional[str]]:
    """Check whether the given IP is currently blocked for the scope."""
    r = get_redis_client()
    block_key = f"rate_limit:{scope}:{ip}:block"

    try:
        block_label = await r.get(block_key)
        if block_label:
            ttl = await r.ttl(block_key)
            # ttl: -2 (missing), -1 (no expiry), >=0 (seconds)
            if ttl > 0:
                block_until = datetime.utcnow() + timedelta(seconds=ttl)
                return False, block_until, block_label
    except Exception as e:
        logger.error(f"Redis error in check_rate_limit: {e}")
        # Fail open if Redis is down? Or blocked?
        # Let's assume fail open to avoid service disruption, but log error.
        return True, None, None

    return True, None, None


async def register_failure(scope: str, ip: str) -> Tuple[Optional[datetime], Optional[str]]:
    """Record a failed attempt. Returns block information when a block is active."""
    r = get_redis_client()
    count_key = f"rate_limit:{scope}:{ip}:count"
    block_key = f"rate_limit:{scope}:{ip}:block"

    try:
        # Check if already blocked
        block_label = await r.get(block_key)
        if block_label:
            ttl = await r.ttl(block_key)
            if ttl > 0:
                return datetime.utcnow() + timedelta(seconds=ttl), block_label

        # Increment count
        count = await r.incr(count_key)
        
        # Set a long expiry for the count itself so it doesn't leak forever
        # (Only set it on first increment to avoid resetting TTL constantly, 
        # though incr doesn't change TTL, so we check if count==1 or just ttl check)
        if count == 1:
            # Keep count for 30 days max if inactive
            await r.expire(count_key, 30 * 86400)

        now = datetime.utcnow()
        for threshold, duration, label in THRESHOLDS:
            if count >= threshold:
                # Block!
                await r.set(block_key, label, ex=duration)
                # Reset count so users start fresh after block expires
                await r.delete(count_key)
                return now + duration, label

    except Exception as e:
        logger.error(f"Redis error in register_failure: {e}")
        return None, None

    return None, None


async def register_success(scope: str, ip: str) -> None:
    """Reset counters after a successful attempt."""
    r = get_redis_client()
    count_key = f"rate_limit:{scope}:{ip}:count"
    block_key = f"rate_limit:{scope}:{ip}:block"
    try:
        await r.delete(count_key, block_key)
    except Exception as e:
        logger.error(f"Redis error in register_success: {e}")


def get_block_message(label: Optional[str]) -> str:
    if label == "1日":
        return "一定回数以上の失敗があったため、この機能へのアクセスを1日間ブロックしています。時間をおいて再度お試しください。"
    if label == "30分":
        return "一定回数以上の失敗があったため、この機能へのアクセスを30分間ブロックしています。時間をおいて再度お試しください。"
    return "一定回数以上の失敗があったため、この機能へのアクセスを制限しています。時間をおいて再度お試しください。"


def get_client_ip(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if getattr(request, "client", None) and request.client:
        return request.client.host
    return "unknown"