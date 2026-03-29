import asyncio
import os
import re
import secrets
import sys
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, MagicMock, patch

# プロジェクトルートをsys.pathに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# databaseモジュールを強制的にモック化する
# これにより、aiomysqlなどのドライバがなくてもapp.pyをインポート可能にする
mock_database = MagicMock()
mock_database.db_session = MagicMock()
# await db_session.remove() に対応するための非同期モック
mock_database.db_session.remove = AsyncMock()
mock_database.engine = AsyncMock()

# redisモジュールもモック化
mock_redis = MagicMock()
mock_redis_asyncio = MagicMock()
sys.modules["redis"] = mock_redis
sys.modules["redis.asyncio"] = mock_redis_asyncio

# starsessionsモジュールもモック化
mock_starsessions = MagicMock()
sys.modules["starsessions"] = mock_starsessions


# SessionMiddleware が ASGI アプリとして正しく振る舞うようにする
class MockSessionMiddleware:
    _cookie_name = "test_session_id"
    _sessions = {}

    def __init__(self, app, **kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        cookie_header = ""
        for key, value in scope.get("headers", []):
            if key == b"cookie":
                cookie_header = value.decode("latin-1")
                break

        cookies = SimpleCookie()
        if cookie_header:
            cookies.load(cookie_header)

        session_id = (
            cookies[MockSessionMiddleware._cookie_name].value
            if MockSessionMiddleware._cookie_name in cookies
            else None
        )
        if not session_id or session_id not in MockSessionMiddleware._sessions:
            session_id = secrets.token_hex(16)
            MockSessionMiddleware._sessions[session_id] = {}

        scope["session"] = MockSessionMiddleware._sessions[session_id]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (
                        b"set-cookie",
                        (
                            f"{MockSessionMiddleware._cookie_name}="
                            f"{session_id}; Path=/; HttpOnly"
                        ).encode("latin-1"),
                    )
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
        MockSessionMiddleware._sessions[session_id] = scope.get("session", {})


mock_starsessions.SessionMiddleware = MockSessionMiddleware


class MockSessionAutoloadMiddleware:
    def __init__(self, app, **kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


mock_starsessions.SessionAutoloadMiddleware = MockSessionAutoloadMiddleware

mock_starsessions_stores = MagicMock()
sys.modules["starsessions.stores"] = mock_starsessions_stores
mock_starsessions_stores_redis = MagicMock()
sys.modules["starsessions.stores.redis"] = mock_starsessions_stores_redis

# diff_match_patchモジュールもモック化
mock_dmp = MagicMock()
sys.modules["diff_match_patch"] = mock_dmp

# 実際にモジュールとして登録
sys.modules["database"] = mock_database

# これ以降のインポートでは、databaseモジュールは上記のモックが使われる
import pytest  # noqa: E402
import httpx  # noqa: E402


class SimpleASGITestClient:
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    CSRF_TOKEN_PATH_CANDIDATES = ("/fs-qr", "/group", "/note", "/admin/")

    def __init__(self, app):
        self.app = app
        self.cookies = httpx.Cookies()
        self.csrf_token = None

    async def _raw_request(self, method: str, path: str, **kwargs):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=self.cookies,
            follow_redirects=False,
        ) as client:
            response = await client.request(method, path, **kwargs)
            self.cookies.update(client.cookies)
            return response

    @staticmethod
    def _extract_csrf_token_from_html(html: str):
        if not html:
            return None
        patterns = [
            r"<meta\s+name=['\"]csrf-token['\"]\s+content=['\"]([^'\"]+)['\"]",
            r"name=['\"]csrf_token['\"]\s+value=['\"]([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None

    async def _ensure_csrf_token(self) -> str:
        if self.csrf_token:
            return self.csrf_token
        for path in self.CSRF_TOKEN_PATH_CANDIDATES:
            response = await self._raw_request("GET", path)
            token = self._extract_csrf_token_from_html(response.text)
            if token:
                self.csrf_token = token
                return token
        raise RuntimeError("Failed to extract CSRF token from candidate page responses")

    async def _request(self, method: str, path: str, **kwargs):
        method_upper = method.upper()
        headers = dict(kwargs.pop("headers", {}) or {})
        auto_csrf_added = False

        has_csrf_header = any(key.lower() == "x-csrf-token" for key in headers)
        if method_upper not in self.SAFE_METHODS and not has_csrf_header:
            headers["X-CSRF-Token"] = await self._ensure_csrf_token()
            auto_csrf_added = True

        if headers:
            kwargs["headers"] = headers

        response = await self._raw_request(method, path, **kwargs)
        if auto_csrf_added and response.status_code == 403:
            self.csrf_token = None
            headers["X-CSRF-Token"] = await self._ensure_csrf_token()
            kwargs["headers"] = headers
            response = await self._raw_request(method, path, **kwargs)
        return response

    def request(self, method: str, path: str, **kwargs):
        return asyncio.run(self._request(method, path, **kwargs))

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture(scope="module")
def test_client():
    # さらに細かい部分のモックが必要な場合はここでpatchする
    # Note.note_dataなどがDBにアクセスするのを防ぐ

    with (
        patch("migration_runner.run_migrations", new_callable=AsyncMock),
        patch("Note.note_realtime.startup", new_callable=AsyncMock),
        patch("Note.note_realtime.shutdown", new_callable=AsyncMock),
        patch("Note.note_data.get_room_meta_direct", new_callable=AsyncMock),
        patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock),
        patch("Group.group_data.get_data_direct", new_callable=AsyncMock),
    ):
        # appのインポートはモック設定後に行う
        from app import app

        asyncio.run(app.router.startup())
        try:
            yield SimpleASGITestClient(app)
        finally:
            asyncio.run(app.router.shutdown())
