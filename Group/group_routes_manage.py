from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from session_auth import (
    clear_session_authenticated,
    is_session_authenticated,
    mark_session_authenticated,
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
            password = form.get("password")
            if password == management_password:
                mark_session_authenticated(request.session, "management_authenticated")
            else:
                flash_message(request, "パスワードが違います。 সন")
                return render_template(request, "manage_rooms_login.html")

        if not is_session_authenticated(request.session, "management_authenticated"):
            return render_template(request, "manage_rooms_login.html")

        rooms = await group_data.get_all()
        return render_template(request, "manage_rooms.html", rooms=rooms)


def _register_manage_rooms_get(router: APIRouter):
    @router.get("/manage_rooms", name="group.manage_rooms")
    async def manage_rooms(request: Request):
        if not is_session_authenticated(request.session, "management_authenticated"):
            return render_template(request, "manage_rooms_login.html")

        rooms = await group_data.get_all()
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
