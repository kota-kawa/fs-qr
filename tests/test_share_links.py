import asyncio
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import share_links
from share_links import ServiceKey


class FakeUrl:
    def __init__(self, value: str, path: str):
        self.value = value
        self.path = path

    def __str__(self):
        return self.value


class FakeRequest:
    def url_for(self, name: str, **params):
        token = params.get("token")
        room_id = params.get("room_id")
        if token:
            path = f"/{name}/{token}"
        else:
            path = f"/{name}/{room_id}"
        return FakeUrl(f"http://testserver{path}", path)


def test_hash_token_uses_secret_key():
    with patch("share_links.SECRET_KEY", "secret"):
        assert (
            share_links.hash_token("token")
            == hmac.new(b"secret", b"token", hashlib.sha256).hexdigest()
        )


def test_hash_token_without_secret_uses_plain_sha256():
    with patch("share_links.SECRET_KEY", ""):
        assert share_links.hash_token("token") == hashlib.sha256(b"token").hexdigest()


def test_share_password_round_trip_and_not_cleartext():
    enc = share_links.encrypt_share_password("024680")
    # 暗号文には平文が含まれない（at-rest で読めない）
    assert "024680" not in enc
    assert enc != "024680"
    assert share_links.decrypt_share_password(enc) == "024680"


def test_share_link_password_decrypts_metadata():
    enc = share_links.encrypt_share_password("135790")
    link = {"resource_id": "r1", "metadata": {"password_enc": enc}}
    assert share_links.share_link_password(link) == "135790"


def test_share_link_password_absent_or_invalid_returns_empty():
    assert share_links.share_link_password(None) == ""
    assert share_links.share_link_password({"metadata": {}}) == ""
    assert (
        share_links.share_link_password({"metadata": {"password_enc": "not-a-token"}})
        == ""
    )


def test_decrypt_with_wrong_key_returns_empty():
    # 鍵（SECRET_KEY）が異なると復号できない
    share_links._fernet = None
    with patch("share_links.SECRET_KEY", "key-a"):
        enc = share_links.encrypt_share_password("024680")
    share_links._fernet = None
    with patch("share_links.SECRET_KEY", "key-b"):
        assert share_links.decrypt_share_password(enc) == ""
    share_links._fernet = None


def test_build_share_url_and_room_url():
    request = FakeRequest()

    share_url = share_links.build_share_url(
        request, service_key=ServiceKey.GROUP, token="tok123", fragment="files"
    )
    room_url = share_links.build_room_url(
        request, service_key=ServiceKey.NOTE, resource_id="abc123"
    )

    assert share_url == "http://testserver/group.share_entry/tok123#files"
    assert room_url == "/note.note_room/abc123"


def test_create_share_link_inserts_hashed_token():
    execute_mock = AsyncMock()
    with (
        patch("share_links.generate_token", return_value="generated-token"),
        patch("share_links.execute_query", execute_mock),
        patch("share_links.hash_token", return_value="hashed-token"),
    ):
        token = asyncio.run(
            share_links.create_share_link(
                service_key=ServiceKey.FSQR,
                resource_id="secure123",
                expires_at="2026-05-25 00:00:00",
                metadata={"id": "room123"},
            )
        )

    assert token == "generated-token"
    params = execute_mock.await_args.args[1]
    assert params == {
        "service_key": "fsqr",
        "resource_id": "secure123",
        "token_hash": "hashed-token",
        "scope": "read",
        "expires_at": "2026-05-25 00:00:00",
        "metadata": '{"id": "room123"}',
    }


def test_resolve_share_link_rejects_short_token_without_query():
    execute_mock = AsyncMock()
    with patch("share_links.execute_query", execute_mock):
        result = asyncio.run(share_links.resolve_share_link("short"))

    assert result is None
    execute_mock.assert_not_awaited()


def test_resolve_share_link_returns_none_for_missing_or_service_mismatch():
    with patch("share_links.execute_query", AsyncMock(return_value=[])):
        assert (
            asyncio.run(
                share_links.resolve_share_link("a" * 32, service_key=ServiceKey.NOTE)
            )
            is None
        )

    with patch(
        "share_links.execute_query",
        AsyncMock(return_value=[{"service_key": "group", "resource_id": "abc123"}]),
    ):
        assert (
            asyncio.run(
                share_links.resolve_share_link("a" * 32, service_key=ServiceKey.NOTE)
            )
            is None
        )


def test_resolve_share_link_returns_matching_row():
    row = {
        "service_key": "note",
        "resource_id": "abc123",
        "scope": "read",
        "metadata": "{}",
    }
    with patch("share_links.execute_query", AsyncMock(return_value=[row])):
        result = asyncio.run(
            share_links.resolve_share_link("a" * 32, service_key=ServiceKey.NOTE)
        )

    assert result == row


def test_revoke_resource_links_marks_active_links_revoked():
    execute_mock = AsyncMock()
    with patch("share_links.execute_query", execute_mock):
        asyncio.run(
            share_links.revoke_resource_links(
                service_key=ServiceKey.GROUP, resource_id="abc123"
            )
        )

    assert execute_mock.await_args.args[1] == {
        "service_key": "group",
        "resource_id": "abc123",
    }
