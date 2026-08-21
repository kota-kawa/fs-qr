import asyncio
import json
import logging
import uuid

import redis.asyncio as redis

from settings import REDIS_URL

logger = logging.getLogger(__name__)

INSTANCE_ID = uuid.uuid4().hex
CHANNEL_PREFIX = "group:room:"
CHANNEL_PATTERN = f"{CHANNEL_PREFIX}*"
ROOM_CONNECTIONS_KEY_PREFIX = "group:ws:room"
INSTANCE_CONNECTIONS_KEY = f"group:ws:instance:{INSTANCE_ID}:connections"
CONNECTION_TTL_SECONDS = 3600
PUBSUB_RETRY_SECONDS = 5

_redis_client = None
_pubsub_task = None
_pubsub_stop_event = None


class GroupRoomHub:
    """WebSocket objects stay local; Redis shares room events across workers."""

    def __init__(self):
        # WebSocket はプロセスローカルに保持し、Redis に直列化しない。
        # Keep WebSocket objects process-local instead of serializing them in Redis.
        # room_id -> {websocket: connection_id}
        self._rooms = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id, websocket):
        await websocket.accept()
        connection_id = uuid.uuid4().hex
        async with self._lock:
            self._rooms.setdefault(room_id, {})[websocket] = connection_id
        await self._register_connection(room_id, connection_id)
        ensure_pubsub()

    async def disconnect(self, room_id, websocket):
        connection_id = await self._remove_connection(room_id, websocket)
        if connection_id:
            await self._unregister_connection(room_id, connection_id)

    async def broadcast(self, room_id, payload):
        async with self._lock:
            sockets = list(self._rooms.get(room_id, {}).keys())

        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                await self.disconnect(room_id, websocket)

    async def close_room(self, room_id, code=1001):
        async with self._lock:
            connections = self._rooms.pop(room_id, {})

        for websocket, connection_id in connections.items():
            try:
                await websocket.close(code=code)
            except Exception as exc:
                logger.debug(
                    "Failed to close Group websocket for room %s: %s", room_id, exc
                )
            await self._unregister_connection(room_id, connection_id)

    async def disconnect_all(self):
        async with self._lock:
            connections_by_room = self._rooms
            self._rooms = {}

        for room_id, connections in connections_by_room.items():
            for connection_id in connections.values():
                await self._unregister_connection(room_id, connection_id)
        await self._clear_instance_connections()

    async def _remove_connection(self, room_id, websocket):
        async with self._lock:
            connections = self._rooms.get(room_id)
            if not connections:
                return None
            connection_id = connections.pop(websocket, None)
            if not connections:
                self._rooms.pop(room_id, None)
            return connection_id

    async def _register_connection(self, room_id, connection_id):
        client = await get_redis()
        if not client:
            return

        member = _connection_member(room_id, connection_id)
        room_key = _room_connections_key(room_id)
        try:
            pipeline = client.pipeline(transaction=True)
            pipeline.sadd(room_key, member)
            pipeline.expire(room_key, CONNECTION_TTL_SECONDS)
            pipeline.sadd(INSTANCE_CONNECTIONS_KEY, member)
            pipeline.expire(INSTANCE_CONNECTIONS_KEY, CONNECTION_TTL_SECONDS)
            await pipeline.execute()
        except Exception as exc:
            logger.warning(
                "Failed to register Group websocket connection in Redis: %s", exc
            )

    async def _unregister_connection(self, room_id, connection_id):
        client = await get_redis()
        if not client:
            return

        member = _connection_member(room_id, connection_id)
        room_key = _room_connections_key(room_id)
        try:
            pipeline = client.pipeline(transaction=True)
            pipeline.srem(room_key, member)
            pipeline.srem(INSTANCE_CONNECTIONS_KEY, member)
            pipeline.scard(room_key)
            pipeline.scard(INSTANCE_CONNECTIONS_KEY)
            _, _, room_count, instance_count = await pipeline.execute()
            if room_count == 0:
                await client.delete(room_key)
            if instance_count == 0:
                await client.delete(INSTANCE_CONNECTIONS_KEY)
        except Exception as exc:
            logger.warning(
                "Failed to unregister Group websocket connection in Redis: %s", exc
            )

    async def _clear_instance_connections(self):
        # 異常終了後に残ったこの instance の接続記録だけを掃除する。
        # Remove only this instance's stale connection records after an unclean exit.
        client = await get_redis()
        if not client:
            return

        try:
            members = await client.smembers(INSTANCE_CONNECTIONS_KEY)
            if not members:
                await client.delete(INSTANCE_CONNECTIONS_KEY)
                return

            room_ids = set()
            pipeline = client.pipeline(transaction=True)
            for member in members:
                _, room_id, _ = _parse_connection_member(member)
                if room_id:
                    room_ids.add(room_id)
                    pipeline.srem(_room_connections_key(room_id), member)
            pipeline.delete(INSTANCE_CONNECTIONS_KEY)
            await pipeline.execute()

            for room_id in room_ids:
                room_key = _room_connections_key(room_id)
                if await client.scard(room_key) == 0:
                    await client.delete(room_key)
        except Exception as exc:
            logger.warning(
                "Failed to clear Group websocket connections in Redis: %s", exc
            )


hub = GroupRoomHub()


def _room_connections_key(room_id):
    return f"{ROOM_CONNECTIONS_KEY_PREFIX}:{room_id}:connections"


def _connection_member(room_id, connection_id):
    return f"{INSTANCE_ID}:{room_id}:{connection_id}"


def _parse_connection_member(member):
    if isinstance(member, bytes):
        member = member.decode("utf-8")
    parts = str(member).split(":", 2)
    if len(parts) != 3:
        return None, None, None
    return parts[0], parts[1], parts[2]


def _channel_name(room_id):
    return f"{CHANNEL_PREFIX}{room_id}"


def _decode_channel_room_id(channel_name):
    if isinstance(channel_name, bytes):
        channel_name = channel_name.decode("utf-8")
    if not isinstance(channel_name, str) or not channel_name.startswith(CHANNEL_PREFIX):
        return None
    room_id = channel_name.removeprefix(CHANNEL_PREFIX)
    return room_id or None


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable; Group realtime runs single-process: %s", exc)
        return None
    _redis_client = client
    return client


async def notify_group_files_updated(room_id):
    payload = {"type": "files_updated"}
    await hub.broadcast(room_id, payload)
    return await _publish_room_event(room_id, payload)


async def notify_group_room_closed(room_id, code=1001):
    payload = {"type": "room_closed"}
    await hub.broadcast(room_id, payload)
    await hub.close_room(room_id, code=code)
    return await _publish_room_event(room_id, payload)


async def _publish_room_event(room_id, payload):
    ensure_pubsub()
    client = await get_redis()
    if not client:
        return False
    message = {"room_id": room_id, "payload": payload, "source": INSTANCE_ID}
    try:
        await client.publish(_channel_name(room_id), json.dumps(message))
        return True
    except Exception as exc:
        logger.warning("Failed to publish Group realtime update: %s", exc)
        return False


async def _pubsub_loop():
    client = await get_redis()
    if not client:
        return

    pubsub = client.pubsub()
    try:
        await pubsub.psubscribe(CHANNEL_PATTERN)
        async for message in pubsub.listen():
            if message is None or message.get("type") not in {"message", "pmessage"}:
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                event = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                continue
            if event.get("source") == INSTANCE_ID:
                continue
            room_id = event.get("room_id") or _decode_channel_room_id(
                message.get("channel")
            )
            payload = event.get("payload")
            if not room_id or not isinstance(payload, dict):
                continue
            if payload.get("type") == "files_updated":
                await hub.broadcast(room_id, {"type": "files_updated"})
            elif payload.get("type") == "room_closed":
                await hub.broadcast(room_id, {"type": "room_closed"})
                await hub.close_room(room_id, code=1001)
    finally:
        try:
            await pubsub.close()
        except Exception:  # noqa: S110
            pass


async def _pubsub_supervisor():
    while _pubsub_stop_event is not None and not _pubsub_stop_event.is_set():
        try:
            await _pubsub_loop()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Group Redis pubsub loop stopped: %s", exc)
        try:
            await asyncio.wait_for(
                _pubsub_stop_event.wait(), timeout=PUBSUB_RETRY_SECONDS
            )
        except TimeoutError:
            continue


def ensure_pubsub():
    global _pubsub_task, _pubsub_stop_event
    if _pubsub_task is None or _pubsub_task.done():
        _pubsub_stop_event = asyncio.Event()
        _pubsub_task = asyncio.create_task(_pubsub_supervisor())


async def startup():
    await hub._clear_instance_connections()
    ensure_pubsub()


async def shutdown():
    global _pubsub_task, _pubsub_stop_event, _redis_client
    await hub.disconnect_all()
    if _pubsub_stop_event is not None:
        _pubsub_stop_event.set()
    if _pubsub_task is not None:
        _pubsub_task.cancel()
        try:
            await _pubsub_task
        except asyncio.CancelledError:
            pass
        _pubsub_task = None
    _pubsub_stop_event = None
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:  # noqa: S110
            pass
        _redis_client = None
