import logging

from fastapi import APIRouter, Request
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import NoteSyncInput
from . import note_data as nd
from .note_sync import sync_note_content
from web import enforce_csrf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.api_route(
    "/note/{room_id}/{password}", methods=["GET", "POST"], name="note.note_sync"
)
async def note_sync(request: Request, room_id: str, password: str):
    if request.method == "POST":
        await enforce_csrf(request)

    meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            room_id = fallback_room_id
            meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        return api_error_response(
            "room not found or password mismatch", status_code=404
        )

    if request.method == "GET":
        try:
            row = await nd.get_row(room_id)
            if row["updated_at"] is None:
                return api_error_response(
                    "room not found or not initialized", status_code=404
                )
            return api_ok_response(
                {
                    "content": row["content"],
                    "updated_at": row["updated_at"].isoformat(
                        sep=" ", timespec="microseconds"
                    ),
                }
            )
        except Exception as e:
            logger.error("GET error for room %s: %s", room_id, e)
        return api_error_response("Internal server error", status_code=500)

    try:
        try:
            data = await request.json()
        except Exception:
            data = {}
        try:
            sync_in = NoteSyncInput.model_validate(
                data if isinstance(data, dict) else {}
            )
        except ValidationError:
            return api_error_response("Invalid request body", status_code=400)
        client_content = sync_in.content
        client_last_known_updated_at = sync_in.last_known_updated_at
        client_original_content = sync_in.original_content
        payload, status_code, _ = await sync_note_content(
            room_id,
            client_content,
            client_last_known_updated_at,
            client_original_content,
        )
        if status_code >= 400:
            return api_error_response(
                payload.get("error", "Internal server error"),
                status_code=status_code,
                data=payload.get("data", {}),
            )
        return api_ok_response(payload.get("data", {}), status_code=status_code)

    except Exception as e:
        logger.error("Critical error in note_sync for room %s: %s", room_id, e)
        return api_error_response("Internal server error", status_code=500)
