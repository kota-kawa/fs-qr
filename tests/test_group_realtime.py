import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter
from fastapi import WebSocketDisconnect

from Group import group_realtime
from Group.group_routes_ws import register_group_files_ws_route


def test_group_room_hub_connect_broadcast_disconnect():
    hub = group_realtime.GroupRoomHub()
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()

    async def scenario():
        with (
            patch("Group.group_realtime.get_redis", new=AsyncMock(return_value=None)),
            patch("Group.group_realtime.ensure_pubsub"),
        ):
            await hub.connect("abc123", websocket)
            assert websocket in hub._rooms["abc123"]

            await hub.broadcast("abc123", {"type": "files_updated"})
            websocket.send_json.assert_awaited_once_with({"type": "files_updated"})

            await hub.disconnect("abc123", websocket)
            assert "abc123" not in hub._rooms

    asyncio.run(scenario())


def test_notify_group_files_updated_broadcasts_payload():
    async def scenario():
        fake_hub = MagicMock()
        fake_hub.broadcast = AsyncMock()
        with (
            patch.object(group_realtime, "hub", fake_hub),
            patch(
                "Group.group_realtime._publish_room_event",
                new=AsyncMock(return_value=True),
            ) as publish_mock,
        ):
            await group_realtime.notify_group_files_updated("room42")
            fake_hub.broadcast.assert_awaited_once_with(
                "room42", {"type": "files_updated"}
            )
            publish_mock.assert_awaited_once_with("room42", {"type": "files_updated"})

    asyncio.run(scenario())


def test_group_room_hub_tracks_connections_in_redis():
    hub = group_realtime.GroupRoomHub()
    websocket = MagicMock()
    websocket.accept = AsyncMock()

    register_pipeline = MagicMock()
    register_pipeline.execute = AsyncMock(return_value=[1, 1, 1, 1])
    unregister_pipeline = MagicMock()
    unregister_pipeline.execute = AsyncMock(return_value=[1, 1, 0, 0])
    redis_client = MagicMock()
    redis_client.pipeline.side_effect = [register_pipeline, unregister_pipeline]
    redis_client.delete = AsyncMock()

    async def scenario():
        with (
            patch(
                "Group.group_realtime.get_redis",
                new=AsyncMock(return_value=redis_client),
            ),
            patch("Group.group_realtime.ensure_pubsub"),
        ):
            await hub.connect("abc123", websocket)
            connection_id = hub._rooms["abc123"][websocket]
            member = group_realtime._connection_member("abc123", connection_id)
            await hub.disconnect("abc123", websocket)

        room_key = group_realtime._room_connections_key("abc123")
        register_pipeline.sadd.assert_any_call(room_key, member)
        register_pipeline.sadd.assert_any_call(
            group_realtime.INSTANCE_CONNECTIONS_KEY, member
        )
        unregister_pipeline.srem.assert_any_call(room_key, member)
        unregister_pipeline.srem.assert_any_call(
            group_realtime.INSTANCE_CONNECTIONS_KEY, member
        )
        redis_client.delete.assert_any_await(room_key)
        redis_client.delete.assert_any_await(group_realtime.INSTANCE_CONNECTIONS_KEY)

    asyncio.run(scenario())


def test_group_pubsub_dispatches_only_remote_allowed_events():
    class FakePubSub:
        def __init__(self, messages):
            self.messages = messages
            self.subscriptions = []
            self.closed = False

        async def psubscribe(self, pattern):
            self.subscriptions.append(pattern)

        def listen(self):
            return self._listen()

        async def _listen(self):
            for message in self.messages:
                yield message

        async def close(self):
            self.closed = True

    async def scenario():
        pubsub = FakePubSub(
            [
                {"type": "message", "data": "not json"},
                {
                    "type": "message",
                    "data": json.dumps(
                        {
                            "room_id": "local",
                            "payload": {"type": "files_updated"},
                            "source": group_realtime.INSTANCE_ID,
                        }
                    ),
                },
                {
                    "type": "pmessage",
                    "channel": b"group:room:remote",
                    "data": json.dumps(
                        {
                            "payload": {"type": "files_updated"},
                            "source": "other-worker",
                        }
                    ),
                },
                {
                    "type": "message",
                    "data": json.dumps(
                        {
                            "room_id": "closed",
                            "payload": {"type": "room_closed"},
                            "source": "other-worker",
                        }
                    ),
                },
                {
                    "type": "message",
                    "data": json.dumps(
                        {
                            "room_id": "ignored",
                            "payload": {"type": "unexpected"},
                            "source": "other-worker",
                        }
                    ),
                },
            ]
        )
        client = MagicMock()
        client.pubsub.return_value = pubsub
        with (
            patch("Group.group_realtime.get_redis", new=AsyncMock(return_value=client)),
            patch.object(group_realtime.hub, "broadcast", new=AsyncMock()) as broadcast,
            patch.object(
                group_realtime.hub, "close_room", new=AsyncMock()
            ) as close_room,
        ):
            await group_realtime._pubsub_loop()

        assert pubsub.subscriptions == [group_realtime.CHANNEL_PATTERN]
        assert pubsub.closed is True
        broadcast.assert_any_await("remote", {"type": "files_updated"})
        broadcast.assert_any_await("closed", {"type": "room_closed"})
        assert broadcast.await_count == 2
        close_room.assert_awaited_once_with("closed", code=1001)

    asyncio.run(scenario())


def test_group_room_closed_notifies_local_connections_and_redis():
    async def scenario():
        fake_hub = MagicMock()
        fake_hub.broadcast = AsyncMock()
        fake_hub.close_room = AsyncMock()
        with (
            patch.object(group_realtime, "hub", fake_hub),
            patch(
                "Group.group_realtime._publish_room_event",
                new=AsyncMock(return_value=True),
            ) as publish_mock,
        ):
            assert await group_realtime.notify_group_room_closed("room42") is True
            fake_hub.broadcast.assert_awaited_once_with(
                "room42", {"type": "room_closed"}
            )
            fake_hub.close_room.assert_awaited_once_with("room42", code=1001)
            publish_mock.assert_awaited_once_with("room42", {"type": "room_closed"})

    asyncio.run(scenario())


def test_group_file_notification_degrades_to_local_broadcast_without_redis():
    async def scenario():
        fake_hub = MagicMock()
        fake_hub.broadcast = AsyncMock()
        with (
            patch.object(group_realtime, "hub", fake_hub),
            patch("Group.group_realtime.ensure_pubsub"),
            patch("Group.group_realtime.get_redis", new=AsyncMock(return_value=None)),
        ):
            assert await group_realtime.notify_group_files_updated("room42") is False
            fake_hub.broadcast.assert_awaited_once_with(
                "room42", {"type": "files_updated"}
            )

    asyncio.run(scenario())


def test_group_files_ws_rejects_invalid_auth():
    router = APIRouter()
    register_group_files_ws_route(router)
    endpoint = router.routes[0].endpoint
    websocket = MagicMock()
    websocket.query_params = {"csrf_token": "csrf-test-token"}
    websocket.session = {"_csrf_token": "csrf-test-token"}
    websocket.close = AsyncMock()

    async def scenario():
        with patch(
            "Group.group_routes_ws.get_room_if_active",
            new=AsyncMock(return_value=None),
        ):
            await endpoint(websocket=websocket, room_id="abc123")

    asyncio.run(scenario())
    websocket.close.assert_awaited_once_with(code=1008)


def test_group_files_ws_connects_and_disconnects_on_client_close():
    router = APIRouter()
    register_group_files_ws_route(router)
    endpoint = router.routes[0].endpoint
    websocket = MagicMock()
    websocket.query_params = {"csrf_token": "csrf-test-token"}
    websocket.session = {
        "_csrf_token": "csrf-test-token",
        "group_room_access": {"abc123": {}},
    }
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    async def scenario():
        with (
            patch(
                "Group.group_routes_ws.get_room_if_active",
                new=AsyncMock(return_value={"id": "abc123"}),
            ),
            patch("Group.group_routes_ws.hub.connect", new=AsyncMock()) as connect_mock,
            patch(
                "Group.group_routes_ws.hub.disconnect", new=AsyncMock()
            ) as disconnect_mock,
        ):
            await endpoint(websocket=websocket, room_id="abc123")
            connect_mock.assert_awaited_once_with("abc123", websocket)
            disconnect_mock.assert_awaited_once_with("abc123", websocket)

    asyncio.run(scenario())


def test_group_files_ws_rejects_missing_websocket_csrf():
    router = APIRouter()
    register_group_files_ws_route(router)
    endpoint = router.routes[0].endpoint
    websocket = MagicMock()
    websocket.query_params = {}
    websocket.session = {"_csrf_token": "csrf-test-token"}
    websocket.close = AsyncMock()

    async def scenario():
        await endpoint(websocket=websocket, room_id="abc123")

    asyncio.run(scenario())
    websocket.close.assert_awaited_once_with(code=1008)
