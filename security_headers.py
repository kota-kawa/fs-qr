"""全 HTTP レスポンスに付与するセキュリティヘッダー。

nginx の add_header は location 内に 1 つでも add_header があると
server レベルの定義を継承しない（ヘッダーが漏れる location ができる）ため、
アプリ側ミドルウェアで一元的に付与する。
"""

from __future__ import annotations

import os

# CSP のホワイトリストはテンプレート・JS が実際に参照する外部オリジンに基づく:
# - Google AdSense / gtag: pagead2.googlesyndication.com, googletagmanager.com ほか
# - Google Ad Traffic Quality (sodar): *.adtrafficquality.google
#   ep1/ep2/ep3... のように広告視認性・不正トラフィック検知用スクリプトの
#   配信元サブドメインが動的に変わるためワイルドカードで許可する。
# - CDN: cdn.jsdelivr.net (Bootstrap), cdnjs.cloudflare.com (Font Awesome, JSZip)
# - Web フォント: fonts.googleapis.com / fonts.gstatic.com
# テンプレート内インラインスクリプトはリクエストごとの nonce で許可する。
# `unsafe-inline` は使わず、漏洩した HTML 断片がスクリプト実行権限を持たないようにする。
# 広告の画像・iframe・計測先は配信ドメインが流動的なため img/frame は https: で許可。
_CSP_SCRIPT_SOURCES = (
    "'self'",
    "https://pagead2.googlesyndication.com",
    "https://googleads.g.doubleclick.net",
    "https://tpc.googlesyndication.com",
    "https://www.googletagmanager.com",
    "https://*.adtrafficquality.google",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
)


def _build_default_content_security_policy(nonce: str = "") -> str:
    nonce_source = f" 'nonce-{nonce}'" if nonce else ""
    script_sources = " ".join(_CSP_SCRIPT_SOURCES)
    directives = (
        "default-src 'self'",
        f"script-src{nonce_source} {script_sources}",
        "style-src 'self' 'unsafe-inline'"
        " https://fonts.googleapis.com"
        " https://cdn.jsdelivr.net"
        " https://cdnjs.cloudflare.com",
        "font-src 'self' data:"
        " https://fonts.gstatic.com"
        " https://cdn.jsdelivr.net"
        " https://cdnjs.cloudflare.com",
        "img-src 'self' data: blob: https:",
        "frame-src https:",
        "connect-src 'self'"
        " https://pagead2.googlesyndication.com"
        " https://googleads.g.doubleclick.net"
        " https://*.adtrafficquality.google"
        " https://www.google-analytics.com"
        " https://region1.google-analytics.com"
        " https://www.googletagmanager.com"
        " https://cdn.jsdelivr.net"
        " https://cdnjs.cloudflare.com",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
    )
    return "; ".join(directives)


DEFAULT_CONTENT_SECURITY_POLICY = _build_default_content_security_policy()

# SECURITY_CSP でポリシー全体を差し替え可能。
# SECURITY_CSP_REPORT_ONLY=true で Report-Only 配信に切り替え（観察モード）。
CONTENT_SECURITY_POLICY = (
    os.getenv("SECURITY_CSP", "").strip() or DEFAULT_CONTENT_SECURITY_POLICY
)
CSP_REPORT_ONLY = os.getenv("SECURITY_CSP_REPORT_ONLY", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    # Share passwords/tokens can be present in legacy paths or fragments;
    # do not disclose the source URL to another request.
    # 旧URLの認証情報や fragment を参照元として送信しない。
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def apply_security_headers(headers, *, nonce: str = "") -> None:
    """レスポンスヘッダーに不足分のセキュリティヘッダーを追加する。

    既にエンドポイント側で同名ヘッダーを設定している場合は上書きしない。
    """
    for name, value in SECURITY_HEADERS.items():
        if name not in headers:
            headers[name] = value

    csp_header_name = (
        "Content-Security-Policy-Report-Only"
        if CSP_REPORT_ONLY
        else "Content-Security-Policy"
    )
    if (
        "Content-Security-Policy" not in headers
        and "Content-Security-Policy-Report-Only" not in headers
    ):
        # Apply a per-response nonce only to the built-in policy. An explicitly
        # configured SECURITY_CSP remains under the operator's control.
        # 組み込みポリシーだけリクエスト単位 nonce を付与し、明示設定は運用者の値を尊重する。
        headers[csp_header_name] = (
            _build_default_content_security_policy(nonce)
            if nonce and CONTENT_SECURITY_POLICY == DEFAULT_CONTENT_SECURITY_POLICY
            else CONTENT_SECURITY_POLICY
        )
