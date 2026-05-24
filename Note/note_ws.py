import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from database import remove_db_session
from models import NoteWsMessage
from rate_limit import (
    SCOPE_NOTE,
    check_rate_limit,
    get_block_message,
    register_failure,
    register_success,
)
from web import validate_websocket_csrf
from . import note_data as nd
from .note_access import has_note_room_access_session
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


def _ws_session(websocket: WebSocket):
    session = getattr(websocket, "session", None)
    if session is None and isinstance(getattr(websocket, "scope", None), dict):
        session = websocket.scope.get("session")
    return session


async def _authorize_note_ws(websocket: WebSocket, room_id: str, ip: str) -> bool:
    allowed, _, _ = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        await websocket.close(code=1008)
        return False

    if not validate_websocket_csrf(websocket):
        await websocket.close(code=1008)
        return False

    session = _ws_session(websocket)
    if not session or not has_note_room_access_session(session, room_id):
        await websocket.close(code=1008)
        return False

    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            await websocket.accept()
            await websocket.send_json(
                {"type": "error", "error": get_block_message(block_label)}
            )
        await websocket.close(code=1008)
        return False

    return True


async def _send_initial_state(websocket: WebSocket, room_id: str) -> bool:
    row = await nd.get_row(room_id)
    if not row:
        await websocket.send_json(
            {"type": "error", "error": "Room has expired or was deleted."}
        )
        await websocket.close(code=1008)
        return False

    await websocket.send_json(
        {
            "type": "init",
            "content": row["content"],
            "updated_at": row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
            "version": row["version"],
        }
    )
    await remove_db_session()
    return True


async def _handle_note_messages(websocket: WebSocket, room_id: str) -> None:
    while True:
        raw = await websocket.receive_json()
        try:
            message = NoteWsMessage.model_validate(raw)
        except ValidationError:
            continue
        client_content = message.content
        client_request_id = message.request_id
        client_base_version = message.base_version
        client_original_content = message.original_content

        try:
            payload, status_code, changed = await sync_note_content(
                room_id,
                client_content,
                client_base_version,
                client_original_content,
            )
        except Exception as exc:
            logger.error("Critical error in note_ws for room %s: %s", room_id, exc)
            await websocket.send_json(
                {"type": "error", "error": "Internal server error"}
            )
            await remove_db_session()
            continue

        payload_with_type = {"type": "ack", **payload}
        if client_request_id:
            payload_with_type["request_id"] = client_request_id
        await websocket.send_json(payload_with_type)
        if status_code == 410:
            await websocket.close(code=1008)
            return

        if changed and status_code == 200:
            payload_data = payload.get("data", {})
            if not isinstance(payload_data, dict):
                payload_data = {}
            update_payload = {
                "type": "update",
                "status": "ok",
                "data": {
                    "content": payload_data.get("content"),
                    "updated_at": payload_data.get("updated_at"),
                    "version": payload_data.get("version"),
                    "note_status": payload_data.get("note_status"),
                },
                "error": None,
            }
            await hub.broadcast(room_id, update_payload, exclude=websocket)
            await publish_room_update(room_id, update_payload)

        await remove_db_session()


@router.websocket("/ws/note/{room_id}")
async def note_ws(websocket: WebSocket, room_id: str):
    ip = _ws_client_ip(websocket)
    if not await _authorize_note_ws(websocket, room_id, ip):
        return

    await register_success(SCOPE_NOTE, ip)
    await hub.connect(room_id, websocket)
    try:
        if not await _send_initial_state(websocket, room_id):
            return
        await _handle_note_messages(websocket, room_id)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Unexpected websocket error in room %s: %s", room_id, exc)
    finally:
        await hub.disconnect(room_id, websocket)
        await remove_db_session()
