import asyncio
import re
from unittest.mock import AsyncMock, mock_open, patch

from starlette.testclient import TestClient

from Group import group_data
from share_links import encrypt_share_password


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
        patch("Group.group_routes_room.generate_room_password", return_value="000042"),
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
            data={"id": "abc123", "idMode": "manual", "retention_hours": 24},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/group/r/abc123"
    assert payload["data"]["share_url"].startswith("http://testserver/group/s/")
    assert payload["data"]["password"] == "000042"
    create_mock.assert_awaited_once_with(
        id="abc123",
        password="000042",
        room_id="abc123",
        retention_hours=24,
    )


def test_create_group_room_auto_empty_id_is_generated_server_side(
    test_client: TestClient,
):
    """auto ID が空でもサーバー側でIDを生成して作成できる"""
    create_mock = AsyncMock()
    with (
        patch("Group.group_routes_room._generate_room_id", return_value="gen001"),
        patch("Group.group_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Group.group_routes_room.create_share_link",
            new=AsyncMock(return_value="group-share-token"),
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
            json={"id": "", "idMode": "auto", "retention_hours": 24},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/group/r/gen001"
    create_mock.assert_awaited_once_with(
        id="gen001",
        password="000042",
        room_id="gen001",
        retention_hours=24,
    )


def test_create_group_room_succeeds_when_share_link_creation_fails(
    test_client: TestClient,
):
    """共有URL発行が失敗してもルーム作成自体は完了する"""
    create_mock = AsyncMock()
    remove_mock = AsyncMock()
    with (
        patch("Group.group_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Group.group_routes_room.group_data.get_data",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("Group.group_routes_room.group_data.create_room", create_mock),
        patch("Group.group_routes_room.group_data.remove_data", remove_mock),
        patch(
            "Group.group_routes_room.create_share_link",
            new=AsyncMock(side_effect=RuntimeError("share table missing")),
        ),
        patch("Group.group_routes_room.os.makedirs"),
    ):
        response = test_client.post(
            "/create_group_room",
            data={"id": "abc123", "idMode": "manual", "retention_hours": 24},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/group/r/abc123"
    assert payload["data"]["share_url"] == ""
    assert payload["data"]["password"] == "000042"
    create_mock.assert_awaited_once()
    remove_mock.assert_not_awaited()


# --- search_group_process バリデーション ---


def test_search_group_invalid_id_chars(test_client: TestClient):
    response = test_client.post(
        "/search_group_process",
        data={"id": "bad!!", "password": "123456"},
    )
    assert response.status_code == 400
    assert "ID" in response.text


def test_search_group_invalid_id_length(test_client: TestClient):
    response = test_client.post(
        "/search_group_process",
        data={"id": "abc12", "password": "123456"},
    )
    assert response.status_code == 400
    assert "6文字" in response.text


def test_search_group_invalid_password_chars(test_client: TestClient):
    response = test_client.post(
        "/search_group_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 400
    assert "パスワード" in response.text


# --- group ファイル操作: 不正パス ---


def test_download_file_dotdot_filename(test_client: TestClient):
    """ ".." を含むファイル名の download は 400 を返す"""
    # "..malicious.txt" は URL 正規化の対象にならず、アプリ層でブロックされる
    response = test_client.get("/download/roomid/..malicious.txt")
    assert response.status_code == 400


def test_delete_file_dotdot_filename(test_client: TestClient):
    """ ".." を含むファイル名の delete は 400 を返す"""
    response = test_client.delete("/delete/roomid/..malicious.txt")
    assert response.status_code == 400


# --- group_room: 認証失敗かつ Note ルームでもない → 404 ---


def test_group_room_not_found(test_client: TestClient):
    """旧ID/Password URLは停止済みなので 410 を返す"""
    response = test_client.get("/group/abc123/000000")
    assert response.status_code == 410


def test_group_room_uses_modular_scripts_without_legacy_inline_logic(
    test_client: TestClient,
):
    """group_room は分割済み JS を読み込み、旧インライン実装を含まない"""
    mock_room = {"id": "tester", "retention_hours": 24, "time": None}
    with (
        patch(
            "Group.group_routes_room.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_room.has_group_room_access", return_value=True),
        patch(
            "Group.group_routes_room.get_group_room_share_token",
            return_value="group-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ),
        patch(
            "Group.group_routes_room.register_success",
            new_callable=AsyncMock,
        ),
    ):
        response = test_client.get("/group/r/abc123")

    assert response.status_code == 200
    html = response.text

    expected_script_paths = [
        "/static/js/group_room/core.js",
        "/static/js/group_room/preview.js",
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
    assert "groupPreviewOverlay" in html
    assert 'id="groupShareQrCode"' in html
    assert (
        'data-share-url="http://testserver/group/s/group-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"'
        in html
    )
    assert "/static/qrcode.min.js" in html
    assert "api.qrserver.com" not in html
    assert "function handleFiles(files)" not in html
    assert "function fetchAndDisplayOtherFiles()" not in html


def test_group_share_entry_renders_room_without_redirect(test_client: TestClient):
    """QRの共有URLはスマホのブラウザ移動で壊れないよう直接ルームを表示する"""
    mock_room = {"id": "tester", "retention_hours": 24, "time": None}
    share_token = "group-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    with (
        patch(
            "Group.group_routes_room.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_room.resolve_share_link",
            new_callable=AsyncMock,
            return_value={
                "service_key": "group",
                "resource_id": "grp999",
                "metadata": {
                    "id": "grp999",
                    "password_enc": encrypt_share_password("024680"),
                },
            },
        ),
        patch(
            "Group.group_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_room.register_success", new_callable=AsyncMock),
    ):
        response = test_client.get(f"/group/s/{share_token}")

    assert response.status_code == 200
    assert "location" not in response.headers
    html = response.text
    assert "グループファイル共有" in html
    assert f'data-share-url="http://testserver/group/s/{share_token}"' in html
    # 共有URLで入った受信者にもパスワードが表示される
    assert "024680" in html


# --- group_upload: 認証失敗 → 400 ---


def test_group_upload_invalid_auth(test_client: TestClient):
    """セッションがない場合はファイルアップロードを拒否する"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_no_files(test_client: TestClient):
    """認証は通るがファイルが送られない場合は 400 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post("/group_upload/abc123")
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_rejects_html_or_svg_content(test_client: TestClient):
    """HTML/SVG 判定されたファイルは 400 で拒否する"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    detector = type("Detector", (), {"from_buffer": lambda self, _: "text/html"})()
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("file_validation._MIME_DETECTOR", detector),
        patch("Group.group_routes_file.os.makedirs"),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("safe.txt", b"<html>bad</html>", "text/plain")},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "HTML/SVGファイルはアップロードできません。"
    assert payload["data"]["files"] == ["safe.txt"]


def test_group_upload_succeeds_when_realtime_notification_fails(
    test_client: TestClient, tmp_path
):
    """保存後の通知失敗はアップロード成功レスポンスを壊さない"""
    with (
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch(
            "Group.group_routes_file.get_room_if_active",
            new_callable=AsyncMock,
            return_value={"id": "abc123"},
        ),
        patch(
            "Group.group_routes_file.validate_upload_file_content", return_value=None
        ),
        patch(
            "Group.group_routes_file.notify_group_files_updated",
            new=AsyncMock(side_effect=RuntimeError("ws down")),
        ),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("notes.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["saved_files"] == ["notes.txt"]
    assert (tmp_path / "abc123" / "notes.txt").read_bytes() == b"hello"


# --- check (list_files): 認証失敗 → 404 ---


def test_list_files_invalid_auth(test_client: TestClient):
    """セッションがない場合はファイル一覧取得を拒否する"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/check/abc123")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- download/all: 認証失敗 → 404 ---


def test_download_all_invalid_auth(test_client: TestClient):
    """セッションがない場合は全ファイルダウンロードを拒否する"""
    with patch(
        "Group.group_data.get_data_direct",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/download/all/abc123")
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


def test_create_group_room_generates_numeric_password(test_client: TestClient):
    create_mock = AsyncMock()
    with (
        patch("Group.group_routes_room.generate_room_password", return_value="000042"),
        patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None),
        patch("Group.group_data.create_room", create_mock),
        patch("Group.group_routes_room.os.makedirs"),
    ):
        response = test_client.post(
            "/create_group_room",
            json={"id": "abc123", "idMode": "manual"},
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/group/r/abc123"
    create_mock.assert_awaited_once()
    assert create_mock.await_args.kwargs["password"] == "000042"


def test_group_owner_session_can_delete_room(test_client: TestClient):
    """ルーム作成直後の同一セッションだけGroupルームを削除できる"""
    room_id = "gdel01"
    active_room = {
        "id": room_id,
        "room_id": room_id,
        "retention_hours": 24,
        "time": None,
    }
    remove_mock = AsyncMock(return_value=True)
    with (
        patch("Group.group_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Group.group_routes_room.group_data.get_data",
            new_callable=AsyncMock,
            side_effect=[None, [active_room]],
        ),
        patch("Group.group_routes_room.group_data.create_room", new_callable=AsyncMock),
        patch("Group.group_routes_room.group_data.remove_data", remove_mock),
        patch("Group.group_routes_room.os.makedirs"),
    ):
        create_response = test_client.post(
            "/create_group_room",
            json={"id": room_id, "idMode": "manual"},
        )
        delete_response = test_client.post(f"/group/r/{room_id}/delete")

    assert create_response.status_code == 302
    assert delete_response.status_code == 302
    assert delete_response.headers["location"] == "/remove-succes"
    remove_mock.assert_awaited_once_with(room_id)


def test_group_delete_room_requires_owner_session(test_client: TestClient):
    """作成セッションがないGroupルーム削除は403を返す"""
    room_id = "gfor01"
    active_room = {
        "id": room_id,
        "room_id": room_id,
        "retention_hours": 24,
        "time": None,
    }
    with (
        patch(
            "Group.group_routes_room.group_data.get_data",
            new_callable=AsyncMock,
            return_value=[active_room],
        ),
        patch(
            "Group.group_routes_room.group_data.remove_data", new_callable=AsyncMock
        ) as remove_mock,
    ):
        response = test_client.post(f"/group/r/{room_id}/delete")

    assert response.status_code == 403
    remove_mock.assert_not_awaited()


def test_delete_all_rooms_requires_management_auth(test_client: TestClient):
    with patch("Group.group_data.all_remove", new_callable=AsyncMock) as remove_mock:
        response = test_client.post("/delete_all_rooms")

    assert response.status_code == 302
    assert response.headers["location"] == "/manage_rooms"
    remove_mock.assert_not_awaited()


def test_manage_rooms_login_rate_limited_returns_429(test_client: TestClient):
    with patch(
        "Group.group_routes_manage.check_rate_limit",
        new=AsyncMock(return_value=(False, None, "30分")),
    ):
        response = test_client.post("/manage_rooms", data={"password": "wrongpw"})

    assert response.status_code == 429
    assert "30分" in response.text


def test_manage_rooms_login_wrong_pw_registers_failure(test_client: TestClient):
    with (
        patch("Group.group_routes_manage.management_password", "managepw"),
        patch(
            "Group.group_routes_manage.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch(
            "Group.group_routes_manage.register_failure",
            new=AsyncMock(return_value=(None, None)),
        ) as failure_mock,
    ):
        response = test_client.post("/manage_rooms", data={"password": "wrongpw"})

    assert response.status_code == 200
    failure_mock.assert_awaited_once()
    assert failure_mock.await_args.args[0] == "management"


def test_manage_rooms_login_success_clears_rate_limit(test_client: TestClient):
    with (
        patch("Group.group_routes_manage.management_password", "managepw"),
        patch(
            "Group.group_routes_manage.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch(
            "Group.group_routes_manage.register_success", new=AsyncMock()
        ) as success_mock,
        patch("Group.group_data.get_all_direct", new=AsyncMock(return_value=[])),
    ):
        response = test_client.post("/manage_rooms", data={"password": "managepw"})

    assert response.status_code == 200
    success_mock.assert_awaited_once()
    assert success_mock.await_args.args[0] == "management"
    test_client.get("/logout_management")


def test_delete_room_requires_management_auth(test_client: TestClient):
    with patch("Group.group_data.remove_data", new_callable=AsyncMock) as remove_mock:
        response = test_client.post("/delete_room/abc123")

    assert response.status_code == 302
    assert response.headers["location"] == "/manage_rooms"
    remove_mock.assert_not_awaited()


def test_remove_data_keeps_db_record_when_folder_delete_fails():
    """フォルダ削除に失敗した場合はDBレコードを削除しない"""
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=[{"room_id": "abc123"}],
        ),
        patch(
            "Group.group_data.iter_room_folders",
            return_value=iter([("/uploads", "/uploads/abc123")]),
        ),
        patch("Group.group_data.os.path.exists", return_value=True),
        patch("Group.group_data.shutil.rmtree", side_effect=OSError("denied")),
        patch("Group.group_data.execute_query", new_callable=AsyncMock) as query_mock,
    ):
        result = asyncio.run(group_data.remove_data("abc123"))

    assert result is False
    query_mock.assert_not_awaited()


# --- ファイル操作: 認証成功後のフロー ---


def test_list_files_auth_success_no_dir(test_client: TestClient, tmp_path):
    """認証成功でもルームディレクトリが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    legacy_root = tmp_path / "legacy"
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path / "current")),
        patch("Group.group_storage.LEGACY_UPLOAD_FOLDER", str(legacy_root)),
    ):
        response = test_client.get("/check/nodir1")
    # 認証通過 → ディレクトリなし → 404
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_list_files_includes_preview_metadata(test_client: TestClient, tmp_path):
    """一覧取得はプレビュー可能なファイル種別を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    room_dir = tmp_path / "abc123"
    room_dir.mkdir()
    (room_dir / "sample.png").write_bytes(b"image")
    (room_dir / "archive.zip").write_bytes(b"zip")

    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
    ):
        response = test_client.get("/check/abc123")

    assert response.status_code == 200
    files = {item["name"]: item for item in response.json()["data"]["files"]}
    assert files["sample.png"]["previewable"] is True
    assert files["sample.png"]["preview_type"] == "image"
    assert files["archive.zip"]["previewable"] is False


def test_download_file_not_found_after_auth(test_client: TestClient):
    """認証成功でもファイルが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.get("/download/abc123/notexist.txt")
    assert response.status_code == 404


def test_preview_file_returns_inline_response(test_client: TestClient, tmp_path):
    """プレビュー可能なファイルは inline で返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    room_dir = tmp_path / "abc123"
    room_dir.mkdir()
    (room_dir / "memo.txt").write_text("hello", encoding="utf-8")

    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
    ):
        response = test_client.get("/preview/abc123/memo.txt")

    assert response.status_code == 200
    assert response.text == "hello"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_preview_file_rejects_unsupported_type(test_client: TestClient, tmp_path):
    """対応外の拡張子はプレビューしない"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    room_dir = tmp_path / "abc123"
    room_dir.mkdir()
    (room_dir / "archive.zip").write_bytes(b"zip")

    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
    ):
        response = test_client.get("/preview/abc123/archive.zip")

    assert response.status_code == 415
    assert response.json()["status"] == "error"


def test_delete_file_not_found_after_auth(test_client: TestClient):
    """認証成功でもファイルが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
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
        response = test_client.delete("/delete/abc123/notexist.txt")
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
        patch("Group.group_routes_file.has_group_room_access", return_value=False),
        patch("Group.group_routes_file.os.remove") as remove_mock,
    ):
        response = test_client.delete("/delete/abc123/test.txt")

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
        response = test_client.delete("/delete/abc123/test.txt")

    assert response.status_code == 429
    remove_mock.assert_not_called()


def test_download_all_auth_success_no_dir(test_client: TestClient):
    """認証成功でもルームディレクトリが存在しない場合は 404 を返す"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.os.path.exists", return_value=False),
    ):
        response = test_client.get("/download/all/abc123")
    assert response.status_code == 404


def test_group_upload_too_many_files(test_client: TestClient):
    """ファイル数が上限を超えると 400 を返す"""
    from settings import UPLOAD_MAX_FILES

    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    files = [
        ("upfile", (f"file{i}.txt", b"x", "text/plain"))
        for i in range(UPLOAD_MAX_FILES + 1)
    ]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files=files,
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_rejects_when_room_total_size_exceeded(test_client: TestClient):
    """既存ファイルとの合計サイズが上限を超えると 400 を返す"""
    from settings import UPLOAD_MAX_TOTAL_SIZE_BYTES

    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch(
            "Group.group_routes_file.room_files_usage",
            return_value=(1, UPLOAD_MAX_TOTAL_SIZE_BYTES),
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("extra.txt", b"x", "text/plain")},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_group_upload_rejects_when_room_file_count_exceeded(test_client: TestClient):
    """既存ファイル数との合計が上限を超えると 400 を返す"""
    from settings import UPLOAD_MAX_FILES

    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch(
            "Group.group_routes_file.room_files_usage",
            return_value=(UPLOAD_MAX_FILES, 0),
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("extra.txt", b"x", "text/plain")},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"


def test_download_file_empty_filename_returns_400(test_client: TestClient):
    """空のファイル名は 400 を返す"""
    response = test_client.get("/download/abc123/ ")
    assert response.status_code == 400


def test_group_upload_notifies_realtime_when_saved_files_exist(test_client: TestClient):
    """保存済みファイルがある場合は realtime 通知を送る"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
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
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
    ):
        response = test_client.post(
            "/group_upload/abc123",
            files={"upfile": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 200
    notify_mock.assert_awaited_once_with("abc123")


def test_static_group_uploads_are_not_public(test_client: TestClient):
    response = test_client.get("/static/group_uploads/abc123/test.txt")

    assert response.status_code == 404


def test_list_files_uses_legacy_folder_fallback(test_client: TestClient, tmp_path):
    """旧 static/group_uploads 相当の既存ファイルも認証APIでは参照できる"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    current_root = tmp_path / "current"
    legacy_root = tmp_path / "legacy"
    legacy_room = legacy_root / "abc123"
    legacy_room.mkdir(parents=True)
    (legacy_room / "old.txt").write_text("old", encoding="utf-8")

    with (
        patch(
            "Group.group_data.get_data_direct",
            new_callable=AsyncMock,
            return_value=mock_room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(current_root)),
        patch("Group.group_storage.LEGACY_UPLOAD_FOLDER", str(legacy_root)),
    ):
        response = test_client.get("/check/abc123")

    assert response.status_code == 200
    assert response.json()["data"]["files"][0]["name"] == "old.txt"


def test_group_delete_notifies_realtime_on_success(test_client: TestClient, tmp_path):
    """ファイル削除成功時は realtime 通知を送る"""
    mock_room = [{"password": "000000", "id": "abc123", "retention_hours": 24}]
    notify_mock = AsyncMock()
    room_dir = tmp_path / "abc123"
    room_dir.mkdir()
    target_file = room_dir / "test.txt"
    target_file.write_text("content", encoding="utf-8")
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
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(tmp_path)),
        patch("Group.group_storage.LEGACY_UPLOAD_FOLDER", str(tmp_path / "legacy")),
    ):
        response = test_client.delete("/delete/abc123/test.txt")

    assert response.status_code == 200
    assert not target_file.exists()
    notify_mock.assert_awaited_once_with("abc123")
