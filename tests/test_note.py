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
