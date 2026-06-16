"""file_serving.build_file_response / _build_accel_uri の単体テスト。

X-Accel-Redirect オフロードと FileResponse フォールバックの両分岐を検証する。
"""

import importlib
import os

import pytest
from starlette.responses import FileResponse, Response


def _reload_with(monkeypatch, *, enabled, fsqr_root, group_root):
    """settings を差し替えて file_serving を読み込み直す。"""
    import settings

    monkeypatch.setattr(settings, "X_ACCEL_REDIRECT_ENABLED", enabled, raising=False)
    monkeypatch.setattr(
        settings,
        "X_ACCEL_LOCATIONS",
        {
            "fsqr": ("/_protected/fsqr", fsqr_root),
            "group": ("/_protected/group", group_root),
        },
        raising=False,
    )
    import file_serving

    return importlib.reload(file_serving)


def test_accel_uri_encodes_and_keeps_subdirs(monkeypatch, tmp_path):
    fs = _reload_with(
        monkeypatch, enabled=True, fsqr_root=str(tmp_path), group_root=str(tmp_path)
    )
    uri = fs._build_accel_uri(
        "/_protected/group", str(tmp_path), str(tmp_path / "room1" / "a b.png")
    )
    assert uri == "/_protected/group/room1/a%20b.png"


def test_accel_uri_rejects_path_outside_root(monkeypatch, tmp_path):
    fs = _reload_with(
        monkeypatch, enabled=True, fsqr_root=str(tmp_path), group_root=str(tmp_path)
    )
    outside = os.path.join(str(tmp_path), "..", "secret.enc")
    assert fs._build_accel_uri("/_protected/fsqr", str(tmp_path), outside) is None


def test_build_file_response_uses_x_accel_when_enabled(monkeypatch, tmp_path):
    fs = _reload_with(
        monkeypatch, enabled=True, fsqr_root=str(tmp_path), group_root=str(tmp_path)
    )
    target = tmp_path / "file.enc"
    target.write_bytes(b"data")
    resp = fs.build_file_response(
        str(target),
        media_type="application/octet-stream",
        headers={"Content-Length": "4", "X-File-Type": "single"},
        accel_scope="fsqr",
    )
    assert isinstance(resp, Response) and not isinstance(resp, FileResponse)
    assert resp.headers["X-Accel-Redirect"] == "/_protected/fsqr/file.enc"
    # 本体は空（実体は nginx が配信）。アプリが渡した実ファイルサイズ "4" は載せず、
    # nginx が内部リダイレクト先のファイルから Content-Length を再計算する。
    assert resp.body == b""
    assert resp.headers["content-length"] == "0"
    # 認可由来のヘッダは保持される。
    assert resp.headers["X-File-Type"] == "single"


def test_build_file_response_falls_back_to_fileresponse_when_disabled(
    monkeypatch, tmp_path
):
    fs = _reload_with(
        monkeypatch, enabled=False, fsqr_root=str(tmp_path), group_root=str(tmp_path)
    )
    target = tmp_path / "file.zip"
    target.write_bytes(b"zipdata")
    resp = fs.build_file_response(
        str(target), media_type="application/zip", accel_scope="fsqr"
    )
    assert isinstance(resp, FileResponse)
    assert "X-Accel-Redirect" not in resp.headers


def test_build_file_response_falls_back_when_path_outside_scope(monkeypatch, tmp_path):
    inside = tmp_path / "uploads"
    inside.mkdir()
    other = tmp_path / "elsewhere"
    other.mkdir()
    fs = _reload_with(
        monkeypatch, enabled=True, fsqr_root=str(inside), group_root=str(inside)
    )
    target = other / "legacy.bin"
    target.write_bytes(b"x")
    resp = fs.build_file_response(
        str(target), media_type="application/octet-stream", accel_scope="fsqr"
    )
    # スコープ外（例: レガシー保存場所）は FileResponse にフォールバック。
    assert isinstance(resp, FileResponse)


@pytest.fixture(autouse=True)
def _restore_file_serving():
    """テスト後に本番設定で file_serving を読み戻し、他テストへの影響を防ぐ。"""
    yield
    import file_serving

    importlib.reload(file_serving)
