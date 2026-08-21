import base64
import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

from Note.note_collaboration import TOKEN_TTL_SECONDS, create_collaboration_token


def test_yjs_state_exists_in_fresh_schema_and_upgrade_migration():
    fresh_schema = Path("db_init/create_tables.sql").read_text(encoding="utf-8")
    migration = Path("alembic/versions/20260821_0013_note_yjs_state.py").read_text(
        encoding="utf-8"
    )

    assert "yjs_state LONGBLOB NULL" in fresh_schema
    assert "ADD COLUMN yjs_state LONGBLOB NULL" in migration


def test_collaboration_token_is_room_scoped_and_signed():
    with patch("Note.note_collaboration.SECRET_KEY", "test-secret"):
        token = create_collaboration_token("room-42", now=100)

    body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    expected = hmac.new(b"test-secret", body.encode("ascii"), hashlib.sha256).digest()

    assert payload == {"room": "room-42", "exp": 100 + TOKEN_TTL_SECONDS}
    assert hmac.compare_digest(base64.urlsafe_b64decode(signature + "=="), expected)


def test_collaboration_token_requires_secret_key():
    with (
        patch("Note.note_collaboration.SECRET_KEY", None),
        patch("Note.note_collaboration.time.time", return_value=100),
    ):
        try:
            create_collaboration_token("room-42")
        except RuntimeError as exc:
            assert str(exc) == "SECRET_KEY is required for Note collaboration"
        else:  # pragma: no cover - safety assertion
            raise AssertionError("missing SECRET_KEY must be rejected")


def test_note_room_uses_bundled_yjs_client_and_not_legacy_sync(test_client):
    from unittest.mock import AsyncMock

    meta = {
        "id": "public1",
        "room_id": "abc123",
        "retention_hours": 24,
        "expires_at": None,
    }
    with (
        patch(
            "Note.note_app.nd.get_room_meta_direct",
            new=AsyncMock(return_value=meta),
        ),
        patch("Note.note_app.has_note_room_access", return_value=True),
        patch(
            "Note.note_app.check_rate_limit",
            new=AsyncMock(return_value=(True, None, None)),
        ),
        patch("Note.note_app.nd.get_row", new=AsyncMock(return_value={"content": ""})),
        patch("Note.note_app.register_success", new=AsyncMock()),
        patch("Note.note_app.create_collaboration_token", return_value="signed.token"),
    ):
        response = test_client.get("/note/r/abc123")

    assert response.status_code == 200
    assert "yjs-collaboration.js" in response.text
    assert 'collaborationToken: "signed.token"' in response.text
    assert "note_room_realtime/socket.js" not in response.text
    assert "/ws/note/" not in response.text
