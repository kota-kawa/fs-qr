"""Redis control events for the Hocuspocus Note collaboration service."""

import json
import logging

import redis.asyncio as redis

from settings import REDIS_URL

logger = logging.getLogger(__name__)
_redis_client = None


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable for Note collaboration events: %s", exc)
        return None
    _redis_client = client
    return client


async def publish_room_expired(room_id: str) -> bool:
    """Notify Hocuspocus instances to close a room / 削除済みルームを閉じる。"""
    client = await get_redis()
    if not client:
        return False
    event = {"room_id": room_id, "payload": {"type": "room_expired"}}
    try:
        await client.publish(f"note:room:{room_id}", json.dumps(event))
        return True
    except Exception as exc:
        logger.warning("Failed to publish Note room expiration: %s", exc)
        return False


async def startup() -> None:
    await get_redis()


async def shutdown() -> None:
    global _redis_client
    if _redis_client is None:
        return
    try:
        await _redis_client.aclose()
    except AttributeError:  # pragma: no cover - Redis < 5 compatibility
        await _redis_client.close()
    finally:
        _redis_client = None
