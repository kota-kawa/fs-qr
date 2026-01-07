import os
import shutil

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from FSQR import fsqr_data as fs_data
from FSQR.fsqr_app import msg
from settings import ADMIN_KEY
from web import render_template

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


@router.get("/admin/list", name="admin.admin_list")
async def admin_list(request: Request, pw: str = ""):
    if pw != ADMIN_KEY:
        return msg(request, "マスターパスワードが違います")
    return render_template(request, "admin_list.html", files=fs_data.get_all(), pw=ADMIN_KEY)


@router.get("/admin/remove/{secure_id}", name="admin.admin_remove")
async def admin_remove(request: Request, secure_id: str, pw: str = ""):
    if pw != ADMIN_KEY:
        return msg(request, "マスターパスワードが違います")

    data = fs_data.get_data(secure_id)
    if not data:
        return msg(request, "パラメータが不正です")

    fs_data.remove_data(secure_id)
    return RedirectResponse("/remove-succes", status_code=302)


@router.post("/all-remove", name="admin.all")
async def all_remove(request: Request):
    form = await request.form()
    if form.get("pw", "") != ADMIN_KEY:
        return msg(request, "マスターパスワードが違います")

    fs_data.all_remove()
    shutil.rmtree(os.path.join(BASE_DIR, "static", "upload"))
    os.mkdir(os.path.join(BASE_DIR, "static", "upload"))
    return RedirectResponse("/remove-succes", status_code=302)
