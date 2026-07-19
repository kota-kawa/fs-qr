"""「現在の閲覧者数」機能のテスト。

テスト環境では Redis がモック化されているため、presence モジュールは
プロセス内メモリのフォールバックストアを使って動作する。
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import presence


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- presence モジュール単体 -------------------------------------------------


def test_heartbeat_counts_distinct_viewers():
    scope, key = "group", "room-distinct"
    assert _run(presence.heartbeat(scope, key, "viewer-a")) == 1
    # 同じ viewer のハートビートは重複カウントしない
    assert _run(presence.heartbeat(scope, key, "viewer-a")) == 1
    assert _run(presence.heartbeat(scope, key, "viewer-b")) == 2


def test_leave_decrements_count():
    scope, key = "note", "room-leave"
    _run(presence.heartbeat(scope, key, "viewer-a"))
    _run(presence.heartbeat(scope, key, "viewer-b"))
    assert _run(presence.leave(scope, key, "viewer-a")) == 1
    assert _run(presence.count(scope, key)) == 1


def test_stale_viewers_are_pruned(monkeypatch):
    scope, key = "fsqr-share", "token-stale"
    base = 1_000_000.0
    monkeypatch.setattr(presence.time, "time", lambda: base)
    assert _run(presence.heartbeat(scope, key, "viewer-old")) == 1
    # ウィンドウを超えて時間が経過すると、古い閲覧者は除外される
    monkeypatch.setattr(
        presence.time, "time", lambda: base + presence.PRESENCE_WINDOW_SECONDS + 5
    )
    assert _run(presence.count(scope, key)) == 0


def test_stale_viewers_expire_at_window_boundary(monkeypatch):
    scope, key = "fsqr-share", "token-boundary"
    base = 1_000_000.0
    monkeypatch.setattr(presence.time, "time", lambda: base)
    assert _run(presence.heartbeat(scope, key, "viewer-old")) == 1
    monkeypatch.setattr(
        presence.time, "time", lambda: base + presence.PRESENCE_WINDOW_SECONDS
    )
    assert _run(presence.count(scope, key)) == 0


def test_presence_window_matches_realtime_requirement():
    assert presence.PRESENCE_WINDOW_SECONDS <= 10


def test_validators():
    assert presence.is_valid_scope("group")
    assert not presence.is_valid_scope("unknown-scope")
    assert presence.is_valid_key("abc-123_XYZ")
    assert not presence.is_valid_key("bad/key")
    assert not presence.is_valid_key("")
    assert presence.is_valid_viewer_id("v-abc123")
    assert not presence.is_valid_viewer_id("v with space")


# --- API エンドポイント ------------------------------------------------------


def test_api_heartbeat_returns_count(test_client):
    response = test_client.post("/api/presence/group/api-room?viewer_id=v-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["count"] == 1


def test_api_count_is_public(test_client):
    test_client.post("/api/presence/note/api-count?viewer_id=v-1")
    test_client.post("/api/presence/note/api-count?viewer_id=v-2")
    response = test_client.get("/api/presence/note/api-count")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 2


def test_api_leave_decrements(test_client):
    test_client.post("/api/presence/group/api-leave?viewer_id=v-1")
    test_client.post("/api/presence/group/api-leave?viewer_id=v-2")
    response = test_client.post("/api/presence/group/api-leave/leave?viewer_id=v-1")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 1


def test_api_rejects_unknown_scope(test_client):
    response = test_client.post("/api/presence/unknown/room?viewer_id=v-1")
    assert response.status_code == 404


def test_api_rejects_invalid_key(test_client):
    response = test_client.post("/api/presence/group/bad%20key?viewer_id=v-1")
    assert response.status_code == 404


def test_api_heartbeat_requires_viewer_id(test_client):
    response = test_client.post("/api/presence/group/api-room")
    assert response.status_code == 400


# --- ページにバッジが描画されること -----------------------------------------


def test_upload_complete_renders_presence_widget(test_client):
    mock_data = [
        {
            "id": "abc123",
            "password": "654321",
            "retention_hours": 24,
            "time": datetime(2099, 1, 1, 0, 0),
        }
    ]
    with patch(
        "FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=mock_data
    ):
        response = test_client.get("/upload_complete/abc123-uid-file")
    assert response.status_code == 200
    assert 'data-presence-scope="fsqr-upload"' in response.text
    assert 'data-presence-key="abc123-uid-file"' in response.text
