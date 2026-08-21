import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from Note import note_realtime


def test_publish_room_expired_sends_hocuspocus_control_event():
    client = MagicMock()
    client.publish = AsyncMock(return_value=1)

    async def scenario():
        with patch("Note.note_realtime.get_redis", new=AsyncMock(return_value=client)):
            assert await note_realtime.publish_room_expired("room1") is True

    asyncio.run(scenario())
    channel, raw = client.publish.await_args.args
    assert channel == "note:room:room1"
    assert json.loads(raw) == {
        "room_id": "room1",
        "payload": {"type": "room_expired"},
    }


def test_publish_room_expired_degrades_when_redis_is_unavailable():
    async def scenario():
        with patch("Note.note_realtime.get_redis", new=AsyncMock(return_value=None)):
            assert await note_realtime.publish_room_expired("room1") is False

    asyncio.run(scenario())


def test_shutdown_closes_cached_redis_client():
    client = MagicMock()
    client.aclose = AsyncMock()

    async def scenario():
        note_realtime._redis_client = client
        await note_realtime.shutdown()

    asyncio.run(scenario())
    client.aclose.assert_awaited_once()
    assert note_realtime._redis_client is None
