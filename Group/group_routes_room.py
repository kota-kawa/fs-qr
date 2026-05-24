import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from werkzeug.utils import secure_filename

from api_response import api_error_response, api_ok_response
from models import RoomCreateInput
from rate_limit import (
    SCOPE_GROUP,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from room_credentials import generate_room_password, validate_room_credentials
from share_links import (
    ServiceKey,
    build_room_url,
    build_share_url,
    create_share_link,
    resolve_share_link,
)
from web import get_or_create_csrf_token, render_template
from web import enforce_csrf
from web import wants_json_response

from . import group_data
from .group_common import (
    get_group_room_password,
    get_group_room_share_token,
    get_room_if_active,
    has_group_room_access,
    remember_group_room_access,
)
from .group_responses import room_msg
from .group_storage import UPLOAD_FOLDER

logger = logging.getLogger(__name__)


def register_group_room_access_route(router: APIRouter):
    @router.get("/group/s/{token}", name="group.share_entry")
    async def group_share_entry(request: Request, token: str):
        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
        if not allowed:
            return room_msg(request, get_block_message(block_label), status_code=429)

        link = await resolve_share_link(token, service_key=ServiceKey.GROUP)
        if not link:
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return room_msg(
                    request, get_block_message(block_label), status_code=429
                )
            return room_msg(request, "共有URLが無効です", status_code=404)

        room_id = link["resource_id"]
        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(
                request, "指定されたルームが見つかりません", status_code=404
            )

        await register_success(SCOPE_GROUP, ip)
        remember_group_room_access(request, room_id, token)
        return RedirectResponse(
            build_room_url(request, service_key=ServiceKey.GROUP, resource_id=room_id),
            status_code=302,
        )

    @router.get("/group/r/{room_id}", name="group.group_room")
    async def group_room(request: Request, room_id: str):
        ip = get_client_ip(request)
        allowed, _, block_label = await check_rate_limit(SCOPE_GROUP, ip)
        if not allowed:
            return room_msg(request, get_block_message(block_label), status_code=429)

        if not has_group_room_access(request, room_id):
            return room_msg(
                request, "共有URLからアクセスしてください。", status_code=404
            )

        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(
                request, "指定されたルームが見つかりません", status_code=404
            )

        await register_success(SCOPE_GROUP, ip)

        user_id = record.get("id", "不明")
        retention_days = record.get("retention_days", 7)
        share_token = get_group_room_share_token(request, room_id)
        password = get_group_room_password(request, room_id)
        share_url = (
            build_share_url(request, service_key=ServiceKey.GROUP, token=share_token)
            if share_token
            else ""
        )
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
            share_url=share_url,
            retention_days=retention_days,
            deletion_date=deletion_date,
            websocket_csrf_token=get_or_create_csrf_token(request),
        )

    @router.get("/group/{room_id}/{password}", name="group.group_legacy_room")
    async def group_legacy_room(request: Request, room_id: str, password: str):
        return room_msg(
            request,
            "旧形式のグループURLは停止しました。新しい共有URLからアクセスしてください。",
            status_code=410,
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

        password = generate_room_password()

        folder_path = os.path.join(UPLOAD_FOLDER, secure_filename(room_id))
        os.makedirs(folder_path, exist_ok=True)

        await group_data.create_room(
            id=room_id,
            password=password,
            room_id=room_id,
            retention_days=retention_days,
        )
        try:
            share_token = await create_share_link(
                service_key=ServiceKey.GROUP,
                resource_id=room_id,
                expires_at=datetime.now() + timedelta(days=retention_days),
                metadata={"id": room_id},
            )
        except Exception:
            logger.exception("Failed to create Group share link: room_id=%s", room_id)
            try:
                await group_data.remove_data(room_id)
            except Exception:
                logger.exception("Failed to roll back Group room: room_id=%s", room_id)
            return api_error_response(
                "共有URLの作成に失敗しました。時間をおいて再度お試しください。",
                status_code=500,
            )
        remember_group_room_access(
            request, room_id, share_token=share_token, password=password
        )
        redirect_url = build_room_url(
            request, service_key=ServiceKey.GROUP, resource_id=room_id
        )
        if wants_json_response(request):
            return api_ok_response(
                {
                    "redirect_url": redirect_url,
                    "share_url": build_share_url(
                        request, service_key=ServiceKey.GROUP, token=share_token
                    ),
                    "password": password,
                }
            )
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
            return room_msg(request, get_block_message(block_label), status_code=429)

        try:
            id_val, password = validate_room_credentials(id_val, password)
        except ValueError as exc:
            return room_msg(request, str(exc), status_code=400)

        room_id = await group_data.pich_room_id(id_val, password)
        if not room_id:
            _, block_label = await register_failure(SCOPE_GROUP, ip)
            if block_label:
                return room_msg(
                    request, get_block_message(block_label), status_code=429
                )
            return room_msg(request, "IDまたはパスワードが違います。", status_code=404)

        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(
                request, "指定されたルームが見つかりません", status_code=404
            )

        await register_success(SCOPE_GROUP, ip)
        remember_group_room_access(request, room_id, password=password)
        return RedirectResponse(
            build_room_url(request, service_key=ServiceKey.GROUP, resource_id=room_id),
            status_code=302,
        )


def register_group_direct_route(router: APIRouter):
    @router.get("/group_direct/{room_id}/{password}", name="group.group_direct_access")
    async def group_direct_access(request: Request, room_id: str, password: str):
        return room_msg(
            request,
            "旧形式のグループ直接アクセスは停止しました。新しい共有URLを使用してください。",
            status_code=410,
        )
