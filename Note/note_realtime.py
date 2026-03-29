import asyncio
import json
import logging
import os
import uuid

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INSTANCE_ID = uuid.uuid4().hex
ROOM_CONNECTIONS_KEY_PREFIX = "note:ws:room"
INSTANCE_CONNECTIONS_KEY = f"note:ws:instance:{INSTANCE_ID}:connections"

_redis_client = None
_pubsub_task = None


class RoomHub:
    def __init__(self):
        # room_id -> {websocket: connection_id}
        self._rooms = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id, websocket):
        await websocket.accept()
        connection_id = uuid.uuid4().hex
        async with self._lock:
            self._rooms.setdefault(room_id, {})[websocket] = connection_id
        await self._register_connection(room_id, connection_id)

    async def disconnect(self, room_id, websocket):
        connection_id = None
        async with self._lock:
            sockets = self._rooms.get(room_id)
            if not sockets:
                return
            connection_id = sockets.pop(websocket, None)
            if not sockets:
                self._rooms.pop(room_id, None)
        if connection_id:
            await self._unregister_connection(room_id, connection_id)

    async def broadcast(self, room_id, payload, exclude=None):
        async with self._lock:
            sockets = list(self._rooms.get(room_id, {}).keys())

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
            dead_connection_ids = []
            async with self._lock:
                active = self._rooms.get(room_id)
                if not active:
                    return
                for ws in dead:
                    connection_id = active.pop(ws, None)
                    if connection_id:
                        dead_connection_ids.append(connection_id)
                if not active:
                    self._rooms.pop(room_id, None)
            for connection_id in dead_connection_ids:
                await self._unregister_connection(room_id, connection_id)

    async def disconnect_all(self):
        async with self._lock:
            snapshot = {
                room_id: list(connections.values())
                for room_id, connections in self._rooms.items()
            }
            self._rooms.clear()

        for room_id, connection_ids in snapshot.items():
            for connection_id in connection_ids:
                await self._unregister_connection(room_id, connection_id)

        await self._clear_instance_connections()

    async def _register_connection(self, room_id, connection_id):
        client = await get_redis()
        if not client:
            return

        member = _connection_member(room_id, connection_id)
        room_key = _room_connections_key(room_id)
        instance_key = _instance_connections_key()
        try:
            pipeline = client.pipeline(transaction=True)
            pipeline.sadd(room_key, member)
            pipeline.sadd(instance_key, member)
            await pipeline.execute()
        except Exception as exc:
            logger.warning("Failed to register websocket connection in Redis: %s", exc)

    async def _unregister_connection(self, room_id, connection_id):
        client = await get_redis()
        if not client:
            return

        member = _connection_member(room_id, connection_id)
        room_key = _room_connections_key(room_id)
        instance_key = _instance_connections_key()
        try:
            pipeline = client.pipeline(transaction=True)
            pipeline.srem(room_key, member)
            pipeline.srem(instance_key, member)
            pipeline.scard(room_key)
            pipeline.scard(instance_key)
            room_removed, instance_removed, room_count, instance_count = (
                await pipeline.execute()
            )
            if room_removed and room_count == 0:
                await client.delete(room_key)
            if instance_removed and instance_count == 0:
                await client.delete(instance_key)
        except Exception as exc:
            logger.warning("Failed to unregister websocket connection in Redis: %s", exc)

    async def _clear_instance_connections(self):
        client = await get_redis()
        if not client:
            return

        instance_key = _instance_connections_key()
        try:
            members = await client.smembers(instance_key)
            if not members:
                await client.delete(instance_key)
                return

            room_ids = set()
            pipeline = client.pipeline(transaction=True)
            for member in members:
                _, room_id, _ = _parse_connection_member(member)
                if room_id:
                    room_ids.add(room_id)
                    pipeline.srem(_room_connections_key(room_id), member)
            pipeline.delete(instance_key)
            await pipeline.execute()

            for room_id in room_ids:
                room_key = _room_connections_key(room_id)
                if await client.scard(room_key) == 0:
                    await client.delete(room_key)
        except Exception as exc:
            logger.warning("Failed to clear instance websocket connections: %s", exc)


hub = RoomHub()


def _room_connections_key(room_id):
    return f"{ROOM_CONNECTIONS_KEY_PREFIX}:{room_id}:connections"


def _instance_connections_key():
    return INSTANCE_CONNECTIONS_KEY


def _connection_member(room_id, connection_id):
    return f"{INSTANCE_ID}:{room_id}:{connection_id}"


def _parse_connection_member(member):
    if isinstance(member, bytes):
        member = member.decode("utf-8")
    parts = str(member).split(":", 2)
    if len(parts) != 3:
        return None, None, None
    return parts[0], parts[1], parts[2]


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
    await hub._clear_instance_connections()
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
    await hub.disconnect_all()
    if _pubsub_task is not None:
        _pubsub_task.cancel()
        try:
            await _pubsub_task
        except asyncio.CancelledError:
            pass
        _pubsub_task = None
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
