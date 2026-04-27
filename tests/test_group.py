import re
from unittest.mock import AsyncMock, mock_open, patch

from starlette.testclient import TestClient


def test_group_menu(test_client: TestClient):
    response = test_client.get("/group_menu")
    assert response.status_code == 200


def test_group_access_page(test_client: TestClient):
    response = test_client.get("/group")
    assert response.status_code == 200


def test_create_room_page(test_client: TestClient):
    response = test_client.get("/create_room")
    assert response.status_code == 200


def test_search_group_page(test_client: TestClient):
    response = test_client.get("/search_group")
    assert response.status_code == 200


# --- create_group_room バリデーション ---


def test_create_group_room_empty_id(test_client: TestClient):
    """ID が空の場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_group_room",
        json={"id": "", "idMode": "manual"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_create_group_room_invalid_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_group_room",
        json={"id": "abc!@#", "idMode": "manual"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_create_group_room_wrong_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_group_room",
        json={"id": "abcde", "idMode": "manual"},  # 5文字
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_create_group_room_fetch_returns_redirect_url(test_client: TestClient):
    """fetch からの作成は画面遷移先を JSON で返す"""
    create_mock = AsyncMock()
    with (
        patch(
            "Group.group_routes_room.secrets.token_urlsafe", return_value="Strong_pw1"
        ),
        patch(
            "Group.group_routes_room.group_data.get_data",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("Group.group_routes_room.group_data.create_room", create_mock),
        patch("Group.group_routes_room.os.makedirs"),
    ):
        response = test_client.post(
            "/create_group_room",
            data={"id": "abc123", "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/group/abc123/Strong_pw1"
    create_mock.assert_awaited_once_with(
        id="abc123",
        password="Strong_pw1",
        room_id="abc123",
        retention_days=7,
    )


# --- search_group_process バリデーション ---


def test_search_group_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字があると 400 JSON エラーを返す"""
    response = test_client.post(
        "/search_group_process",
        data={"id": "bad!!", "password": "123456"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_search_group_invalid_password_chars(test_client: TestClient):
    """短すぎるパスワードは 400 JSON エラーを返す"""
    response = test_client.post(
        "/search_group_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- group ファイル操作: 不正パス ---


def test_download_file_dotdot_filename(test_client: TestClient):
    """ ".." を含むファイル名の download は 400 を返す"""
    # "..malicious.txt" は URL 正規化の対象にならず、アプリ層でブロックされる
    response = test_client.get("/download/roomid/000000/..malicious.txt")
    assert response.status_code == 400


def test_delete_file_dotdot_filename(test_client: TestClient):
    """ ".." を含むファイル名の delete は 400 を返す"""
    response = test_client.delete("/delete/roomid/000000/..malicious.txt")
    assert response.status_code == 400


# --- group_room: 認証失敗かつ Note ルームでもない → 404 ---


def test_group_room_not_found(test_client: TestClient):
    """認証情報が一致せず Note ルームでもない場合は 404 を返す"""
    with patch(
        "Note.note_data.get_room_meta_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/group/abc123/000000")
    assert response.status_code == 404


def test_group_room_uses_modular_scripts_without_legacy_inline_logic(
    test_client: TestClient,
):
    """group_room は分割済み JS を読み込み、旧インライン実装を含まない"""
    mock_room = {"id": "tester", "retention_days": 7, "time": None}
    with (
        patch(
            "Group.group_routes_room.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_room.get_room_if_valid",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch(
            "Group.group_routes_room.register_success",
            new_callable=AsyncMock,
        ),
        patch("Group.group_routes_room.remember_group_room_access"),
    ):
        response = test_client.get("/group/abc123/000000")

    assert response.status_code == 200
    html = response.text

    expected_script_paths = [
        "/static/js/group_room/core.js",
        "/static/js/group_room/downloads.js",
        "/static/js/group_room/remote-files.js",
        "/static/js/group_room/upload-queue.js",
        "/static/js/group_room/upload-submit.js",
        "/static/js/group_room/main.js",
    ]

    script_positions = []
    for script_path in expected_script_paths:
        script_tag_pattern = rf'<script src="{re.escape(script_path)}\?v=\d+"></script>'
        script_tag_match = re.search(script_tag_pattern, html)
        assert script_tag_match is not None
        script_positions.append(script_tag_match.start())

    assert script_positions == sorted(script_positions)
    assert "window.__FSQR_APP__.api.setConfig('groupRoom', Object.freeze({" in html
    assert "maxFiles" in html
    assert "maxTotalSizeBytes" in html
    assert "fileListRequestTimeoutMs" in html
    assert "function handleFiles(files)" not in html
    assert "function fetchAndDisplayOtherFiles()" not in html


# --- group_upload: 認証失敗 → 400 ---


def test_group_upload_invalid_auth(test_client: TestClient):
    """認証情報が一致しない場合はファイルアップロードを拒否する (400)"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.post(
            "/group_upload/abc123/000000",
            files={"upfile": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_no_files(test_client: TestClient):
    """認証は通るがファイルが送られない場合は 400 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=mock_room,
    ):
        response = test_client.post("/group_upload/abc123/000000")
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_rejects_html_or_svg_content(test_client: TestClient):
    """HTML/SVG 判定されたファイルは 400 で拒否する"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    detector = type("Detector", (), {"from_buffer": lambda self, _: "text/html"})()
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("file_validation._MIME_DETECTOR", detector),
        patch("Group.group_routes_file.os.makedirs"),
    ):
        response = test_client.post(
            "/group_upload/abc123/000000",
            files={"upfile": ("safe.txt", b"<html>bad</html>", "text/plain")},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "HTML/SVG ファイルはアップロードできません。"
    assert payload["data"]["files"] == ["safe.txt"]


# --- check (list_files): 認証失敗 → 404 ---


def test_list_files_invalid_auth(test_client: TestClient):
    """認証情報が一致しない場合はファイル一覧取得を拒否する (404)"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/check/abc123/000000")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- download/all: 認証失敗 → 404 ---


def test_download_all_invalid_auth(test_client: TestClient):
    """認証情報が一致しない場合は全ファイルダウンロードを拒否する (404)"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/download/all/abc123/000000")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- create_group_room: auto モードで重複 ID → 409 ---


def test_create_group_room_auto_duplicate(test_client: TestClient):
    """auto モードで渡した ID が既存ルームと重複する場合は 409 を返す"""
    with patch(
        "Group.group_data.get_data",
        new_callable=AsyncMock,
        return_value=[{"room_id": "abc123"}],
    ):
        response = test_client.post(
            "/create_group_room",
            json={"id": "abc123", "idMode": "auto"},
        )
    assert response.status_code == 409
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["data"]["retry_auto"] is True


def test_create_group_room_generates_urlsafe_password(test_client: TestClient):
    create_mock = AsyncMock()
    with (
        patch(
            "Group.group_routes_room.secrets.token_urlsafe", return_value="Strong_pw1"
        ),
        patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None),
        patch("Group.group_data.create_room", create_mock),
        patch("Group.group_routes_room.os.makedirs"),
    ):
        response = test_client.post(
            "/create_group_room",
            json={"id": "abc123", "idMode": "manual"},
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/group/abc123/Strong_pw1"
    create_mock.assert_awaited_once()
    assert create_mock.await_args.kwargs["password"] == "Strong_pw1"


def test_delete_all_rooms_requires_management_auth(test_client: TestClient):
    with patch("Group.group_data.all_remove", new_callable=AsyncMock) as remove_mock:
        response = test_client.post("/delete_all_rooms")

    assert response.status_code == 302
    assert response.headers["location"] == "/manage_rooms"
    remove_mock.assert_not_awaited()


def test_delete_room_requires_management_auth(test_client: TestClient):
    with patch("Group.group_data.remove_data", new_callable=AsyncMock) as remove_mock:
        response = test_client.post("/delete_room/abc123")

    assert response.status_code == 302
    assert response.headers["location"] == "/manage_rooms"
    remove_mock.assert_not_awaited()


# --- ファイル操作: 認証成功後のフロー ---


def test_list_files_auth_success_no_dir(test_client: TestClient):
    """認証成功でもルームディレクトリが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.os.path.exists", return_value=False),
    ):
        response = test_client.get("/check/abc123/000000")
    # 認証通過 → ディレクトリなし → 404
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_download_file_not_found_after_auth(test_client: TestClient):
    """認証成功でもファイルが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=mock_room,
    ):
        response = test_client.get("/download/abc123/000000/notexist.txt")
    assert response.status_code == 404


def test_delete_file_not_found_after_auth(test_client: TestClient):
    """認証成功でもファイルが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    with (
        patch(
            "Group.group_routes_file.has_group_room_access",
            return_value=True,
        ),
        patch(
            "Group.group_routes_file.check_exponential_backoff",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_file.clear_exponential_backoff",
            new_callable=AsyncMock,
        ),
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
    ):
        response = test_client.delete("/delete/abc123/000000/notexist.txt")
    assert response.status_code == 404


def test_delete_file_requires_room_session(test_client: TestClient):
    """ルームセッションがない場合は削除を拒否する"""
    with (
        patch(
            "Group.group_routes_file.check_exponential_backoff",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_file.register_exponential_backoff_failure",
            new_callable=AsyncMock,
            return_value=(None, "2秒"),
        ) as backoff_mock,
        patch("Group.group_routes_file.os.remove") as remove_mock,
    ):
        response = test_client.delete("/delete/abc123/000000/test.txt")

    assert response.status_code == 403
    assert backoff_mock.await_count >= 1
    remove_mock.assert_not_called()


def test_delete_file_backoff_returns_429(test_client: TestClient):
    """削除失敗のバックオフ中は 429 を返す"""
    with (
        patch(
            "Group.group_routes_file.check_exponential_backoff",
            new_callable=AsyncMock,
            return_value=(False, None, "2秒"),
        ),
        patch("Group.group_routes_file.os.remove") as remove_mock,
    ):
        response = test_client.delete("/delete/abc123/000000/test.txt")

    assert response.status_code == 429
    remove_mock.assert_not_called()


def test_download_all_auth_success_no_dir(test_client: TestClient):
    """認証成功でもルームディレクトリが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.os.path.exists", return_value=False),
    ):
        response = test_client.get("/download/all/abc123/000000")
    assert response.status_code == 404


def test_group_upload_too_many_files(test_client: TestClient):
    """ファイル数が 10 を超えると 400 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    files = [("upfile", (f"file{i}.txt", b"x", "text/plain")) for i in range(11)]
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=mock_room,
    ):
        response = test_client.post(
            "/group_upload/abc123/000000",
            files=files,
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_download_file_empty_filename_returns_400(test_client: TestClient):
    """空のファイル名は 400 を返す"""
    response = test_client.get("/download/abc123/000000/ ")
    assert response.status_code == 400


def test_group_upload_notifies_realtime_when_saved_files_exist(test_client: TestClient):
    """保存済みファイルがある場合は realtime 通知を送る"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    notify_mock = AsyncMock()
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.notify_group_files_updated", notify_mock),
        patch("Group.group_routes_file.os.makedirs"),
        patch("Group.group_routes_file.open", mock_open(), create=True),
        patch("Group.group_routes_file.shutil.copyfileobj"),
        patch("Group.group_routes_file.os.path.getsize", return_value=1),
    ):
        response = test_client.post(
            "/group_upload/abc123/000000",
            files={"upfile": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 200
    notify_mock.assert_awaited_once_with("abc123")


def test_group_delete_notifies_realtime_on_success(test_client: TestClient):
    """ファイル削除成功時は realtime 通知を送る"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_days": 7}]
    notify_mock = AsyncMock()
    with (
        patch(
            "Group.group_routes_file.has_group_room_access",
            return_value=True,
        ),
        patch(
            "Group.group_routes_file.check_exponential_backoff",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_file.clear_exponential_backoff",
            new_callable=AsyncMock,
        ),
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.notify_group_files_updated", notify_mock),
        patch("Group.group_routes_file.os.path.exists", return_value=True),
        patch("Group.group_routes_file.os.remove"),
    ):
        response = test_client.delete("/delete/abc123/000000/test.txt")

    assert response.status_code == 200
    notify_mock.assert_awaited_once_with("abc123")
