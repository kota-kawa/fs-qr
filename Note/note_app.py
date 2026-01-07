import random
import re
from datetime import timedelta

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, RedirectResponse

from rate_limit import (
    SCOPE_NOTE,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from web import build_url, flash_message, render_template
from . import note_data as nd

router = APIRouter()


_ROOM_ID_RE = re.compile(r"^[a-zA-Z0-9]{6}$")


def _is_valid_room_id(value: str) -> bool:
    return bool(value) and bool(_ROOM_ID_RE.match(value))


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
    id_mode = (form_data.get("idMode") if form_data else None) or json_data.get("idMode", "auto")

    retention_value = form_data.get("retention_days") if form_data else None
    if retention_value is None:
        retention_value = json_data.get("retention_days", 7)
    try:
        retention_days = int(retention_value)
    except (TypeError, ValueError):
        retention_days = 7

    if retention_days not in (1, 7, 30):
        retention_days = 7

    if id_mode == "auto":
        if not _is_valid_room_id(id_val):
            id_val = ""
    else:
        if not id_val:
            return JSONResponse({"error": "IDが指定されていません。"}, status_code=400)
        if not _is_valid_room_id(id_val):
            if not re.match(r"^[a-zA-Z0-9]+$", id_val):
                return JSONResponse(
                    {"error": "IDに無効な文字が含まれています。半角英数字のみ使用してください。"},
                    status_code=400,
                )
            return JSONResponse({"error": "IDは6文字の半角英数字で入力してください"}, status_code=400)

    if id_mode == "auto":
        if id_val and await _room_id_exists(id_val):
            return JSONResponse(
                {"error": "生成されたIDが重複しています。新しいIDで再試行してください。", "retry_auto": True},
                status_code=409,
            )
        if not id_val:
            generated = None
            for _ in range(10):
                candidate = _generate_room_id()
                if not await _room_id_exists(candidate):
                    generated = candidate
                    break
            if not generated:
                return JSONResponse(
                    {"error": "自動生成IDの作成に失敗しました。時間をおいて再試行してください。"},
                    status_code=500,
                )
            id_val = generated
    else:
        if await _room_id_exists(id_val):
            return JSONResponse({"error": "このIDは既に使用されています。別のIDを使用してください。"}, status_code=409)

    room_id = id_val

    pw = str(random.randrange(10**5, 10**6))
    await nd.create_room(room_id, pw, room_id, retention_days=retention_days)
    created = await _get_room_if_valid(room_id, pw)
    if not created:
        return JSONResponse(
            {"error": "ルーム作成に失敗しました。時間をおいて再試行してください。"},
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
        response = render_template(request, "error.html", message=get_block_message(block_label))
        response.status_code = 429
        return response

    meta = await _get_room_if_valid(room_id, password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            await register_success(SCOPE_NOTE, ip)
            return RedirectResponse(
                build_url(request, "note.note_room", room_id=fallback_room_id, password=password),
                status_code=302,
            )
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            response = render_template(request, "error.html", message=get_block_message(block_label))
            response.status_code = 429
            return response
        response = render_template(
            request, "error.html", message="指定されたルームが見つからないか、パスワードが間違っています"
        )
        response.status_code = 404
        return response

    await register_success(SCOPE_NOTE, ip)

    retention_days = meta.get("retention_days", 7)
    created_at = meta.get("time")
    deletion_date = None
    if created_at:
        try:
            deletion_date = (created_at + timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M")
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
    )


@router.get("/search_note", name="note.search_note_room_page")
async def search_note_room_page(request: Request):
    return render_template(request, "search_note_room.html")


@router.post("/search_note_process", name="note.search_note_room")
async def search_note_room(request: Request):
    form = await request.form()
    id_val = (form.get("id") or "").strip()
    pw = (form.get("password") or "").strip()

    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        flash_message(request, get_block_message(block_label))
        return RedirectResponse("/search_note", status_code=302)
    if not re.match(r"^[a-zA-Z0-9]+$", id_val) or not re.match(r"^[0-9]+$", pw):
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
        response = render_template(request, "error.html", message=get_block_message(block_label))
        response.status_code = 429
        return response

    meta = await _get_room_if_valid(room_id, password)
    if not meta:
        fallback_room_id = await nd.pick_room_id_direct(room_id, password)
        if fallback_room_id:
            await register_success(SCOPE_NOTE, ip)
            return RedirectResponse(
                build_url(request, "note.note_room", room_id=fallback_room_id, password=password),
                status_code=302,
            )
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            response = render_template(request, "error.html", message=get_block_message(block_label))
            response.status_code = 429
            return response
        response = render_template(
            request, "error.html", message="指定されたルームが見つからないか、パスワードが間違っています"
        )
        response.status_code = 404
        return response

    await register_success(SCOPE_NOTE, ip)

    return RedirectResponse(
        build_url(request, "note.note_room", room_id=room_id, password=password),
        status_code=302,
    )
