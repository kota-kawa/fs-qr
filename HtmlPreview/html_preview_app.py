from fastapi import APIRouter, Request

from web import render_template

router = APIRouter()

CDN_ASSETS = {
    "styles": [
        {
            "name": "Bootstrap 5.3.8",
            "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css",
            "integrity": (
                "sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB"
            ),
        },
        {
            "name": "Font Awesome 7.3.0",
            "url": (
                "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@7.3.0/"
                "css/all.min.css"
            ),
            "integrity": (
                "sha384-sTlsophtwz/I4myskS3OIJf5VvEojkXKZyBTWZm0YD/K1pN7C5wpBPLyrsbr1SU2"
            ),
        },
    ],
    "fonts": (
        "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@7.3.0/webfonts/"
    ),
    "mermaid": {
        "name": "Mermaid 12.2.0",
        "url": "https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js",
        "integrity": (
            "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp"
        ),
    },
}


@router.get("/html-preview", name="html_preview")
async def html_preview(request: Request):
    response = render_template(request, "html-preview.html", cdn_assets=CDN_ASSETS)
    nonce = request.state.csp_nonce
    styles = " ".join(asset["url"] for asset in CDN_ASSETS["styles"])
    # Allow fixed CDN resources, without accepting pasted scripts or uploads.
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'self' 'nonce-{nonce}' "
        f"{CDN_ASSETS['mermaid']['url']}; "
        "style-src 'self' 'unsafe-inline'; "
        f"font-src {CDN_ASSETS['fonts']}; img-src 'self' data:; "
        "frame-src 'self'; base-uri 'none'; form-action 'none'; "
        f"frame-ancestors 'self'; connect-src {styles}; object-src 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response
