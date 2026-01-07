import asyncio
import json
import logging
import os
import uuid

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INSTANCE_ID = uuid.uuid4().hex

_redis_client = None
_pubsub_task = None


class RoomHub:
    def __init__(self):
        self._rooms = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id, websocket):
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(websocket)

    async def disconnect(self, room_id, websocket):
        async with self._lock:
            sockets = self._rooms.get(room_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._rooms.pop(room_id, None)

    async def broadcast(self, room_id, payload, exclude=None):
        async with self._lock:
            sockets = list(self._rooms.get(room_id, set()))

        if not sockets:
            return

        dead = []
        for ws in sockets:
            if exclude is not None and ws is exclude:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                active = self._rooms.get(room_id)
                if not active:
                    return
                for ws in dead:
                    active.discard(ws)
                if not active:
                    self._rooms.pop(room_id, None)


hub = RoomHub()


def _decode_channel_room_id(channel_name):
    if not channel_name:
        return None
    if isinstance(channel_name, bytes):
        channel_name = channel_name.decode("utf-8")
    if channel_name.startswith("note:room:"):
        return channel_name.split("note:room:", 1)[1]
    return None


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable (%s); realtime will run single-process", exc)
        _redis_client = None
        return None
    _redis_client = client
    return _redis_client


async def publish_room_update(room_id, payload):
    client = await get_redis()
    if not client:
        return False
    await ensure_pubsub()
    message = {
        "room_id": room_id,
        "payload": payload,
        "source": INSTANCE_ID,
    }
    try:
        await client.publish(f"note:room:{room_id}", json.dumps(message))
        return True
    except Exception as exc:
        logger.warning("Failed to publish redis update: %s", exc)
        return False


async def _pubsub_loop():
    client = await get_redis()
    if not client:
        return

    pubsub = client.pubsub()
    await pubsub.psubscribe("note:room:*")
    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") not in ("pmessage", "message"):
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                payload = json.loads(data)
            except Exception:
                continue
            if payload.get("source") == INSTANCE_ID:
                continue
            room_id = payload.get("room_id")
            if not room_id:
                channel_room = _decode_channel_room_id(message.get("channel"))
                room_id = channel_room
            room_payload = payload.get("payload")
            if room_id and room_payload:
                await hub.broadcast(room_id, room_payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Redis pubsub loop stopped: %s", exc)
    finally:
        try:
            await pubsub.close()
        except Exception:
            pass


async def startup():
    await ensure_pubsub()


async def ensure_pubsub():
    global _pubsub_task
    if _pubsub_task is None or _pubsub_task.done():
        client = await get_redis()
        if client is None:
            return
        _pubsub_task = asyncio.create_task(_pubsub_loop())


async def shutdown():
    global _pubsub_task, _redis_client
    if _pubsub_task is not None:
        _pubsub_task.cancel()
        _pubsub_task = None
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
