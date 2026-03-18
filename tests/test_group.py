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
    assert "error" in response.json()


def test_create_group_room_invalid_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_group_room",
        json={"id": "abc!@#", "idMode": "manual"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_create_group_room_wrong_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_group_room",
        json={"id": "abcde", "idMode": "manual"},  # 5文字
    )
    assert response.status_code == 400
    assert "error" in response.json()


# --- search_group_process バリデーション ---

def test_search_group_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字があると 400 JSON エラーを返す"""
    response = test_client.post(
        "/search_group_process",
        data={"id": "bad!!", "password": "123456"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_search_group_invalid_password_chars(test_client: TestClient):
    """パスワードに英字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/search_group_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


# --- group ファイル操作: 不正パス ---

def test_download_file_dotdot_filename(test_client: TestClient):
    """".." を含むファイル名の download は 400 を返す"""
    # "..malicious.txt" は URL 正規化の対象にならず、アプリ層でブロックされる
    response = test_client.get("/download/roomid/000000/..malicious.txt")
    assert response.status_code == 400


def test_delete_file_dotdot_filename(test_client: TestClient):
    """".." を含むファイル名の delete は 400 を返す"""
    response = test_client.delete("/delete/roomid/000000/..malicious.txt")
    assert response.status_code == 400
