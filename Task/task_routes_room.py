from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse

from api_response import api_error_response, api_ok_response
from models import RoomCreateInput
from rate_limit import (
    SCOPE_TASK,
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
    encrypt_share_password,
    resolve_share_link,
    share_link_password,
)
from web import (
    enforce_csrf,
    render_template,
    wants_json_response,
)
from . import task_data
from .task_common import (
    can_delete_task_room,
    forget_task_room_access,
    get_room_if_active,
    get_task_room_password,
    get_task_room_share_token,
    has_task_room_access,
    remember_task_room_access,
)
from .task_responses import room_msg

logger = logging.getLogger(__name__)
ROOM_ID_CHARS = string.ascii_letters + string.digits
ROOM_ID_ATTEMPTS = 10


def _generate_room_id() -> str:
    return "".join(secrets.choice(ROOM_ID_CHARS) for _ in range(6))


def _valid_manual_id(room_id: str) -> bool:
    try:
        RoomCreateInput(id=room_id, id_mode="manual").validate_manual_id()
    except (ValidationError, ValueError):
        return False
    return True


async def _create_task_share_token(
    room_id: str, password: str, retention_hours: int
) -> str:
    try:
        return await create_share_link(
            service_key=ServiceKey.TASK,
            resource_id=room_id,
            expires_at=datetime.now() + timedelta(hours=retention_hours),
            metadata={"id": room_id, "password_enc": encrypt_share_password(password)},
        )
    except Exception:
        logger.exception("Failed to create Task share link: room_id=%s", room_id)
        return ""


def _render_task_room(request: Request, room_id: str, record: dict):
    share_token = get_task_room_share_token(request, room_id)
    expires_at = record.get("expires_at")
    return render_template(
        request,
        "task_board.html",
        room_id=room_id,
        user_id=record.get("id", ""),
        password=get_task_room_password(request, room_id),
        share_url=build_share_url(
            request, service_key=ServiceKey.TASK, token=share_token
        )
        if share_token
        else "",
        retention_hours=record.get("retention_hours", 24),
        deletion_date=expires_at.strftime("%Y-%m-%d %H:%M") if expires_at else None,
        can_delete=can_delete_task_room(request, room_id),
        presence_scope="task",
        presence_key=room_id,
    )


def register_task_room_access_routes(router: APIRouter) -> None:
    @router.get("/task/s/{token}", name="task.share_entry")
    async def task_share_entry(request: Request, token: str):
        ip = get_client_ip(request)
        allowed, _, label = await check_rate_limit(SCOPE_TASK, ip)
        if not allowed:
            return room_msg(request, get_block_message(label), 429)
        link = await resolve_share_link(token, service_key=ServiceKey.TASK)
        if not link:
            _, label = await register_failure(SCOPE_TASK, ip)
            return room_msg(
                request,
                get_block_message(label) if label else "共有URLが無効です",
                429 if label else 404,
            )
        room_id = link["resource_id"]
        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(request, "指定されたルームが見つかりません", 404)
        await register_success(SCOPE_TASK, ip)
        remember_task_room_access(
            request, room_id, share_token=token, password=share_link_password(link)
        )
        return _render_task_room(request, room_id, record)

    # /task/s and /task/r must precede this legacy catch-all route.
    @router.get("/task/r/{room_id}", name="task.task_room")
    async def task_room(request: Request, room_id: str):
        if not has_task_room_access(request, room_id):
            return room_msg(request, "共有URLまたは検索からアクセスしてください。", 404)
        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(request, "指定されたルームが見つかりません", 404)
        return _render_task_room(request, room_id, record)

    @router.get("/task/{room_id}/{password}", name="task.legacy_room")
    async def task_legacy_room(request: Request, room_id: str, password: str):
        return room_msg(
            request, "旧形式のTask URLは停止しました。共有URLを使用してください。", 410
        )


def register_task_create_room_route(router: APIRouter) -> None:
    @router.post("/create_task_room", name="task.create_task_room")
    async def create_task_room(request: Request):
        await enforce_csrf(request)
        json_data: dict = {}
        form_data = None
        if "application/json" in request.headers.get("content-type", ""):
            try:
                json_data = await request.json() or {}
            except Exception:
                json_data = {}
        else:
            form_data = await request.form()
        raw_id = str(
            (form_data.get("id") if form_data else json_data.get("id", "")) or ""
        ).strip()
        raw_mode = (
            form_data.get("idMode") if form_data else json_data.get("idMode")
        ) or "auto"
        raw_retention = (
            form_data.get("retention_hours")
            if form_data
            else json_data.get("retention_hours")
        ) or 24
        try:
            inp = RoomCreateInput(
                id=raw_id, id_mode=raw_mode, retention_hours=raw_retention
            )
            room_id = (
                inp.validate_manual_id()
                if inp.id_mode != "auto"
                else (inp.id if _valid_manual_id(inp.id) else "")
            )
        except (ValidationError, ValueError) as exc:
            return api_error_response(
                str(exc) or "入力内容が不正です。", status_code=400
            )
        if not room_id:
            for _ in range(ROOM_ID_ATTEMPTS):
                candidate = _generate_room_id()
                if not await task_data.get_room_meta_direct(candidate):
                    room_id = candidate
                    break
        elif await task_data.get_room_meta_direct(room_id):
            return api_error_response(
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
                data={"retry_auto": inp.id_mode == "auto"},
            )
        if not room_id:
            return api_error_response(
                "自動生成IDの作成に失敗しました。", status_code=500
            )
        password = generate_room_password()
        try:
            await task_data.create_room(room_id, password, room_id, inp.retention_hours)
        except IntegrityError:
            return api_error_response(
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
                data={"retry_auto": inp.id_mode == "auto"},
            )
        except Exception:
            logger.exception("Failed to create task room")
            return api_error_response("ルーム作成に失敗しました。", status_code=500)
        share_token = await _create_task_share_token(
            room_id, password, inp.retention_hours
        )
        remember_task_room_access(
            request,
            room_id,
            share_token=share_token,
            password=password,
            can_delete=True,
        )
        redirect_url = build_room_url(
            request, service_key=ServiceKey.TASK, resource_id=room_id
        )
        if wants_json_response(request):
            return api_ok_response(
                {
                    "redirect_url": redirect_url,
                    "share_url": build_share_url(
                        request, service_key=ServiceKey.TASK, token=share_token
                    )
                    if share_token
                    else "",
                    "password": password,
                }
            )
        return RedirectResponse(redirect_url, 302)


def register_task_search_process_route(router: APIRouter) -> None:
    @router.post("/search_task_process", name="task.search_task_room")
    async def search_task_room(request: Request):
        await enforce_csrf(request)
        form = await request.form()
        ip = get_client_ip(request)
        allowed, _, label = await check_rate_limit(SCOPE_TASK, ip)
        if not allowed:
            return room_msg(request, get_block_message(label), 429)
        try:
            id_, password = validate_room_credentials(
                str(form.get("id") or ""), str(form.get("password") or "")
            )
        except ValueError as exc:
            return room_msg(request, str(exc), 400)
        room_id = await task_data.pick_room_id_direct(id_, password)
        if not room_id or not await get_room_if_active(room_id):
            _, label = await register_failure(SCOPE_TASK, ip)
            return room_msg(
                request,
                get_block_message(label) if label else "IDまたはパスワードが違います。",
                429 if label else 404,
            )
        await register_success(SCOPE_TASK, ip)
        remember_task_room_access(request, room_id, password=password)
        return RedirectResponse(
            build_room_url(request, service_key=ServiceKey.TASK, resource_id=room_id),
            302,
        )


def register_task_delete_own_room_route(router: APIRouter) -> None:
    @router.post("/task/r/{room_id}/delete", name="task.delete_own_room")
    async def delete_own_room(request: Request, room_id: str):
        await enforce_csrf(request)
        if not await get_room_if_active(room_id):
            return api_error_response("ルームが見つかりません。", status_code=404)
        if not can_delete_task_room(request, room_id):
            return api_error_response("削除権限がありません。", status_code=403)
        await task_data.remove_room(room_id)
        forget_task_room_access(request, room_id)
        return (
            api_ok_response({"redirect_url": "/remove-succes"})
            if wants_json_response(request)
            else RedirectResponse("/remove-succes", 302)
        )
