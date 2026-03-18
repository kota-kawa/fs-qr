from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_fsqr_menu(test_client: TestClient):
    response = test_client.get("/fs-qr_menu")
    assert response.status_code == 200


def test_fsqr_upload_page(test_client: TestClient):
    response = test_client.get("/fs-qr")
    assert response.status_code == 200


def test_fsqr_search_page(test_client: TestClient):
    response = test_client.get("/search_fs-qr")
    assert response.status_code == 200


def test_remove_succes_page(test_client: TestClient):
    """削除完了ページが正常に表示される"""
    response = test_client.get("/remove-succes")
    assert response.status_code == 200


# --- アップロードバリデーション ---

def test_upload_no_file(test_client: TestClient):
    """ファイルなしでアップロードすると 400 を返す"""
    response = test_client.post("/upload", data={"name": "", "file_type": "multiple"})
    assert response.status_code == 400


def test_upload_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/upload",
        files={"upfile": ("test.txt", b"hello", "text/plain")},
        data={"name": "inv@lid", "file_type": "multiple"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_upload_wrong_id_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/upload",
        files={"upfile": ("test.txt", b"hello", "text/plain")},
        data={"name": "abc", "file_type": "multiple"},  # 3文字
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_upload_too_many_files(test_client: TestClient):
    """ファイル数が 10 を超えると 400 JSON エラーを返す"""
    files = [("upfile", (f"file{i}.txt", b"x", "text/plain")) for i in range(11)]
    response = test_client.post("/upload", files=files, data={"name": "", "file_type": "multiple"})
    assert response.status_code == 400
    assert "error" in response.json()


# --- try_login バリデーション ---

def test_try_login_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字を含む場合はエラーページを返す"""
    response = test_client.post("/try_login", data={"name": "bad!@#", "pw": "123456"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_try_login_invalid_pw_chars(test_client: TestClient):
    """パスワードに英字が混在する場合はエラーページを返す"""
    response = test_client.post("/try_login", data={"name": "abc123", "pw": "abc"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- upload_complete / download の 404 ---

def test_upload_complete_not_found(test_client: TestClient):
    """存在しない secure_id へのアクセスは 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        response = test_client.get("/upload_complete/nonexistent000")
    assert response.status_code == 404


def test_download_not_found(test_client: TestClient):
    """存在しない secure_id への download アクセスは 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        response = test_client.get("/download/nonexistent000")
    assert response.status_code == 404
