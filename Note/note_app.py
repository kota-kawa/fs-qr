import logging
import re
import secrets

from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse

from api_response import api_error_response, api_ok_response
from i18n import is_language_query_only
from models import RoomCreateInput
from rate_limit import (
    SCOPE_NOTE,
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
from web import (
    enforce_csrf,
    get_or_create_csrf_token,
    render_template,
    wants_json_response,
)
from . import note_data as nd
from .note_access import (
    can_delete_note_room,
    forget_note_room_access,
    get_note_room_password,
    get_note_room_share_token,
    has_note_room_access,
    remember_note_room_access,
)
from .note_realtime import hub as note_ws_hub
from .note_realtime import publish_room_expired

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_valid_room_id(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9]{6}$", value)) if value else False


def _generate_room_id() -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(chars) for _ in range(6))


async def _room_id_exists(room_id: str) -> bool:
    rows = await nd._exec(
        "SELECT room_id FROM note_room WHERE room_id = :r",
        {"r": room_id},
        fetch=True,
    )
    return bool(rows)


def _canonical_redirect(request: Request):
    if request.url.query and not is_language_query_only(request):
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


def _gone_response(
    request: Request, message: str = "このノートルームは利用できません。"
):
    response = render_template(request, "error.html", message=message)
    response.status_code = 410
    return response


async def _get_room_if_valid(room_id):
    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        return None
    return meta


def _render_note_room(request: Request, room_id: str, meta: dict):
    retention_days = meta.get("retention_days", 7)
    expires_at = meta.get("expires_at")
    deletion_date = None
    if expires_at:
        try:
            deletion_date = expires_at.strftime("%Y-%m-%d %H:%M")
        except Exception:
            deletion_date = None

    share_token = get_note_room_share_token(request, room_id)
    password = get_note_room_password(request, room_id)
    share_url = (
        build_share_url(request, service_key=ServiceKey.NOTE, token=share_token)
        if share_token
        else ""
    )

    return render_template(
        request,
        "note_room.html",
        room_id=room_id,
        user_id=meta["id"],
        password=password,
        share_url=share_url,
        retention_days=retention_days,
        deletion_date=deletion_date,
        can_delete=can_delete_note_room(request, room_id),
        websocket_csrf_token=get_or_create_csrf_token(request),
    )


@router.get("/note_menu", name="note.note_menu")
async def note_menu(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "note_menu.html")


@router.get("/create_note_room", name="note.create_note_room_page")
async def create_note_room_page(request: Request):
    return render_template(request, "create_note_room.html")


@router.post("/create_note_room", name="note.create_note_room")
async def create_note_room(request: Request):  # noqa: C901
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

    try:
        inp = RoomCreateInput(
            id=raw_id, id_mode=raw_id_mode, retention_days=raw_retention
        )
    except ValidationError:
        return api_error_response("入力内容が不正です。", status_code=400)
    id_val = inp.id
    id_mode = inp.id_mode
    retention_days = inp.retention_days

    if id_mode == "auto":
        if not _is_valid_room_id(id_val):
            id_val = ""
    else:
        try:
            id_val = inp.validate_manual_id()
        except ValueError as exc:
            return api_error_response(str(exc), status_code=400)

    try:
        if id_mode == "auto":
            if id_val and await _room_id_exists(id_val):
                return api_error_response(
                    "生成されたIDが重複しています。新しいIDで再試行してください。",
                    status_code=409,
                    data={"retry_auto": True},
                )
            if not id_val:
                generated = None
                for _ in range(10):
                    candidate = _generate_room_id()
                    if not await _room_id_exists(candidate):
                        generated = candidate
                        break
                if not generated:
                    return api_error_response(
                        "自動生成IDの作成に失敗しました。時間をおいて再試行してください。",
                        status_code=500,
                    )
                id_val = generated
        else:
            if await _room_id_exists(id_val):
                return api_error_response(
                    "このIDは既に使用されています。別のIDを使用してください。",
                    status_code=409,
                )
    except Exception:
        logger.exception("Failed to check note room ID")
        return api_error_response(
            "ルーム作成に失敗しました。時間をおいて再度お試しください。",
            status_code=500,
        )

    room_id = id_val

    password = generate_room_password()
    try:
        await nd.create_room(
            room_id,
            password,
            room_id,
            retention_days=retention_days,
        )
        created = await _get_room_if_valid(room_id)
    except IntegrityError:
        logger.info("Note room ID conflict while creating room_id=%s", room_id)
        return api_error_response(
            "このIDは既に使用されています。別のIDを使用してください。",
            status_code=409,
            data={"retry_auto": id_mode == "auto"},
        )
    except Exception:
        logger.exception("Failed to create note room")
        return api_error_response(
            "ルーム作成に失敗しました。時間をおいて再度お試しください。",
            status_code=500,
        )
    if not created:
        return api_error_response(
            "ルーム作成に失敗しました。時間をおいて再試行してください。",
            status_code=500,
        )
    try:
        share_token = await create_share_link(
            service_key=ServiceKey.NOTE,
            resource_id=room_id,
            expires_at=created.get("expires_at"),
        )
    except Exception:
        logger.exception("Failed to create Note share link: room_id=%s", room_id)
        try:
            await nd.remove_room(room_id)
        except Exception:
            logger.exception("Failed to roll back Note room: room_id=%s", room_id)
        return api_error_response(
            "共有URLの作成に失敗しました。時間をおいて再度お試しください。",
            status_code=500,
        )
    remember_note_room_access(
        request,
        room_id,
        share_token=share_token,
        password=password,
        can_delete=True,
    )
    redirect_url = build_room_url(
        request, service_key=ServiceKey.NOTE, resource_id=room_id
    )
    share_url = build_share_url(request, service_key=ServiceKey.NOTE, token=share_token)
    if wants_json_response(request):
        return api_ok_response(
            {
                "redirect_url": redirect_url,
                "share_url": share_url,
                "password": password,
                "room_id": room_id,
                "expires_at": created.get("expires_at").isoformat(sep=" ")
                if created.get("expires_at")
                else None,
            }
        )
    return RedirectResponse(redirect_url, status_code=302)


@router.get("/note", name="note.note_room_access")
async def note_room_access(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "note_room_access.html")


@router.get("/note/s/{token}", name="note.share_entry")
async def note_share(request: Request, token: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        response = render_template(
            request, "error.html", message=get_block_message(block_label)
        )
        response.status_code = 429
        return response

    token = (token or "").strip()
    if len(token) < 32:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            response = render_template(
                request, "error.html", message=get_block_message(block_label)
            )
            response.status_code = 429
            return response
        response = render_template(request, "error.html", message="共有URLが無効です。")
        response.status_code = 404
        return response

    link = await resolve_share_link(token, service_key=ServiceKey.NOTE)
    if not link:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            response = render_template(
                request, "error.html", message=get_block_message(block_label)
            )
            response.status_code = 429
            return response
        response = render_template(
            request,
            "error.html",
            message="指定されたノートルームが見つからないか、期限切れです。",
        )
        response.status_code = 404
        return response

    await register_success(SCOPE_NOTE, ip)
    room_id = link["resource_id"]
    meta = await _get_room_if_valid(room_id)
    if not meta:
        return _gone_response(
            request, "このノートルームは期限切れ、または削除済みです。"
        )
    row = await nd.get_row(room_id)
    if not row:
        return _gone_response(
            request, "このノートルームは期限切れ、または削除済みです。"
        )
    remember_note_room_access(request, room_id, share_token=token)
    return _render_note_room(request, room_id, meta)


@router.get("/note/r/{room_id}", name="note.note_room")
async def note_room(request: Request, room_id: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        response = render_template(
            request, "error.html", message=get_block_message(block_label)
        )
        response.status_code = 429
        return response

    if not has_note_room_access(request, room_id):
        response = render_template(
            request, "error.html", message="共有URLからアクセスしてください。"
        )
        response.status_code = 404
        return response

    meta = await _get_room_if_valid(room_id)
    if not meta:
        return _gone_response(
            request, "このノートルームは期限切れ、または削除済みです。"
        )

    row = await nd.get_row(room_id)
    if not row:
        return _gone_response(
            request, "このノートルームは期限切れ、または削除済みです。"
        )

    await register_success(SCOPE_NOTE, ip)
    return _render_note_room(request, room_id, meta)


@router.post("/note/r/{room_id}/delete", name="note.delete_own_room")
async def delete_note_room(request: Request, room_id: str):
    await enforce_csrf(request)

    meta = await _get_room_if_valid(room_id)
    if not meta:
        if wants_json_response(request):
            return api_error_response("ルームが見つかりません。", status_code=404)
        response = render_template(request, "error.html", message="ルームが見つかりません。")
        response.status_code = 404
        return response

    if not can_delete_note_room(request, room_id):
        if wants_json_response(request):
            return api_error_response("削除権限がありません。", status_code=403)
        response = render_template(request, "error.html", message="削除権限がありません。")
        response.status_code = 403
        return response

    await nd.remove_room(room_id)
    forget_note_room_access(request, room_id)

    expired_payload = {
        "type": "room_expired",
        "status": "error",
        "data": {},
        "error": "Room has expired or was deleted.",
    }
    await note_ws_hub.broadcast(room_id, expired_payload)
    await publish_room_expired(room_id)
    await note_ws_hub.close_room(room_id)

    if wants_json_response(request):
        return api_ok_response({"redirect_url": "/remove-succes"})
    return RedirectResponse("/remove-succes", status_code=302)


@router.get("/note/{room_id}/{password}", name="note.note_legacy_room")
async def note_legacy_room(request: Request, room_id: str, password: str):
    return _gone_response(
        request,
        "旧形式のノートURLは停止しました。新しい共有URLからアクセスしてください。",
    )


@router.get("/search_note", name="note.search_note_room_page")
async def search_note_room_page(request: Request):
    return render_template(request, "search_note_room.html")


@router.post("/search_note_process", name="note.search_note_room")
async def search_note_room(request: Request):
    await enforce_csrf(request)
    form = await request.form()
    id_val = (form.get("id") or "").strip()
    password = (form.get("password") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        response = render_template(
            request, "error.html", message=get_block_message(block_label)
        )
        response.status_code = 429
        return response

    try:
        id_val, password = validate_room_credentials(id_val, password)
    except ValueError as exc:
        response = render_template(request, "error.html", message=str(exc))
        response.status_code = 400
        return response

    room_id = await nd.pick_room_id(id_val, password)
    if not room_id:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            response = render_template(
                request, "error.html", message=get_block_message(block_label)
            )
            response.status_code = 429
            return response
        response = render_template(
            request, "error.html", message="IDまたはパスワードが違います。"
        )
        response.status_code = 404
        return response

    meta = await _get_room_if_valid(room_id)
    if not meta:
        return _gone_response(
            request, "このノートルームは期限切れ、または削除済みです。"
        )

    await register_success(SCOPE_NOTE, ip)
    remember_note_room_access(request, room_id, password=password)
    return RedirectResponse(
        build_room_url(request, service_key=ServiceKey.NOTE, resource_id=room_id),
        status_code=302,
    )


@router.get("/note_direct/{room_id}/{password}", name="note.note_direct_access")
async def note_direct_access(request: Request, room_id: str, password: str):
    return _gone_response(
        request,
        "旧形式のノート直接アクセスは停止しました。新しい共有URLを使用してください。",
    )
