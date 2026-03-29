import os
import random
import re
from datetime import timedelta

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, RedirectResponse
from werkzeug.utils import secure_filename

from rate_limit import (
    SCOPE_GROUP,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, render_template
from web import enforce_csrf

from . import group_data
from .group_common import UPLOAD_FOLDER, get_room_if_valid
from .group_responses import group_block_response, room_msg


def register_group_room_access_route(router: APIRouter):
    @router.get("/group/{room_id}/{password}", name="group.group_room")
    async def group_room(request: Request, room_id: str, password: str):
        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
        if not allowed:
            return room_msg(request, get_block_message(block_label), status_code=429)

        record = await get_room_if_valid(room_id, password)
        if not record:
            try:
                from Note import note_data as note_data

                meta = await note_data.get_room_meta_direct(room_id, password=password)
                if meta:
                    return RedirectResponse(
                        build_url(
                            request,
                            "note.note_room",
                            room_id=room_id,
                            password=password,
                        ),
                        status_code=302,
                    )
            except Exception:
                pass
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return room_msg(
                    request, get_block_message(block_label), status_code=429
                )
            return room_msg(
                request,
                "指定されたルームが見つからないか、パスワードが違います",
                status_code=404,
            )

        await register_success(SCOPE_GROUP, ip)

        user_id = record.get("id", "不明")
        retention_days = record.get("retention_days", 7)
        created_at = record.get("time")
        deletion_date = None
        if created_at:
            try:
                deletion_date = (created_at + timedelta(days=retention_days)).strftime(
                    "%Y-%m-%d %H:%M"
                )
            except Exception:
                deletion_date = None

        return render_template(
            request,
            "group_room.html",
            room_id=room_id,
            user_id=user_id,
            password=password,
            retention_days=retention_days,
            deletion_date=deletion_date,
        )


def register_group_create_room_route(router: APIRouter):
    @router.post("/create_group_room", name="group.create_group_room")
    async def create_group_room(request: Request):
        await enforce_csrf(request)
        json_data = {}
        form_data = {}
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                json_data = await request.json() or {}
            except Exception:
                json_data = {}
        else:
            form_data = await request.form()

        id_candidates = []
        if form_data and hasattr(form_data, "getlist"):
            id_candidates = form_data.getlist("id")
        if not id_candidates:
            id_candidates = [json_data.get("id", "")]
        id_val = next((str(v).strip() for v in id_candidates if str(v).strip()), "")
        id_mode = (form_data.get("idMode") if form_data else None) or json_data.get(
            "idMode", "auto"
        )

        retention_value = form_data.get("retention_days") if form_data else None
        if retention_value is None:
            retention_value = json_data.get("retention_days", 7)
        try:
            retention_days = int(retention_value)
        except (TypeError, ValueError):
            retention_days = 7

        if retention_days not in (1, 7, 30):
            retention_days = 7

        if not id_val:
            return JSONResponse({"error": "IDが指定されていません。"}, status_code=400)

        if not re.match(r"^[a-zA-Z0-9]+$", id_val):
            return JSONResponse(
                {
                    "error": "IDに無効な文字が含まれています。半角英数字のみ使用してください。"
                },
                status_code=400,
            )
        if len(id_val) != 6:
            return JSONResponse(
                {"error": "IDは6文字の半角英数字で入力してください。"}, status_code=400
            )

        room_id = id_val
        existing_room = await group_data.get_data(room_id)

        if existing_room:
            if id_mode == "auto":
                return JSONResponse(
                    {
                        "error": "生成されたIDが重複しています。新しいIDで再試行してください。",
                        "retry_auto": True,
                    },
                    status_code=409,
                )
            return JSONResponse(
                {"error": "このIDは既に使用されています。別のIDを使用してください。"},
                status_code=409,
            )

        password = str(random.randrange(10**5, 10**6))

        folder_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        os.makedirs(folder_path, exist_ok=True)

        await group_data.create_room(
            id=room_id,
            password=password,
            room_id=room_id,
            retention_days=retention_days,
        )
        return RedirectResponse(
            build_url(request, "group.group_room", room_id=room_id, password=password),
            status_code=302,
        )


def register_group_search_process_route(router: APIRouter):
    @router.post("/search_group_process", name="group.search_room")
    async def search_room(request: Request):
        await enforce_csrf(request)
        form = await request.form()
        id_val = (form.get("id") or "").strip()
        password = (form.get("password") or "").strip()

        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
        if not allowed:
            return group_block_response(request, block_label)

        if not re.match(r"^[a-zA-Z0-9]+$", id_val) or not re.match(
            r"^[0-9]+$", password
        ):
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return group_block_response(request, block_label)
            return JSONResponse(
                {"error": "IDまたはパスワードに不正な値が含まれています。"},
                status_code=400,
            )

        room_id = await group_data.pich_room_id(id_val, password)
        if not room_id:
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return group_block_response(request, block_label)
            return room_msg(request, "IDかパスワードが間違っています", status_code=404)
        await register_success(SCOPE_GROUP, ip)
        return RedirectResponse(
            build_url(request, "group.group_room", room_id=room_id, password=password),
            status_code=302,
        )


def register_group_direct_route(router: APIRouter):
    @router.get("/group_direct/{room_id}/{password}", name="group.group_direct_access")
    async def group_direct_access(request: Request, room_id: str, password: str):
        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
        if not allowed:
            return room_msg(request, get_block_message(block_label), status_code=429)

        record = await get_room_if_valid(room_id, password)
        if not record:
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return room_msg(
                    request, get_block_message(block_label), status_code=429
                )
            return room_msg(
                request, "指定されたルームが見つかりません", status_code=404
            )

        await register_success(SCOPE_GROUP, ip)

        return RedirectResponse(
            build_url(request, "group.group_room", room_id=room_id, password=password),
            status_code=302,
        )
