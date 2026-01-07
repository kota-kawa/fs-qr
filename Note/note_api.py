import asyncio
import logging

import diff_match_patch as dmp_module
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from . import note_data as nd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

MAX_CONTENT_LENGTH = 10000
MAX_RETRY_ATTEMPTS = 3


@router.api_route("/note/{room_id}/{password}", methods=["GET", "POST"], name="note.note_sync")
async def note_sync(request: Request, room_id: str, password: str):
    meta = nd.get_room_meta(room_id, password=password)
    if not meta:
        return JSONResponse({"error": "room not found or password mismatch"}, status_code=404)

    if request.method == "GET":
        try:
            row = nd.get_row(room_id)
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

        if len(client_content) > MAX_CONTENT_LENGTH:
            return JSONResponse(
                {
                    "status": "error",
                    "error": f"Content exceeds max length of {MAX_CONTENT_LENGTH} characters.",
                },
                status_code=400,
            )

        if client_last_known_updated_at is None or client_original_content is None:
            logger.warning("Missing required parameters for room %s, using fallback", room_id)
            nd.save_content(room_id, client_content)
            row = nd.get_row(room_id)
            return JSONResponse(
                {
                    "status": "ok_unconditional_fallback",
                    "updated_at": row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                    "content": row["content"],
                }
            )

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                rowcount = nd.save_content(room_id, client_content, client_last_known_updated_at)

                if rowcount > 0:
                    row = nd.get_row(room_id)
                    return JSONResponse(
                        {
                            "status": "ok",
                            "updated_at": row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                            "content": row["content"],
                        }
                    )

                merge_result = attempt_merge(room_id, client_content, client_original_content)
                if merge_result:
                    return merge_result

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                final_row = nd.get_row(room_id)
                return JSONResponse(
                    {
                        "status": "conflict_max_retries",
                        "error": "Unable to resolve conflict after multiple attempts. Please refresh and try again.",
                        "updated_at": final_row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                        "content": final_row["content"],
                    },
                    status_code=409,
                )

            except Exception as e:
                logger.error("Error in sync attempt %s for room %s: %s", attempt + 1, room_id, e)
                if attempt == MAX_RETRY_ATTEMPTS - 1:
                    raise

    except Exception as e:
        logger.error("Critical error in note_sync for room %s: %s", room_id, e)
        return JSONResponse({"error": "Internal server error"}, status_code=500)


def attempt_merge(room_id, client_content, client_original_content):
    try:
        current_db_row = nd.get_row(room_id)
        server_text = current_db_row["content"]
        server_timestamp = current_db_row["updated_at"].isoformat(sep=" ", timespec="microseconds")

        dmp = dmp_module.diff_match_patch()
        patches = dmp.patch_make(client_original_content, client_content)
        merged_text, patch_results = dmp.patch_apply(patches, server_text)

        if all(patch_results):
            merged_rowcount = nd.save_content(room_id, merged_text, server_timestamp)
            if merged_rowcount > 0:
                final_row = nd.get_row(room_id)
                return JSONResponse(
                    {
                        "status": "ok_merged",
                        "updated_at": final_row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                        "content": final_row["content"],
                    }
                )
            logger.warning("Merge conflict during save for room %s", room_id)
            return None

        final_row = nd.get_row(room_id)
        return JSONResponse(
            {
                "status": "conflict_merge_failed",
                "error": "Automatic merge failed. Please review the latest content.",
                "updated_at": final_row["updated_at"].isoformat(sep=" ", timespec="microseconds"),
                "content": final_row["content"],
            },
            status_code=409,
        )
    except Exception as e:
        logger.error("Error in attempt_merge for room %s: %s", room_id, e)
        return None
