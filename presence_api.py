"""「現在の閲覧者数」を取得・更新する公開 API。

ログイン不要で、対象ページを閲覧している全員が人数を確認できる。
"""

from fastapi import APIRouter, Request

import presence
from api_response import api_error_response, api_ok_response
from rate_limit import (
    PUBLIC_PRESENCE_REQUEST_LIMIT,
    PUBLIC_PRESENCE_WINDOW_SECONDS,
    SCOPE_PRESENCE,
    check_rate_limit,
    get_block_message,
    get_client_ip,
)

router = APIRouter()


def _extract_viewer_id(request: Request) -> str:
    return (request.query_params.get("viewer_id") or "").strip()


def _validate(scope: str, key: str, viewer_id: str):
    if not presence.is_valid_scope(scope):
        return api_error_response("対象が不正です。", status_code=404)
    if not presence.is_valid_key(key):
        return api_error_response("対象が不正です。", status_code=404)
    if viewer_id and not presence.is_valid_viewer_id(viewer_id):
        return api_error_response("リクエストが不正です。", status_code=400)
    return None


async def _check_request_rate(request: Request):
    allowed, _, block_label = await check_rate_limit(
        SCOPE_PRESENCE,
        get_client_ip(request),
        request_limit=PUBLIC_PRESENCE_REQUEST_LIMIT,
        request_window_seconds=PUBLIC_PRESENCE_WINDOW_SECONDS,
    )
    if not allowed:
        return api_error_response(get_block_message(block_label), status_code=429)
    return None


@router.post("/api/presence/{scope}/{key}", name="presence.heartbeat")
async def presence_heartbeat(request: Request, scope: str, key: str):
    rate_error = await _check_request_rate(request)
    if rate_error is not None:
        return rate_error
    viewer_id = _extract_viewer_id(request)
    error = _validate(scope, key, viewer_id)
    if error is not None:
        return error
    if not viewer_id:
        return api_error_response("viewer_id が必要です。", status_code=400)
    try:
        current = await presence.heartbeat(scope, key, viewer_id)
    except presence.PresenceCapacityError:
        return api_error_response(
            "このページの閲覧者数が上限に達しています。",
            status_code=429,
        )
    return api_ok_response({"count": current})


@router.get("/api/presence/{scope}/{key}", name="presence.count")
async def presence_count(request: Request, scope: str, key: str):
    rate_error = await _check_request_rate(request)
    if rate_error is not None:
        return rate_error
    error = _validate(scope, key, "")
    if error is not None:
        return error
    current = await presence.count(scope, key)
    return api_ok_response({"count": current})


@router.post("/api/presence/{scope}/{key}/leave", name="presence.leave")
async def presence_leave(request: Request, scope: str, key: str):
    rate_error = await _check_request_rate(request)
    if rate_error is not None:
        return rate_error
    viewer_id = _extract_viewer_id(request)
    error = _validate(scope, key, viewer_id)
    if error is not None:
        return error
    if not viewer_id:
        return api_ok_response({"count": await presence.count(scope, key)})
    current = await presence.leave(scope, key, viewer_id)
    return api_ok_response({"count": current})
