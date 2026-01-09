import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import remove_db_session
from rate_limit import SCOPE_NOTE, check_rate_limit, get_block_message, register_failure, register_success
from . import note_data as nd
from .note_realtime import hub, publish_room_update
from .note_sync import sync_note_content

logger = logging.getLogger(__name__)

router = APIRouter()


def _ws_client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if websocket.client:
        return websocket.client.host
    return "unknown"


@router.websocket("/ws/note/{room_id}/{password}")
async def note_ws(websocket: WebSocket, room_id: str, password: str):
    ip = _ws_client_ip(websocket)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        await websocket.close(code=1008)
        return

    meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            room_id = fallback_room_id
            meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": get_block_message(block_label)})
        await websocket.close(code=1008)
        return

    await register_success(SCOPE_NOTE, ip)

    await hub.connect(room_id, websocket)
    try:
        row = await nd.get_row(room_id)
        await websocket.send_json(
            {
                "type": "init",
                "content": row["content"],
                "updated_at": row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
            }
        )
        await remove_db_session()

        while True:
            message = await websocket.receive_json()
            if message.get("type") != "save":
                continue
            client_content = message.get("content", "")
            client_last_known_updated_at = message.get("last_known_updated_at")
            client_original_content = message.get("original_content")

            try:
                payload, status_code, changed = await sync_note_content(
                    room_id,
                    client_content,
                    client_last_known_updated_at,
                    client_original_content,
                )
            except Exception as exc:
                logger.error("Critical error in note_ws for room %s: %s", room_id, exc)
                await websocket.send_json({"type": "error", "error": "Internal server error"})
                await remove_db_session()
                continue

            payload_with_type = {"type": "ack", **payload}
            await websocket.send_json(payload_with_type)

            if changed and status_code == 200:
                update_payload = {
                    "type": "update",
                    "content": payload.get("content"),
                    "updated_at": payload.get("updated_at"),
                    "status": payload.get("status"),
                }
                await hub.broadcast(room_id, update_payload, exclude=websocket)
                await publish_room_update(room_id, update_payload)
            
            await remove_db_session()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Unexpected websocket error in room %s: %s", room_id, exc)
    finally:
        await hub.disconnect(room_id, websocket)
        await remove_db_session()
