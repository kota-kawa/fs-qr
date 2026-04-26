import os
import shutil

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from FSQR import fsqr_data as fs_data
from FSQR.fsqr_app import msg
from session_auth import (
    clear_session_authenticated,
    is_session_authenticated,
    mark_session_authenticated,
)
from settings import ADMIN_KEY
from web import enforce_csrf, flash_message, render_template

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ADMIN_SESSION_KEY = "admin_authenticated"


def _is_admin_authenticated(request: Request) -> bool:
    return is_session_authenticated(request.session, ADMIN_SESSION_KEY)


@router.get("/admin/list", name="admin.admin_list")
async def admin_list(request: Request):
    if request.url.query:
        return RedirectResponse(str(request.url.replace(query="")), status_code=302)
    if not _is_admin_authenticated(request):
        return render_template(request, "admin_login.html")
    return render_template(request, "admin_list.html", files=await fs_data.get_all())


@router.post("/admin/list", name="admin.admin_login")
async def admin_login(request: Request):
    await enforce_csrf(request)
    form = await request.form()
    pw = (form.get("pw") or "").strip()
    if pw != ADMIN_KEY:
        flash_message(request, "マスターパスワードが違います")
        return render_template(request, "admin_login.html")
    mark_session_authenticated(request.session, ADMIN_SESSION_KEY)
    return RedirectResponse("/admin/list", status_code=302)


@router.get("/admin/logout", name="admin.admin_logout")
async def admin_logout(request: Request):
    clear_session_authenticated(request.session, ADMIN_SESSION_KEY)
    return RedirectResponse("/admin/list", status_code=302)


@router.post("/admin/remove/{secure_id}", name="admin.admin_remove")
async def admin_remove(request: Request, secure_id: str):
    if not _is_admin_authenticated(request):
        flash_message(request, "管理者として再ログインしてください")
        return RedirectResponse("/admin/list", status_code=302)
    await enforce_csrf(request)

    data = await fs_data.get_data(secure_id)
    if not data:
        return msg(request, "パラメータが不正です")

    await fs_data.remove_data(secure_id)
    return RedirectResponse("/remove-succes", status_code=302)


@router.post("/all-remove", name="admin.all")
async def all_remove(request: Request):
    if not _is_admin_authenticated(request):
        flash_message(request, "管理者として再ログインしてください")
        return RedirectResponse("/admin/list", status_code=302)
    await enforce_csrf(request)

    await fs_data.all_remove()
    shutil.rmtree(os.path.join(BASE_DIR, "static", "upload"))
    os.mkdir(os.path.join(BASE_DIR, "static", "upload"))
    return RedirectResponse("/remove-succes", status_code=302)
