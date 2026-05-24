import logging

from fastapi import APIRouter, Request
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import NoteSyncInput
from . import note_data as nd
from .note_access import has_note_room_access
from .note_sync import sync_note_content
from web import enforce_csrf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _format_updated_at(updated_at):
    return (
        updated_at.isoformat(sep=" ", timespec="microseconds") if updated_at else None
    )


@router.api_route("/note/{room_id}", methods=["GET", "POST"], name="note.note_sync")
async def note_sync(request: Request, room_id: str):
    if request.method == "POST":
        await enforce_csrf(request)

    if not has_note_room_access(request, room_id):
        return api_error_response("room access is not established", status_code=404)

    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        return api_error_response("room expired or deleted", status_code=410)

    if request.method == "GET":
        try:
            row = await nd.get_row(room_id)
            if not row or row["updated_at"] is None:
                return api_error_response(
                    "room expired or not initialized", status_code=410
                )
            return api_ok_response(
                {
                    "content": row["content"],
                    "updated_at": _format_updated_at(row["updated_at"]),
                    "version": row["version"],
                    "expires_at": meta.get("expires_at").isoformat(sep=" ")
                    if meta.get("expires_at")
                    else None,
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
        client_base_version = sync_in.base_version
        client_original_content = sync_in.original_content
        payload, status_code, _ = await sync_note_content(
            room_id,
            client_content,
            client_base_version,
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


@router.api_route(
    "/note/{room_id}/{password}",
    methods=["GET", "POST"],
    name="note.note_legacy_sync",
)
async def note_legacy_sync(request: Request, room_id: str, password: str):
    if request.method == "POST":
        await enforce_csrf(request)
    return api_error_response(
        "legacy note password API is no longer available", status_code=410
    )
