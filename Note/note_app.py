import logging
import secrets as _secrets

from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse

from api_response import api_error_response, api_ok_response, error_page_or_json
from models import NoteTaskRoomCreateInput
from rate_limit import (
    SCOPE_NOTE,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from room_credentials import (
    generate_room_id as _secure_generate_room_id,
    generate_room_password,
    is_valid_room_id,
    validate_room_credentials,
)
from room_create import RoomIdConflict, select_room_id
from room_delete import delete_owned_room
from settings import NOTE_MAX_CONTENT_LENGTH
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
    canonical_redirect as shared_canonical_redirect,
    enforce_csrf,
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
from .note_realtime import publish_room_expired
from .note_collaboration import create_collaboration_token

router = APIRouter()
logger = logging.getLogger(__name__)
# 既存テストと外部拡張が参照するモジュール属性を互換維持する。
secrets = _secrets


def _is_valid_room_id(value: str) -> bool:
    return is_valid_room_id(value)


def _generate_room_id() -> str:
    """互換用の名前。実装は共通の安全な生成器へ委譲する。"""
    return _secure_generate_room_id()


async def _room_id_exists(room_id: str) -> bool:
    rows = await nd._exec(
        "SELECT room_id FROM note_room WHERE room_id = :r",
        {"r": room_id},
        fetch=True,
    )
    return bool(rows)


def _extract_initial_content(form_data, json_data) -> str:
    """Read the optional draft body sent from the landing page editor.

    LP のその場エディタから送られた下書き本文を取り出す。未指定なら空文字。
    """
    raw = form_data.get("content") if form_data else None
    if raw is None:
        raw = json_data.get("content", "")
    return "" if raw is None else str(raw)


def _canonical_redirect(request: Request):
    return shared_canonical_redirect(request)


def _gone_response(
    request: Request, message: str = "このノートルームは利用できません。"
):
    return error_page_or_json(request, message, status_code=410)


async def _get_room_if_valid(room_id):
    meta = await nd.get_room_meta_direct(room_id)
    if not meta:
        return None
    return meta


def _render_note_room(request: Request, room_id: str, meta: dict):
    retention_hours = meta.get("retention_hours", 24)
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
        retention_hours=retention_hours,
        deletion_date=deletion_date,
        can_delete=can_delete_note_room(request, room_id),
        yjs_token=create_collaboration_token(room_id),
        presence_scope="note",
        presence_key=room_id,
    )


@router.get("/note_menu", name="note.note_menu")
async def note_menu(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "note_menu.html")


@router.get("/shared-note", name="note.landing")
async def note_landing(request: Request):
    """Render the acquisition-focused FS!QR Note landing page.

    共同編集の価値を説明するLPと、作成・参加の機能画面を分離する。
    """
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "note_landing.html")


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
    raw_retention = form_data.get("retention_hours") if form_data else None
    if raw_retention is None:
        raw_retention = json_data.get("retention_hours", 24)

    initial_content = _extract_initial_content(form_data, json_data)
    if len(initial_content) > NOTE_MAX_CONTENT_LENGTH:
        return api_error_response(
            f"下書きが長すぎます。{NOTE_MAX_CONTENT_LENGTH}文字以内にしてください。",
            status_code=400,
        )

    try:
        inp = NoteTaskRoomCreateInput(
            id=raw_id, id_mode=raw_id_mode, retention_hours=raw_retention
        )
    except ValidationError:
        return api_error_response("入力内容が不正です。", status_code=400)
    id_val = inp.id
    id_mode = inp.id_mode
    retention_hours = inp.retention_hours

    if id_mode == "auto":
        if not _is_valid_room_id(id_val):
            id_val = ""
    else:
        try:
            id_val = inp.validate_manual_id()
        except ValueError as exc:
            return api_error_response(str(exc), status_code=400)

    try:
        selection = await select_room_id(
            id_val,
            id_mode,
            _room_id_exists,
            generator=_generate_room_id,
        )
        if selection.retry_auto:
            return api_error_response(
                "生成されたIDが重複しています。新しいIDで再試行してください。",
                status_code=409,
                data={"retry_auto": True},
            )
        if not selection.room_id:
            return api_error_response(
                "自動生成IDの作成に失敗しました。時間をおいて再試行してください。",
                status_code=500,
            )
        id_val = selection.room_id
    except RoomIdConflict:
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
            retention_hours=retention_hours,
            initial_content=initial_content,
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
            metadata={
                "id": room_id,
                "password_enc": encrypt_share_password(password),
            },
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
        return error_page_or_json(
            request, get_block_message(block_label), status_code=429
        )

    token = (token or "").strip()
    if len(token) < 32:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            return error_page_or_json(
                request, get_block_message(block_label), status_code=429
            )
        return error_page_or_json(request, "共有URLが無効です。", status_code=404)

    link = await resolve_share_link(token, service_key=ServiceKey.NOTE)
    if not link:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            return error_page_or_json(
                request, get_block_message(block_label), status_code=429
            )
        return error_page_or_json(
            request,
            "指定されたノートルームが見つからないか、期限切れです。",
            status_code=404,
        )

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
    link_password = share_link_password(link)
    remember_note_room_access(
        request, room_id, share_token=token, password=link_password
    )
    return _render_note_room(request, room_id, meta)


@router.get("/note/r/{room_id}", name="note.note_room")
async def note_room(request: Request, room_id: str):
    ip = get_client_ip(request)
    allowed, _, block_label = await check_rate_limit(SCOPE_NOTE, ip)
    if not allowed:
        return error_page_or_json(
            request, get_block_message(block_label), status_code=429
        )

    if not has_note_room_access(request, room_id):
        return error_page_or_json(
            request, "共有URLからアクセスしてください。", status_code=404
        )

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

    outcome = await delete_owned_room(
        request,
        room_id,
        get_active=_get_room_if_valid,
        can_delete=lambda req, key, record: can_delete_note_room(req, key),
        remove=nd.remove_room,
        forget=forget_note_room_access,
    )
    if outcome.status == "not_found":
        return error_page_or_json(request, "ルームが見つかりません。", status_code=404)
    if outcome.status == "forbidden":
        return error_page_or_json(request, "削除権限がありません。", status_code=403)
    if outcome.status == "failed":
        return error_page_or_json(
            request,
            "ルーム削除に失敗しました。時間をおいて再度お試しください。",
            status_code=500,
        )

    # Hocuspocus instances subscribe to this shared close event.
    # 全 Hocuspocus instance が購読する共有クローズイベントを送る。
    await publish_room_expired(room_id)

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
        return error_page_or_json(
            request, get_block_message(block_label), status_code=429
        )

    try:
        id_val, password = validate_room_credentials(id_val, password)
    except ValueError as exc:
        return error_page_or_json(request, str(exc), status_code=400)

    room_id = await nd.pick_room_id(id_val, password)
    if not room_id:
        _, block_label = await register_failure(SCOPE_NOTE, ip)
        if block_label:
            return error_page_or_json(
                request, get_block_message(block_label), status_code=429
            )
        return error_page_or_json(
            request, "IDまたはパスワードが違います。", status_code=404
        )

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
