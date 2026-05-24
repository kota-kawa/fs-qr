from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from rate_limit import (
    SCOPE_TOP_SEARCH,
    check_rate_limit,
    get_block_message,
    get_client_ip,
)
from web import enforce_csrf, render_template

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

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_TOP_SEARCH, ip)
    if not allowed:
        return _render_result(
            request,
            message=get_block_message(block_label),
            status_code=429,
            searched_id=id_val,
        )

    return _render_result(
        request,
        message="IDとパスワードによる一括検索は停止しました。共有URLを使用してください。",
        status_code=410,
        searched_id=id_val,
    )
