import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from Note.note_export import NotePdfFontUnavailableError, build_note_pdf
from settings import NOTE_MAX_CONTENT_LENGTH


ROOM_ID = "abc123"
ROOM_META = {"id": ROOM_ID, "retention_days": 7, "expires_at": None}
ROOM_ROW = {"content": "saved", "updated_at": object(), "version": 1}


def _export_patches(*, has_access=True, meta=ROOM_META, row=ROOM_ROW):
    return (
        patch("Note.note_api.has_note_room_access", return_value=has_access),
        patch(
            "Note.note_api.nd.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=meta,
        ),
        patch(
            "Note.note_api.nd.get_row",
            new_callable=AsyncMock,
            return_value=row,
        ),
    )


def test_note_export_txt_returns_current_editor_content(test_client):
    content = "現在の本文\nsecond line"
    access_patch, meta_patch, row_patch = _export_patches()
    with access_patch, meta_patch, row_patch:
        response = test_client.post(
            f"/api/note/{ROOM_ID}/export/txt",
            json={"content": content},
        )

    assert response.status_code == 200
    assert response.content == content.encode("utf-8")
    assert response.headers["content-type"].startswith("text/plain; charset=utf-8")
    assert response.headers["cache-control"] == "private, no-store"
    assert f'filename="note-{ROOM_ID}.txt"' in response.headers["content-disposition"]


def test_note_export_pdf_returns_attachment(test_client):
    access_patch, meta_patch, row_patch = _export_patches()
    with (
        access_patch,
        meta_patch,
        row_patch,
        patch("Note.note_api.build_note_pdf", return_value=b"%PDF-test") as build,
    ):
        response = test_client.post(
            f"/api/note/{ROOM_ID}/export/pdf",
            json={"content": "未保存の本文"},
        )

    assert response.status_code == 200
    assert response.content == b"%PDF-test"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert f'filename="note-{ROOM_ID}.pdf"' in response.headers["content-disposition"]
    build.assert_called_once_with("未保存の本文", ROOM_ID)


def test_note_export_requires_room_access(test_client):
    access_patch, meta_patch, row_patch = _export_patches(has_access=False)
    with access_patch, meta_patch as get_meta, row_patch as get_row:
        response = test_client.post(
            f"/api/note/{ROOM_ID}/export/txt", json={"content": "secret"}
        )

    assert response.status_code == 404
    get_meta.assert_not_awaited()
    get_row.assert_not_awaited()


def test_note_export_requires_csrf_token(test_client):
    response = asyncio.run(
        test_client._raw_request(
            "POST",
            f"/api/note/{ROOM_ID}/export/txt",
            json={"content": "secret"},
        )
    )

    assert response.status_code == 403


def test_note_export_rejects_expired_room(test_client):
    access_patch, meta_patch, row_patch = _export_patches(meta=None)
    with access_patch, meta_patch, row_patch as get_row:
        response = test_client.post(
            f"/api/note/{ROOM_ID}/export/txt", json={"content": "secret"}
        )

    assert response.status_code == 410
    get_row.assert_not_awaited()


def test_note_export_rejects_missing_content_row(test_client):
    access_patch, meta_patch, row_patch = _export_patches(row=None)
    with access_patch, meta_patch, row_patch:
        response = test_client.post(
            f"/api/note/{ROOM_ID}/export/txt", json={"content": "secret"}
        )

    assert response.status_code == 410


def test_note_export_validates_format_and_content_length(test_client):
    access_patch, meta_patch, row_patch = _export_patches()
    with access_patch, meta_patch, row_patch:
        invalid_format = test_client.post(
            f"/api/note/{ROOM_ID}/export/docx", json={"content": "text"}
        )
        too_long = test_client.post(
            f"/api/note/{ROOM_ID}/export/txt",
            json={"content": "a" * (NOTE_MAX_CONTENT_LENGTH + 1)},
        )

    assert invalid_format.status_code == 404
    assert too_long.status_code == 400


def test_note_export_buttons_are_rendered(test_client):
    with (
        patch("Note.note_app.has_note_room_access", return_value=True),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Note.note_app.nd.get_row",
            new_callable=AsyncMock,
            return_value=ROOM_ROW,
        ),
    ):
        response = test_client.get(f"/note/r/{ROOM_ID}")

    assert response.status_code == 200
    assert 'id="txtDownloadButton"' in response.text
    assert 'id="pdfDownloadButton"' in response.text
    assert "/static/js/note_room_realtime/export.js" in response.text


def test_build_note_pdf_preserves_plain_text_safely():
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    content = "first line\n<tag> & second line\n" + ("long-word " * 500)

    pdf = build_note_pdf(content, ROOM_ID, font_path=font_path)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1_000
    assert b"/CIDFontType2" in pdf
    assert b"/CIDFontType0" not in pdf


def test_build_note_pdf_rejects_non_truetype_outlines():
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

    with (
        patch("Note.note_export._has_truetype_outlines", return_value=False),
        pytest.raises(NotePdfFontUnavailableError),
    ):
        build_note_pdf("text", ROOM_ID, font_path=font_path)
