import random
import re
from datetime import timedelta

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from api_response import api_error_response
from models import RoomCreateInput, RoomSearchInput
from rate_limit import (
    SCOPE_NOTE,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import (
    build_url,
    enforce_csrf,
    flash_message,
    get_or_create_csrf_token,
    render_template,
)
from . import note_data as nd

router = APIRouter()


def _is_valid_room_id(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9]{6}$", value)) if value else False


def _generate_room_id() -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(6))


async def _room_id_exists(room_id: str) -> bool:
    rows = await nd._exec(
        "SELECT room_id FROM note_room WHERE room_id = :r",
        {"r": room_id},
        fetch=True,
    )
    return bool(rows)


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


async def _get_room_if_valid(room_id, password):
    meta = await nd.get_room_meta_direct(room_id, password=password)
    if not meta:
        return None
    await nd.get_row(room_id)
    return meta


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
async def create_note_room(request: Request):
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

    inp = RoomCreateInput(id=raw_id, id_mode=raw_id_mode, retention_days=raw_retention)
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

    room_id = id_val

    pw = str(random.randrange(10**5, 10**6))
    await nd.create_room(room_id, pw, room_id, retention_days=retention_days)
    created = await _get_room_if_valid(room_id, pw)
    if not created:
        return api_error_response(
            "ルーム作成に失敗しました。時間をおいて再試行してください。",
            status_code=500,
        )
    return RedirectResponse(
        build_url(request, "note.note_room", room_id=room_id, password=pw),
        status_code=302,
    )


@router.get("/note", name="note.note_room_access")
async def note_room_access(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "note_room_access.html")


@router.get("/note/{room_id}/{password}", name="note.note_room")
async def note_room(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        response = render_template(
            request, "error.html", message=get_block_message(block_label)
        )
        response.status_code = 429
        return response

    meta = await _get_room_if_valid(room_id, password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            await register_success(SCOPE_NOTE, ip)
            return RedirectResponse(
                build_url(
                    request,
                    "note.note_room",
                    room_id=fallback_room_id,
                    password=password,
                ),
                status_code=302,
            )
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
            message="指定されたルームが見つからないか、パスワードが間違っています",
        )
        response.status_code = 404
        return response

    await register_success(SCOPE_NOTE, ip)

    retention_days = meta.get("retention_days", 7)
    created_at = meta.get("time")
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
        "note_room.html",
        room_id=room_id,
        user_id=meta["id"],
        password=password,
        retention_days=retention_days,
        deletion_date=deletion_date,
        websocket_csrf_token=get_or_create_csrf_token(request),
    )


@router.get("/search_note", name="note.search_note_room_page")
async def search_note_room_page(request: Request):
    return render_template(request, "search_note_room.html")


@router.post("/search_note_process", name="note.search_note_room")
async def search_note_room(request: Request):
    await enforce_csrf(request)
    form = await request.form()
    id_val = (form.get("id") or "").strip()
    pw = (form.get("password") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        flash_message(request, get_block_message(block_label))
        return RedirectResponse("/search_note", status_code=302)
    try:
        inp = RoomSearchInput(room_id=id_val, password=pw)
        id_val, pw = inp.room_id, inp.password
    except ValidationError:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            flash_message(request, get_block_message(block_label))
        else:
            flash_message(request, "ID またはパスワードが不正です。")
        return RedirectResponse("/search_note", status_code=302)
    room_id = await nd.pich_room_id(id_val, pw)
    if not room_id:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            flash_message(request, get_block_message(block_label))
        else:
            flash_message(request, "ID かパスワードが間違っています。")
        return RedirectResponse("/search_note", status_code=302)
    await register_success(SCOPE_NOTE, ip)
    return RedirectResponse(
        build_url(request, "note.note_room", room_id=room_id, password=pw),
        status_code=302,
    )


@router.get("/note_direct/{room_id}/{password}", name="note.note_direct_access")
async def note_direct_access(request: Request, room_id: str, password: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        response = render_template(
            request, "error.html", message=get_block_message(block_label)
        )
        response.status_code = 429
        return response

    meta = await _get_room_if_valid(room_id, password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            await register_success(SCOPE_NOTE, ip)
            return RedirectResponse(
                build_url(
                    request,
                    "note.note_room",
                    room_id=fallback_room_id,
                    password=password,
                ),
                status_code=302,
            )
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
            message="指定されたルームが見つからないか、パスワードが間違っています",
        )
        response.status_code = 404
        return response

    await register_success(SCOPE_NOTE, ip)

    return RedirectResponse(
        build_url(request, "note.note_room", room_id=room_id, password=password),
        status_code=302,
    )
