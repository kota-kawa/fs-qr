import logging

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from . import note_data as nd
from .note_sync import sync_note_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.api_route("/note/{room_id}/{password}", methods=["GET", "POST"], name="note.note_sync")
async def note_sync(request: Request, room_id: str, password: str):
    meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            room_id = fallback_room_id
            meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        return JSONResponse({"error": "room not found or password mismatch"}, status_code=404)

    if request.method == "GET":
        try:
            row = await nd.get_row(room_id)
            if row["updated_at"] is None:
                return JSONResponse({"error": "room not found or not initialized"}, status_code=404)
            return JSONResponse(
                {
                    "content": row["content"],
                    "updated_at": row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                }
            )
        except Exception as e:
            logger.error("GET error for room %s: %s", room_id, e)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    try:
        try:
            data = await request.json()
        except Exception:
            data = {}
        client_content = data.get("content", "")
        client_last_known_updated_at = data.get("last_known_updated_at")
        client_original_content = data.get("original_content")
        payload, status_code, _ = await sync_note_content(
            room_id,
            client_content,
            client_last_known_updated_at,
            client_original_content,
        )
        return JSONResponse(payload, status_code=status_code)

    except Exception as e:
        logger.error("Critical error in note_sync for room %s: %s", room_id, e)
        return JSONResponse({"error": "Internal server error"}, status_code=500)
