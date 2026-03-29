import asyncio


class GroupRoomHub:
    def __init__(self):
        self._rooms = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id, websocket):
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(websocket)

    async def disconnect(self, room_id, websocket):
        async with self._lock:
            sockets = self._rooms.get(room_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._rooms.pop(room_id, None)

    async def broadcast(self, room_id, payload):
        async with self._lock:
            sockets = list(self._rooms.get(room_id, set()))

        if not sockets:
            return

        dead_sockets = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead_sockets.append(websocket)

        if not dead_sockets:
            return

        async with self._lock:
            active = self._rooms.get(room_id)
            if not active:
                return
            for websocket in dead_sockets:
                active.discard(websocket)
            if not active:
                self._rooms.pop(room_id, None)

    async def close_room(self, room_id, code=1001):
        async with self._lock:
            sockets = list(self._rooms.pop(room_id, set()))

        for websocket in sockets:
            try:
                await websocket.close(code=code)
            except Exception:
                continue


hub = GroupRoomHub()


async def notify_group_files_updated(room_id):
    await hub.broadcast(room_id, {"type": "files_updated"})
