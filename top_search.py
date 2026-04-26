from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from FSQR import fsqr_data
from Group import group_data
from Note import note_data
from models import RoomSearchInput
from rate_limit import (
    SCOPE_TOP_SEARCH,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, enforce_csrf, render_template

router = APIRouter()


def _render_result(
    request: Request,
    *,
    message: str,
    status_code: int,
    matches: list[dict[str, Any]] | None = None,
    searched_id: str = "",
):
    response = render_template(
        request,
        "search_all_results.html",
        message=message,
        matches=matches or [],
        searched_id=searched_id,
    )
    response.status_code = status_code
    return response


async def _collect_search_matches(
    request: Request, room_id: str, password: str
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    fsqr_rows = await fsqr_data.get_data_by_credentials(room_id, password)
    if fsqr_rows:
        fsqr_room_id = fsqr_rows[0].get("id") or room_id
        matches.append(
            {
                "service_key": "fsqr",
                "service_name": "QRコード共有",
                "description": "アップロード済みファイルのダウンロード画面を開きます。",
                "url": build_url(
                    request,
                    "fsqr.fs_qr_room",
                    room_id=fsqr_room_id,
                    password=password,
                ),
            }
        )

    group_room_id = await group_data.pich_room_id_direct(room_id, password)
    if group_room_id:
        matches.append(
            {
                "service_key": "group",
                "service_name": "グループ共有",
                "description": "グループルームのファイル共有画面を開きます。",
                "url": build_url(
                    request,
                    "group.group_room",
                    room_id=group_room_id,
                    password=password,
                ),
            }
        )

    note_room_id = await note_data.pick_room_id_direct(room_id, password)
    if note_room_id:
        matches.append(
            {
                "service_key": "note",
                "service_name": "ノート共有",
                "description": "リアルタイムノートルームを開きます。",
                "url": build_url(
                    request,
                    "note.note_room",
                    room_id=note_room_id,
                    password=password,
                ),
            }
        )

    return matches


@router.post("/search_all", name="top_search.search_all")
async def search_all(request: Request):
    await enforce_csrf(request)
    form = await request.form()
    id_val = (form.get("id") or "").strip()
    password = (form.get("password") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_TOP_SEARCH, ip)
    if not allowed:
        return _render_result(
            request,
            message=get_block_message(block_label),
            status_code=429,
            searched_id=id_val,
        )

    try:
        search_input = RoomSearchInput(room_id=id_val, password=password)
        id_val, password = search_input.room_id, search_input.password
    except ValidationError:
        _, block_label = await register_failure(SCOPE_TOP_SEARCH, ip)
        if block_label:
            return _render_result(
                request,
                message=get_block_message(block_label),
                status_code=429,
                searched_id=id_val,
            )
        return _render_result(
            request,
            message="IDまたはパスワードに不正な値が含まれています。",
            status_code=400,
            searched_id=id_val,
        )

    matches = await _collect_search_matches(request, id_val, password)
    if not matches:
        _, block_label = await register_failure(SCOPE_TOP_SEARCH, ip)
        if block_label:
            return _render_result(
                request,
                message=get_block_message(block_label),
                status_code=429,
                searched_id=id_val,
            )
        return _render_result(
            request,
            message="一致するルームまたはファイルが見つかりませんでした。",
            status_code=404,
            searched_id=id_val,
        )

    await register_success(SCOPE_TOP_SEARCH, ip)

    if len(matches) == 1:
        return RedirectResponse(matches[0]["url"], status_code=302)

    return _render_result(
        request,
        message="複数のサービスで一致しました。開くサービスを選んでください。",
        status_code=200,
        matches=matches,
        searched_id=id_val,
    )
