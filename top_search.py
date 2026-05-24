from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from FSQR import fsqr_data
from FSQR.fsqr_app import _remember_fsqr_access
from Group import group_data
from Group.group_common import get_room_if_active, remember_group_room_access
from Note import note_data
from Note.note_access import remember_note_room_access
from rate_limit import (
    SCOPE_TOP_SEARCH,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from room_credentials import validate_room_credentials
from share_links import ServiceKey, build_room_url
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
        id_val, password = validate_room_credentials(id_val, password)
    except ValueError as exc:
        return _render_result(
            request,
            message=str(exc),
            status_code=400,
            searched_id=id_val,
        )

    matches = []

    fsqr_rows = await fsqr_data.get_data_by_credentials(id_val, password)
    if fsqr_rows:
        record = fsqr_rows[0]
        secure_id = record.get("secure_id")
        if secure_id:
            _remember_fsqr_access(request, secure_id, id_val, password)
            matches.append(
                {
                    "service_key": "fsqr",
                    "service_name": "FSQR",
                    "description": "ファイル共有のダウンロードページを開きます。",
                    "url": build_url(request, "fsqr.download", secure_id=secure_id),
                }
            )

    group_room_id = await group_data.pich_room_id(id_val, password)
    if group_room_id and await get_room_if_active(group_room_id):
        remember_group_room_access(request, group_room_id, password=password)
        matches.append(
            {
                "service_key": "group",
                "service_name": "Group",
                "description": "グループファイル共有ルームを開きます。",
                "url": build_room_url(
                    request, service_key=ServiceKey.GROUP, resource_id=group_room_id
                ),
            }
        )

    note_room_id = await note_data.pick_room_id(id_val, password)
    note_meta = (
        await note_data.get_room_meta_direct(note_room_id) if note_room_id else None
    )
    if note_room_id and note_meta:
        remember_note_room_access(request, note_room_id, password=password)
        matches.append(
            {
                "service_key": "note",
                "service_name": "Note",
                "description": "リアルタイムノートルームを開きます。",
                "url": build_room_url(
                    request, service_key=ServiceKey.NOTE, resource_id=note_room_id
                ),
            }
        )

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
            message="一致するルームが見つかりませんでした。",
            status_code=404,
            searched_id=id_val,
        )

    await register_success(SCOPE_TOP_SEARCH, ip)
    if len(matches) == 1:
        return RedirectResponse(matches[0]["url"], status_code=302)

    return _render_result(
        request,
        message="一致するルームが複数あります。開くサービスを選択してください。",
        status_code=200,
        matches=matches,
        searched_id=id_val,
    )
