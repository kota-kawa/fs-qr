from fastapi import APIRouter, Request

from html_preview_assets import CDN_ASSETS
from web import render_template

router = APIRouter()


@router.get("/html-preview", name="html_preview")
async def html_preview(request: Request):
    response = render_template(request, "html-preview.html", cdn_assets=CDN_ASSETS)
    nonce = request.state.csp_nonce
    styles = " ".join(asset["url"] for asset in CDN_ASSETS["styles"])
    webfonts = " ".join(asset["url"] for asset in CDN_ASSETS["webfonts"])
    # Only the tool fetches fixed assets; pasted code runs in an opaque sandbox.
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'self' 'nonce-{nonce}' "
        f"{CDN_ASSETS['mermaid']['url']}; "
        "style-src 'self' 'unsafe-inline'; "
        f"font-src data: {CDN_ASSETS['fonts']}; img-src 'self' data:; "
        "frame-src 'none'; base-uri 'none'; form-action 'none'; "
        f"frame-ancestors 'self'; connect-src {styles} "
        f"{CDN_ASSETS['mermaid']['url']} {CDN_ASSETS['fonts']} {webfonts}; "
        "object-src 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response
