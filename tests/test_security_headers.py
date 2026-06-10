"""セキュリティヘッダーとアクセスログ伏せ字化のテスト。"""

import pytest

from log_config import redact_sensitive_paths
from security_headers import SECURITY_HEADERS

EXPECTED_HEADER_NAMES = (
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Permissions-Policy",
)


def test_index_has_security_headers(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    for name in EXPECTED_HEADER_NAMES:
        assert response.headers.get(name) == SECURITY_HEADERS[name]
    csp = response.headers.get("Content-Security-Policy") or response.headers.get(
        "Content-Security-Policy-Report-Only"
    )
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp


def test_404_response_has_security_headers(test_client):
    response = test_client.get("/no-such-page")
    assert response.status_code == 404
    for name in EXPECTED_HEADER_NAMES:
        assert response.headers.get(name) == SECURITY_HEADERS[name]


def test_static_response_has_security_headers(test_client):
    response = test_client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/fs-qr/room1/secret-pw", "/fs-qr/[redacted]/[redacted]"),
        (
            "/fs-qr/room1/secret-pw/download",
            "/fs-qr/[redacted]/[redacted]/download",
        ),
        ("/fs-qr/s/token123", "/fs-qr/s/[redacted]"),
        ("/fs-qr/s/token123/download", "/fs-qr/s/[redacted]/download"),
        (
            'GET /fs-qr/room1/secret-pw HTTP/1.1" 410',
            'GET /fs-qr/[redacted]/[redacted] HTTP/1.1" 410',
        ),
        # 認証情報を含まないパスはそのまま
        ("/fs-qr", "/fs-qr"),
        ("/fs-qr_menu", "/fs-qr_menu"),
        ("/fs-qr/delete/abc", "/fs-qr/delete/abc"),
        ("/download/abc", "/download/abc"),
    ],
)
def test_redact_sensitive_paths(path, expected):
    assert redact_sensitive_paths(path) == expected
