"""Pinned CDN assets shared by the HTML preview tool and Group's HTML preview."""

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
    "webfonts": [
        {
            "name": "Noto Sans JP",
            "url": (
                "https://cdn.jsdelivr.net/gh/google/fonts@"
                "66a36c8c94b1a5d992ee4e7f392fccfe4945767c/"
                "ofl/notosansjp/NotoSansJP[wght].ttf"
            ),
            "integrity": (
                "sha384-5HQCFe8OxNPojt1uWgu7u/aNR2I8FBn/"
                "xG9CMTBVFvnRN4nNa+hMkx2sPcE/gNzI"
            ),
        },
        {
            "name": "JetBrains Mono",
            "url": (
                "https://cdn.jsdelivr.net/gh/google/fonts@"
                "66a36c8c94b1a5d992ee4e7f392fccfe4945767c/"
                "ofl/jetbrainsmono/JetBrainsMono[wght].ttf"
            ),
            "integrity": (
                "sha384-U1HV2HxEECMos0gfWJu1pa+v0oDb7wEX"
                "mCTRdU0uizFuaCyRFgunAZ0c6Nowh6lU"
            ),
        },
    ],
    "mermaid": {
        "name": "Mermaid 12.2.0",
        "url": "https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js",
        "integrity": (
            "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp"
        ),
    },
}


def build_preview_content_security_policy(nonce: str) -> str:
    """CSP for pages that render untrusted HTML in nested srcdoc frames.

    ``frame-src 'none'`` is inherited by the srcdoc frame, so even opt-in
    scripts cannot navigate the frame to another URL to carry data out.
    """
    styles = " ".join(asset["url"] for asset in CDN_ASSETS["styles"])
    webfonts = " ".join(asset["url"] for asset in CDN_ASSETS["webfonts"])
    # Only the tool fetches fixed assets; pasted code runs in an opaque sandbox.
    return (
        f"default-src 'none'; script-src 'self' 'nonce-{nonce}' "
        f"{CDN_ASSETS['mermaid']['url']}; "
        "style-src 'self' 'unsafe-inline'; "
        f"font-src data: {CDN_ASSETS['fonts']}; img-src 'self' data:; "
        "frame-src 'none'; base-uri 'none'; form-action 'none'; "
        f"frame-ancestors 'self'; connect-src {styles} "
        f"{CDN_ASSETS['mermaid']['url']} {CDN_ASSETS['fonts']} {webfonts}; "
        "object-src 'none'"
    )
