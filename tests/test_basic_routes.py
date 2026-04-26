from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_index(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'action="/search_all"' in response.text
    assert "すべてから検索" in response.text


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


def test_session_middleware_order():
    from app import app

    class_names = [middleware.cls.__name__ for middleware in app.user_middleware]
    session_index = next(
        i for i, name in enumerate(class_names) if "SessionMiddleware" in name
    )
    autoload_index = next(
        i for i, name in enumerate(class_names) if "SessionAutoloadMiddleware" in name
    )
    assert session_index < autoload_index


def test_search_all_fsqr_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch("top_search.register_success", new_callable=AsyncMock),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[{"id": "abc123"}],
        ),
        patch(
            "top_search.group_data.pich_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "top_search.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/fs-qr/abc123/654321"


def test_search_all_group_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch("top_search.register_success", new_callable=AsyncMock),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "top_search.group_data.pich_room_id_direct",
            new_callable=AsyncMock,
            return_value="grp123",
        ),
        patch(
            "top_search.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/group/grp123/654321"


def test_search_all_note_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch("top_search.register_success", new_callable=AsyncMock),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "top_search.group_data.pich_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "top_search.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value="not123",
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/note/not123/654321"


def test_search_all_multiple_matches_returns_choice_page(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch("top_search.register_success", new_callable=AsyncMock),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[{"id": "abc123"}],
        ),
        patch(
            "top_search.group_data.pich_room_id_direct",
            new_callable=AsyncMock,
            return_value="grp123",
        ),
        patch(
            "top_search.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value="not123",
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 200
    assert "QRコード共有" in response.text
    assert "グループ共有" in response.text
    assert "ノート共有" in response.text
    assert 'href="/fs-qr/abc123/654321"' in response.text
    assert 'href="/group/grp123/654321"' in response.text
    assert 'href="/note/not123/654321"' in response.text
    assert "noindex, nofollow" in response.text


def test_search_all_no_match_returns_404(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "top_search.register_failure",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "top_search.group_data.pich_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "top_search.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 404
    assert "見つかりませんでした" in response.text


def test_search_all_invalid_input_returns_400(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "top_search.register_failure",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
    ):
        response = test_client.post(
            "/search_all", data={"id": "bad!!", "password": "654321"}
        )

    assert response.status_code == 400
    assert "不正な値" in response.text


def test_search_all_rate_limited_returns_429(test_client: TestClient):
    with patch(
        "top_search.check_rate_limit",
        new_callable=AsyncMock,
        return_value=(False, None, "30分"),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 429
    assert "30分" in response.text
