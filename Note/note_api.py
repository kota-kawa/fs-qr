import logging

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from api_response import api_error_response, api_ok_response
from file_validation import build_content_disposition_attachment
from models import NoteExportInput
from . import note_data as nd
from .note_access import has_note_room_access
from .note_export import NotePdfFontUnavailableError, build_note_pdf
from web import enforce_csrf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _format_updated_at(updated_at):
    return (
        updated_at.isoformat(sep=" ", timespec="microseconds") if updated_at else None
    )


@router.post("/note/{room_id}/export/{export_format}", name="note.note_export")
async def note_export(request: Request, room_id: str, export_format: str):
    """現在のエディタ内容を TXT または PDF として返す。"""
    await enforce_csrf(request)

    if export_format not in {"txt", "pdf"}:
        return api_error_response("unsupported export format", status_code=404)
    if not has_note_room_access(request, room_id):
        return api_error_response("room access is not established", status_code=404)

    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        return api_error_response("room expired or deleted", status_code=410)
    row = await nd.get_row(room_id)
    if not row:
        return api_error_response("room expired or not initialized", status_code=410)

    try:
        data = await request.json()
    except Exception:
        data = {}
    try:
        export_input = NoteExportInput.model_validate(
            data if isinstance(data, dict) else {}
        )
    except ValidationError:
        return api_error_response("Invalid request body", status_code=400)

    filename = f"note-{room_id}.{export_format}"
    headers = {
        "Content-Disposition": build_content_disposition_attachment(filename),
        "Cache-Control": "private, no-store",
    }
    if export_format == "txt":
        return Response(
            content=export_input.content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )

    try:
        pdf_content = await run_in_threadpool(
            build_note_pdf, export_input.content, room_id
        )
    except NotePdfFontUnavailableError:
        logger.exception("PDF font is unavailable for note room %s", room_id)
        return api_error_response(
            "PDF export is temporarily unavailable", status_code=503
        )
    except Exception:
        logger.exception("PDF export failed for note room %s", room_id)
        return api_error_response("PDF export failed", status_code=500)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers=headers,
    )


@router.get("/note/{room_id}", name="note.note_state")
async def note_state(request: Request, room_id: str):
    """Return the persisted plaintext mirror used by downloads and rollback."""
    if not has_note_room_access(request, room_id):
        return api_error_response("room access is not established", status_code=404)
    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        return api_error_response("room expired or deleted", status_code=410)
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
    except Exception as exc:
        logger.error("GET error for room %s: %s", room_id, exc)
        return api_error_response("Internal server error", status_code=500)


@router.post("/note/{room_id}", name="note.note_legacy_write")
async def note_legacy_write(request: Request, room_id: str):
    """Reject writes from clients that predate the Yjs migration."""
    await enforce_csrf(request)
    if not has_note_room_access(request, room_id):
        return api_error_response("room access is not established", status_code=404)
    return api_error_response(
        "Note writes moved to the Yjs collaboration endpoint", status_code=410
    )


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
