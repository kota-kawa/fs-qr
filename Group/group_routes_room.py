import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.responses import RedirectResponse
from werkzeug.utils import secure_filename

from api_response import api_error_response, api_ok_response
from models import RoomCreateInput, RoomSearchInput
from rate_limit import (
    SCOPE_GROUP,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, get_or_create_csrf_token, render_template
from web import enforce_csrf
from web import wants_json_response

from . import group_data
from .group_common import UPLOAD_FOLDER, get_room_if_valid, remember_group_room_access
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
        remember_group_room_access(request, room_id, password)

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
            websocket_csrf_token=get_or_create_csrf_token(request),
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
        raw_id = next((str(v).strip() for v in id_candidates if str(v).strip()), "")
        raw_id_mode = (form_data.get("idMode") if form_data else None) or json_data.get(
            "idMode", "auto"
        )
        raw_retention = form_data.get("retention_days") if form_data else None
        if raw_retention is None:
            raw_retention = json_data.get("retention_days", 7)

        inp = RoomCreateInput(
            id=raw_id, id_mode=raw_id_mode, retention_days=raw_retention
        )
        retention_days = inp.retention_days

        if inp.id_mode != "auto":
            try:
                id_val = inp.validate_manual_id()
            except ValueError as exc:
                return api_error_response(str(exc), status_code=400)
        else:
            id_val = inp.id
            if not id_val:
                return api_error_response(
                    "IDが取得できませんでした。再度お試しください。",
                    status_code=400,
                )

        room_id = id_val
        existing_room = await group_data.get_data(room_id)

        if existing_room:
            if inp.id_mode == "auto":
                return api_error_response(
                    "生成されたIDが重複しています。新しいIDで再試行してください。",
                    status_code=409,
                    data={"retry_auto": True},
                )
            return api_error_response(
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
            )

        password = secrets.token_urlsafe(8)

        folder_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        os.makedirs(folder_path, exist_ok=True)

        await group_data.create_room(
            id=room_id,
            password=password,
            room_id=room_id,
            retention_days=retention_days,
        )
        redirect_url = build_url(
            request, "group.group_room", room_id=room_id, password=password
        )
        if wants_json_response(request):
            return api_ok_response({"redirect_url": redirect_url})
        return RedirectResponse(redirect_url, status_code=302)


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

        try:
            search_inp = RoomSearchInput(room_id=id_val, password=password)
            id_val, password = search_inp.room_id, search_inp.password
        except ValidationError:
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return group_block_response(request, block_label)
            return api_error_response(
                "IDまたはパスワードに不正な値が含まれています。",
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
