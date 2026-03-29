import asyncio
import logging

import diff_match_patch as dmp_module

from settings import NOTE_MAX_CONTENT_LENGTH
from . import note_data as nd

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = NOTE_MAX_CONTENT_LENGTH
MAX_RETRY_ATTEMPTS = 3


def _format_updated_at(updated_at):
    return (
        updated_at.isoformat(sep=" ", timespec="microseconds") if updated_at else None
    )


def _ok_payload(data, status_text):
    return {"status": "ok", "data": {**data, "note_status": status_text}, "error": None}


def _error_payload(error, status_text, data=None):
    base = {} if data is None else dict(data)
    return {
        "status": "error",
        "data": {**base, "note_status": status_text},
        "error": str(error),
    }


async def sync_note_content(
    room_id, client_content, client_last_known_updated_at, client_original_content
):
    if len(client_content) > MAX_CONTENT_LENGTH:
        return (
            _error_payload(
                f"Content exceeds max length of {MAX_CONTENT_LENGTH} characters.",
                "error",
            ),
            400,
            False,
        )

    if client_last_known_updated_at is None or client_original_content is None:
        logger.warning(
            "Missing required parameters for room %s, using fallback", room_id
        )
        await nd.save_content(room_id, client_content)
        row = await nd.get_row(room_id)
        return (
            _ok_payload(
                {
                    "updated_at": _format_updated_at(row["updated_at"]),
                    "content": row["content"],
                },
                "ok_unconditional_fallback",
            ),
            200,
            True,
        )

    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            rowcount = await nd.save_content(
                room_id, client_content, client_last_known_updated_at
            )

            if rowcount > 0:
                row = await nd.get_row(room_id)
                return (
                    _ok_payload(
                        {
                            "updated_at": _format_updated_at(row["updated_at"]),
                            "content": row["content"],
                        },
                        "ok",
                    ),
                    200,
                    True,
                )

            merge_payload = await attempt_merge(
                room_id, client_content, client_original_content
            )
            if merge_payload:
                payload, http_status, changed = merge_payload
                return payload, http_status, changed

            if attempt < MAX_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(0.1 * (attempt + 1))
                continue
            final_row = await nd.get_row(room_id)
            return (
                _error_payload(
                    "Unable to resolve conflict after multiple attempts. Please refresh and try again.",
                    "conflict_max_retries",
                    data={
                        "updated_at": _format_updated_at(final_row["updated_at"]),
                        "content": final_row["content"],
                    },
                ),
                409,
                False,
            )

        except Exception as e:
            logger.error(
                "Error in sync attempt %s for room %s: %s", attempt + 1, room_id, e
            )
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                raise

    return (_error_payload("Internal server error", "error"), 500, False)


async def attempt_merge(room_id, client_content, client_original_content):
    try:
        current_db_row = await nd.get_row(room_id)
        server_text = current_db_row["content"]
        server_timestamp = _format_updated_at(current_db_row["updated_at"])

        dmp = dmp_module.diff_match_patch()
        patches = dmp.patch_make(client_original_content, client_content)
        merged_text, patch_results = dmp.patch_apply(patches, server_text)

        if all(patch_results):
            merged_rowcount = await nd.save_content(
                room_id, merged_text, server_timestamp
            )
            if merged_rowcount > 0:
                final_row = await nd.get_row(room_id)
                return (
                    _ok_payload(
                        {
                            "updated_at": _format_updated_at(final_row["updated_at"]),
                            "content": final_row["content"],
                        },
                        "ok_merged",
                    ),
                    200,
                    True,
                )
            logger.warning("Merge conflict during save for room %s", room_id)
            return None

        final_row = await nd.get_row(room_id)
        return (
            _error_payload(
                "Automatic merge failed. Please review the latest content.",
                "conflict_merge_failed",
                data={
                    "updated_at": _format_updated_at(final_row["updated_at"]),
                    "content": final_row["content"],
                },
            ),
            409,
            False,
        )
    except Exception as e:
        logger.error("Error in attempt_merge for room %s: %s", room_id, e)
        return None
