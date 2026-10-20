"""Group / Note / Task の作成者向け保存期間設定。"""

from datetime import datetime, timedelta
import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from api_response import api_error_response, api_ok_response, error_page_or_json
from i18n import current_language_ctx, get_translator
from models import ROOM_RETENTION_CHOICES, RoomRetentionInput
from rate_limit import check_rate_limit, get_block_message, get_client_ip
from room_session import RoomSessionAccess
from web import enforce_csrf, wants_json_response

logger = logging.getLogger(__name__)


def room_retention_options(record: dict) -> list[dict]:
    """作成日時起点の削除日時を返す。過去になる選択肢は表示から除く。"""
    created_at = record.get("time")
    if not isinstance(created_at, datetime):
        return []
    now = datetime.now()
    return [
        {"hours": hours, "deletion_date": date.strftime("%Y-%m-%d %H:%M")}
        for hours in ROOM_RETENTION_CHOICES
        if (date := created_at + timedelta(hours=hours)) > now
    ]


def register_room_settings_route(
    router: APIRouter,
    *,
    service: str,
    access: RoomSessionAccess,
    update: Callable[[str, int], Awaitable[dict[str, Any] | None]],
) -> None:
    @router.post(f"/{service}/r/{{room_id}}/settings", name=f"{service}.settings")
    async def save_settings(request: Request, room_id: str):
        await enforce_csrf(request)
        translate = get_translator(current_language_ctx.get())
        if not access.can_delete(request, room_id):
            return error_page_or_json(
                request, translate("room.settings.forbidden"), status_code=403
            )
        allowed, _, block_label = await check_rate_limit(
            f"{service}_room_settings",
            get_client_ip(request),
            request_limit=30,
            request_window_seconds=60,
        )
        if not allowed:
            return api_error_response(get_block_message(block_label), status_code=429)
        try:
            data = (
                await request.json()
                if "application/json" in request.headers.get("content-type", "")
                else await request.form()
            )
            inp = RoomRetentionInput.model_validate(
                {"retention_hours": data.get("retention_hours")}
            )
        except (ValidationError, ValueError, AttributeError):
            return error_page_or_json(
                request, translate("room.settings.invalid"), status_code=400
            )
        try:
            record = await update(room_id, inp.retention_hours)
        except Exception:
            logger.exception("Failed to update room retention: service=%s", service)
            return error_page_or_json(
                request, translate("room.settings.failed"), status_code=500
            )
        if not record:
            return error_page_or_json(
                request, translate("room.settings.expired"), status_code=409
            )
        if wants_json_response(request):
            return api_ok_response(
                {"deletion_date": record["expires_at"].strftime("%Y-%m-%d %H:%M")}
            )
        return RedirectResponse(f"/{service}/r/{room_id}", status_code=303)
