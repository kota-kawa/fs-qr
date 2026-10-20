from fastapi import APIRouter, Request

from html_preview_assets import CDN_ASSETS, build_preview_content_security_policy
from web import render_template

router = APIRouter()


@router.get("/html-preview", name="html_preview")
async def html_preview(request: Request):
    response = render_template(request, "html-preview.html", cdn_assets=CDN_ASSETS)
    response.headers["Content-Security-Policy"] = build_preview_content_security_policy(
        request.state.csp_nonce
    )
    response.headers["Cache-Control"] = "no-store"
    return response
