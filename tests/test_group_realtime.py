import asyncio
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
        await hub.connect("abc123", websocket)
        assert websocket in hub._rooms["abc123"]

        await hub.broadcast("abc123", {"type": "files_updated"})
        websocket.send_json.assert_awaited_once_with({"type": "files_updated"})

        await hub.disconnect("abc123", websocket)
        assert "abc123" not in hub._rooms

    asyncio.run(scenario())


def test_notify_group_files_updated_broadcasts_payload():
    async def scenario():
        original_hub = group_realtime.hub
        fake_hub = MagicMock()
        fake_hub.broadcast = AsyncMock()
        group_realtime.hub = fake_hub
        try:
            await group_realtime.notify_group_files_updated("room42")
            fake_hub.broadcast.assert_awaited_once_with(
                "room42", {"type": "files_updated"}
            )
        finally:
            group_realtime.hub = original_hub

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
            "Group.group_routes_ws.get_room_if_valid",
            new=AsyncMock(return_value=None),
        ):
            await endpoint(websocket=websocket, room_id="abc123", password="000000")

    asyncio.run(scenario())
    websocket.close.assert_awaited_once_with(code=1008)


def test_group_files_ws_connects_and_disconnects_on_client_close():
    router = APIRouter()
    register_group_files_ws_route(router)
    endpoint = router.routes[0].endpoint
    websocket = MagicMock()
    websocket.query_params = {"csrf_token": "csrf-test-token"}
    websocket.session = {"_csrf_token": "csrf-test-token"}
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    async def scenario():
        with (
            patch(
                "Group.group_routes_ws.get_room_if_valid",
                new=AsyncMock(return_value={"id": "abc123"}),
            ),
            patch("Group.group_routes_ws.hub.connect", new=AsyncMock()) as connect_mock,
            patch(
                "Group.group_routes_ws.hub.disconnect", new=AsyncMock()
            ) as disconnect_mock,
        ):
            await endpoint(websocket=websocket, room_id="abc123", password="000000")
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
        await endpoint(websocket=websocket, room_id="abc123", password="000000")

    asyncio.run(scenario())
    websocket.close.assert_awaited_once_with(code=1008)
