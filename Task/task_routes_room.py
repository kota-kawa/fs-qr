from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse

from api_response import api_error_response, api_ok_response, error_page_or_json
from models import NoteTaskRoomCreateInput, RoomCreateInput
from rate_limit import (
    SCOPE_TASK,
    check_rate_limit,
    get_client_ip,
    register_failure,
    register_success,
)
from room_credentials import (
    generate_room_id as _secure_generate_room_id,
    generate_room_password,
    validate_room_credentials,
)
from room_create import RoomIdConflict, select_room_id
from room_delete import delete_owned_room
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
from .task_responses import (
    room_msg,
    task_api_error,
    task_message,
    task_rate_limit_message,
    task_validation_message,
)

logger = logging.getLogger(__name__)
ROOM_ID_ATTEMPTS = 10


def _generate_room_id() -> str:
    """互換用の名前。実装は共通の安全な生成器へ委譲する。"""
    return _secure_generate_room_id()


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
            return room_msg(request, task_rate_limit_message(label), 429)
        link = await resolve_share_link(token, service_key=ServiceKey.TASK)
        if not link:
            _, label = await register_failure(SCOPE_TASK, ip)
            return room_msg(
                request,
                task_rate_limit_message(label)
                if label
                else task_message("task.share_invalid", "共有URLが無効です。"),
                429 if label else 404,
            )
        room_id = link["resource_id"]
        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(
                request,
                task_message(
                    "task.room_not_found", "指定されたルームが見つかりません。"
                ),
                404,
            )
        await register_success(SCOPE_TASK, ip)
        remember_task_room_access(
            request, room_id, share_token=token, password=share_link_password(link)
        )
        return _render_task_room(request, room_id, record)

    # /task/s and /task/r must precede this legacy catch-all route.
    @router.get("/task/r/{room_id}", name="task.task_room")
    async def task_room(request: Request, room_id: str):
        if not has_task_room_access(request, room_id):
            return room_msg(
                request,
                task_message(
                    "task.access_required",
                    "共有URLまたは検索からアクセスしてください。",
                ),
                404,
            )
        record = await get_room_if_active(room_id)
        if not record:
            return room_msg(
                request,
                task_message(
                    "task.room_not_found", "指定されたルームが見つかりません。"
                ),
                404,
            )
        return _render_task_room(request, room_id, record)

    @router.get("/task/{room_id}/{password}", name="task.legacy_room")
    async def task_legacy_room(request: Request, room_id: str, password: str):
        return room_msg(
            request,
            task_message(
                "task.legacy_url",
                "旧形式のTask URLは停止しました。共有URLを使用してください。",
            ),
            410,
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
            inp = NoteTaskRoomCreateInput(
                id=raw_id, id_mode=raw_mode, retention_hours=raw_retention
            )
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc):
                message = task_validation_message(exc)
            else:
                message = task_message("task.request_error", "入力内容が不正です。")
            return api_error_response(message, status_code=400)
        try:
            selection = await select_room_id(
                raw_id,
                inp.id_mode,
                _task_room_exists,
                attempts=ROOM_ID_ATTEMPTS,
                generator=_generate_room_id,
            )
        except RoomIdConflict:
            return task_api_error(
                "task.id_in_use",
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
                data={"retry_auto": inp.id_mode == "auto"},
            )
        except ValueError as exc:
            return task_api_error(
                "task.request_error", task_validation_message(exc), status_code=400
            )
        if selection.retry_auto:
            return task_api_error(
                "task.id_in_use",
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
                data={"retry_auto": True},
            )
        room_id = selection.room_id
        if not room_id:
            return task_api_error(
                "task.auto_id_failed",
                "自動生成IDの作成に失敗しました。",
                status_code=500,
            )
        password = generate_room_password()
        try:
            await task_data.create_room(room_id, password, room_id, inp.retention_hours)
        except IntegrityError:
            return task_api_error(
                "task.id_in_use",
                "このIDは既に使用されています。別のIDを使用してください。",
                status_code=409,
                data={"retry_auto": inp.id_mode == "auto"},
            )
        except Exception:
            logger.exception("Failed to create task room")
            return task_api_error(
                "task.room_create_failed", "ルーム作成に失敗しました。", status_code=500
            )
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
                    # LP 側で共有情報を表示し、初期タスクを投入するために room_id も返す
                    "room_id": room_id,
                }
            )
        return RedirectResponse(redirect_url, 302)


async def _task_room_exists(room_id: str) -> bool:
    """共通 ID 選択器へ渡す Task 用存在確認。"""
    return bool(await task_data.get_room_meta_direct(room_id))


def register_task_search_process_route(router: APIRouter) -> None:
    @router.post("/search_task_process", name="task.search_task_room")
    async def search_task_room(request: Request):
        await enforce_csrf(request)
        form = await request.form()
        ip = get_client_ip(request)
        allowed, _, label = await check_rate_limit(SCOPE_TASK, ip)
        if not allowed:
            return room_msg(request, task_rate_limit_message(label), 429)
        try:
            id_, password = validate_room_credentials(
                str(form.get("id") or ""), str(form.get("password") or "")
            )
        except ValueError as exc:
            return room_msg(request, task_validation_message(exc), 400)
        room_id = await task_data.pick_room_id_direct(id_, password)
        if not room_id or not await get_room_if_active(room_id):
            _, label = await register_failure(SCOPE_TASK, ip)
            return room_msg(
                request,
                task_rate_limit_message(label)
                if label
                else task_message(
                    "task.invalid_credentials", "IDまたはパスワードが違います。"
                ),
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
        outcome = await delete_owned_room(
            request,
            room_id,
            get_active=get_room_if_active,
            can_delete=lambda req, key, record: can_delete_task_room(req, key),
            remove=task_data.remove_room,
            forget=forget_task_room_access,
        )
        if outcome.status == "not_found":
            message = task_message("task.room_not_found", "ルームが見つかりません。")
            return error_page_or_json(request, message, status_code=404)
        if outcome.status == "forbidden":
            message = task_message("task.delete_permission", "削除権限がありません。")
            return error_page_or_json(request, message, status_code=403)
        if outcome.status == "failed":
            message = task_message(
                "task.delete_failed",
                "ルーム削除に失敗しました。時間をおいて再度お試しください。",
            )
            return error_page_or_json(request, message, status_code=500)
        return (
            api_ok_response({"redirect_url": "/remove-succes"})
            if wants_json_response(request)
            else RedirectResponse("/remove-succes", 302)
        )
