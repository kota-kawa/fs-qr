from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from session_auth import (
    clear_session_authenticated,
    is_session_authenticated,
    mark_session_authenticated,
    secure_compare_secret,
)
from rate_limit import (
    SCOPE_MANAGEMENT,
    check_rate_limit,
    get_block_message,
    get_client_ip,
    register_failure,
    register_success,
)
from settings import MANAGEMENT_PASSWORD as management_password
from web import enforce_csrf, flash_message, render_template

from . import group_data


def _register_manage_rooms_post(router: APIRouter):
    @router.post("/manage_rooms", name="group.manage_rooms_post")
    async def manage_rooms_post(request: Request):
        await enforce_csrf(request)
        if request.method == "POST":
            form = await request.form()
            password = (form.get("password") or "").strip()
            ip = get_client_ip(request)
            allowed, _, block_label = await check_rate_limit(SCOPE_MANAGEMENT, ip)
            if not allowed:
                flash_message(request, get_block_message(block_label))
                response = render_template(request, "manage_rooms_login.html")
                response.status_code = 429
                return response

            if secure_compare_secret(password, management_password):
                await register_success(SCOPE_MANAGEMENT, ip)
                mark_session_authenticated(request.session, "management_authenticated")
            else:
                _, block_label = await register_failure(SCOPE_MANAGEMENT, ip)
                if block_label:
                    flash_message(request, get_block_message(block_label))
                    response = render_template(request, "manage_rooms_login.html")
                    response.status_code = 429
                    return response
                flash_message(request, "パスワードが違います。")
                return render_template(request, "manage_rooms_login.html")

        if not is_session_authenticated(request.session, "management_authenticated"):
            return render_template(request, "manage_rooms_login.html")

        rooms = await group_data.get_all_direct()
        return render_template(request, "manage_rooms.html", rooms=rooms)


def _register_manage_rooms_get(router: APIRouter):
    @router.get("/manage_rooms", name="group.manage_rooms")
    async def manage_rooms(request: Request):
        if not is_session_authenticated(request.session, "management_authenticated"):
            return render_template(request, "manage_rooms_login.html")

        rooms = await group_data.get_all_direct()
        return render_template(request, "manage_rooms.html", rooms=rooms)


def register_group_manage_page_routes(router: APIRouter):
    _register_manage_rooms_post(router)
    _register_manage_rooms_get(router)


def register_group_logout_management_route(router: APIRouter):
    @router.get("/logout_management", name="group.logout_management")
    async def logout_management(request: Request):
        clear_session_authenticated(request.session, "management_authenticated")
        return RedirectResponse("/manage_rooms", status_code=302)


def _redirect_if_not_management_authenticated(request: Request):
    if not is_session_authenticated(request.session, "management_authenticated"):
        return RedirectResponse("/manage_rooms", status_code=302)
    return None


def register_group_delete_room_route(router: APIRouter):
    @router.post("/delete_room/{room_id}", name="group.delete_room")
    async def delete_room(request: Request, room_id: str):
        await enforce_csrf(request)
        redirect = _redirect_if_not_management_authenticated(request)
        if redirect:
            return redirect
        await group_data.remove_data(room_id)
        return RedirectResponse("/manage_rooms", status_code=302)


def register_group_delete_all_rooms_route(router: APIRouter):
    @router.post("/delete_all_rooms", name="group.delete_all_rooms")
    async def delete_all_rooms(request: Request):
        await enforce_csrf(request)
        redirect = _redirect_if_not_management_authenticated(request)
        if redirect:
            return redirect
        await group_data.all_remove()
        return RedirectResponse("/manage_rooms", status_code=302)
