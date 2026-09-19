from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .group_common import GROUP_ACCESS, get_room_if_active
from .group_realtime import hub
from web import validate_websocket_csrf


def register_group_files_ws_route(router: APIRouter):
    @router.websocket("/ws/group/{room_id}")
    async def group_files_ws(websocket: WebSocket, room_id: str):
        if not validate_websocket_csrf(websocket):
            await websocket.close(code=1008)
            return

        if not GROUP_ACCESS.has_session(websocket.session, room_id):
            await websocket.close(code=1008)
            return

        if not await get_room_if_active(room_id):
            await websocket.close(code=1008)
            return

        connected = await hub.connect(room_id, websocket)
        if not connected:
            await websocket.close(code=1013)
            return

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.disconnect(room_id, websocket)
