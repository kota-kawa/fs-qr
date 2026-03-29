import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocketDisconnect

from Note.note_ws import note_ws


def test_note_ws_ack_includes_request_id():
    websocket = MagicMock()
    websocket.headers = {}
    websocket.client = type("Client", (), {"host": "127.0.0.1"})()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {
                "type": "save",
                "request_id": "save-1",
                "content": "hello",
                "last_known_updated_at": "2026-01-01 00:00:00.000000",
                "original_content": "hi",
            },
            WebSocketDisconnect(),
        ]
    )

    initial_row = {
        "content": "initial",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0, 0),
    }
    sync_payload = {
        "status": "ok",
        "data": {
            "content": "hello",
            "updated_at": "2026-01-01 00:00:01.000000",
            "note_status": "ok",
        },
        "error": None,
    }

    async def scenario():
        with (
            patch(
                "Note.note_ws.check_rate_limit",
                new=AsyncMock(return_value=(True, None, None)),
            ),
            patch("Note.note_ws.register_success", new=AsyncMock()),
            patch(
                "Note.note_ws.nd.get_room_meta_direct",
                new=AsyncMock(return_value={"id": "abc123"}),
            ),
            patch("Note.note_ws.nd.get_row", new=AsyncMock(return_value=initial_row)),
            patch("Note.note_ws.hub.connect", new=AsyncMock()),
            patch("Note.note_ws.hub.disconnect", new=AsyncMock()),
            patch("Note.note_ws.hub.broadcast", new=AsyncMock()),
            patch("Note.note_ws.publish_room_update", new=AsyncMock()),
            patch(
                "Note.note_ws.sync_note_content",
                new=AsyncMock(return_value=(sync_payload, 200, False)),
            ),
            patch("Note.note_ws.remove_db_session", new=AsyncMock()),
        ):
            await note_ws(websocket=websocket, room_id="abc123", password="000000")

    asyncio.run(scenario())

    init_payload = websocket.send_json.await_args_list[0].args[0]
    ack_payload = websocket.send_json.await_args_list[1].args[0]

    assert init_payload["type"] == "init"
    assert ack_payload["type"] == "ack"
    assert ack_payload["request_id"] == "save-1"
    assert ack_payload["status"] == "ok"
    assert ack_payload["data"]["note_status"] == "ok"
