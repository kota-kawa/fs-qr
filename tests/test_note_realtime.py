import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from Note import note_realtime


def test_room_hub_connect_disconnect_tracks_connections_in_redis():
    hub = note_realtime.RoomHub()
    websocket = MagicMock()
    websocket.accept = AsyncMock()

    register_pipeline = MagicMock()
    register_pipeline.execute = AsyncMock(return_value=[1, 1])

    unregister_pipeline = MagicMock()
    unregister_pipeline.execute = AsyncMock(return_value=[1, 1, 0, 0])

    redis_client = MagicMock()
    redis_client.pipeline.side_effect = [register_pipeline, unregister_pipeline]
    redis_client.delete = AsyncMock()

    room_id = "abc123"
    room_key = f"note:ws:room:{room_id}:connections"
    instance_key = f"note:ws:instance:{note_realtime.INSTANCE_ID}:connections"

    async def scenario():
        with patch(
            "Note.note_realtime.get_redis", new=AsyncMock(return_value=redis_client)
        ):
            await hub.connect(room_id, websocket)
            connection_id = hub._rooms[room_id][websocket]
            member = f"{note_realtime.INSTANCE_ID}:{room_id}:{connection_id}"

            await hub.disconnect(room_id, websocket)

            register_pipeline.sadd.assert_any_call(room_key, member)
            register_pipeline.sadd.assert_any_call(instance_key, member)

            unregister_pipeline.srem.assert_any_call(room_key, member)
            unregister_pipeline.srem.assert_any_call(instance_key, member)
            unregister_pipeline.scard.assert_any_call(room_key)
            unregister_pipeline.scard.assert_any_call(instance_key)

            redis_client.delete.assert_any_await(room_key)
            redis_client.delete.assert_any_await(instance_key)
            assert room_id not in hub._rooms

    asyncio.run(scenario())


def test_room_hub_disconnect_all_unregisters_every_connection():
    hub = note_realtime.RoomHub()
    ws1 = object()
    ws2 = object()
    hub._rooms = {"room1": {ws1: "conn1", ws2: "conn2"}}

    async def scenario():
        with (
            patch.object(
                hub, "_unregister_connection", new=AsyncMock()
            ) as unregister_mock,
            patch.object(
                hub, "_clear_instance_connections", new=AsyncMock()
            ) as clear_instance_mock,
        ):
            await hub.disconnect_all()

            unregister_mock.assert_any_await("room1", "conn1")
            unregister_mock.assert_any_await("room1", "conn2")
            clear_instance_mock.assert_awaited_once()
            assert hub._rooms == {}

    asyncio.run(scenario())
