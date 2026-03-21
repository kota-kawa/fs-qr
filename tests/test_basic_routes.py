from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_index(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_about(test_client: TestClient):
    response = test_client.get("/about")
    assert response.status_code == 200


def test_usage(test_client: TestClient):
    response = test_client.get("/usage")
    assert response.status_code == 200


def test_contact(test_client: TestClient):
    response = test_client.get("/contact")
    assert response.status_code == 200


def test_privacy_policy(test_client: TestClient):
    response = test_client.get("/privacy-policy")
    assert response.status_code == 200


def test_site_operator(test_client: TestClient):
    response = test_client.get("/site-operator")
    assert response.status_code == 200


def test_404(test_client: TestClient):
    response = test_client.get("/non-existent-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


def test_template_render_failure_returns_fallback_html(test_client: TestClient):
    with patch("web.templates.TemplateResponse", side_effect=RuntimeError("boom")):
        response = test_client.get("/about")

    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]
    assert "一時的なエラーが発生しました" in response.text
    assert "Internal Server Error" not in response.text


def test_pages_render_when_session_raises(test_client: TestClient):
    """csrf_token() がセッション障害でも空文字を返しページが正常に描画される"""

    class BrokenSession(dict):
        def get(self, key, default=None):
            raise RuntimeError("Redis connection refused")

        def __setitem__(self, key, value):
            raise RuntimeError("Redis connection refused")

    original_call = test_client.app.__class__.__call__

    async def patched_call(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            scope["session"] = BrokenSession()
        return await original_call(self, scope, receive, send)

    with patch.object(type(test_client.app), "__call__", patched_call):
        # Note pages (extend note_layout.html which uses csrf_token())
        response = test_client.get("/create_note_room")
        assert response.status_code == 200

        response = test_client.get("/search_note")
        assert response.status_code == 200

        response = test_client.get("/group")
        assert response.status_code == 200

        # Home page (extends layout.html which uses csrf_token())
        response = test_client.get("/")
        assert response.status_code == 200


def test_session_autoload_middleware_is_registered(test_client: TestClient):
    middleware_names = [
        middleware.cls.__name__ for middleware in test_client.app.user_middleware
    ]
    assert "MockSessionAutoloadMiddleware" in middleware_names


def test_manage_rooms_returns_error_when_session_raises(test_client: TestClient):
    class BrokenSession(dict):
        def get(self, key, default=None):
            raise RuntimeError("Redis connection refused")

        def __setitem__(self, key, value):
            raise RuntimeError("Redis connection refused")

        def pop(self, key, default=None):
            raise RuntimeError("Redis connection refused")

    original_call = test_client.app.__class__.__call__

    async def patched_call(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            scope["session"] = BrokenSession()
        return await original_call(self, scope, receive, send)

    with patch.object(type(test_client.app), "__call__", patched_call):
        response = test_client.get("/manage_rooms")

    assert response.status_code == 503
    assert "セッションにアクセスできません" in response.text


def test_unexpected_exception_returns_json_error_response(test_client: TestClient):
    with patch(
        "FSQR.fsqr_app.fs_data.get_data",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        response = test_client.get(
            "/download/test-secure-id", headers={"accept": "application/json"}
        )

    assert response.status_code == 500
    assert "application/json" in response.headers["content-type"]
    assert response.json() == {
        "detail": "一時的なエラーが発生しました。時間をおいて再度お試しください。"
    }
