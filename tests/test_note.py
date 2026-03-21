from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_note_menu(test_client: TestClient):
    response = test_client.get("/note_menu")
    assert response.status_code == 200


def test_create_note_room_page(test_client: TestClient):
    response = test_client.get("/create_note_room")
    assert response.status_code == 200


def test_note_access_page(test_client: TestClient):
    response = test_client.get("/note")
    assert response.status_code == 200


def test_search_note_page(test_client: TestClient):
    response = test_client.get("/search_note")
    assert response.status_code == 200


# --- create_note_room バリデーション (manual モード) ---


def test_create_note_room_empty_id_manual(test_client: TestClient):
    """manual モードで ID が空の場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "", "idMode": "manual"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_create_note_room_invalid_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "abc!@#", "idMode": "manual"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_create_note_room_wrong_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "abcde", "idMode": "manual"},  # 5文字
    )
    assert response.status_code == 400
    assert "error" in response.json()


# --- search_note_process バリデーション ---


def test_search_note_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字があると /search_note にリダイレクトする"""
    response = test_client.post(
        "/search_note_process",
        data={"id": "bad!!", "password": "123456"},
    )
    # バリデーションエラー時は /search_note へリダイレクト (302)
    assert response.status_code == 302
    assert "/search_note" in response.headers["location"]


def test_search_note_invalid_password_chars(test_client: TestClient):
    """パスワードに英字が含まれると /search_note にリダイレクトする"""
    response = test_client.post(
        "/search_note_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 302
    assert "/search_note" in response.headers["location"]


# --- note_room: ルームが見つからない → 404 ---


def test_note_room_not_found(test_client: TestClient):
    """認証情報が一致しないルームアクセスは 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = test_client.get("/note/abc123/000000")
    assert response.status_code == 404


def test_note_direct_not_found(test_client: TestClient):
    """note_direct_access で認証失敗の場合は 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = test_client.get("/note_direct/abc123/000000")
    assert response.status_code == 404


# --- create_note_room: auto モードで渡した ID が重複 → 409 ---


def test_create_note_room_auto_duplicate(test_client: TestClient):
    """auto モードで渡した ID が既存ルームと重複する場合は 409 を返す"""
    with patch(
        "Note.note_app._room_id_exists",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = test_client.post(
            "/create_note_room",
            json={"id": "abc123", "idMode": "auto"},
        )
    assert response.status_code == 409
    assert "retry_auto" in response.json()
