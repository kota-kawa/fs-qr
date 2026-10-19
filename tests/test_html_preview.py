import re
from unittest.mock import patch

import pytest

from i18n import SUPPORTED_LANGUAGES


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_html_preview_renders_localized_tool(test_client, language):
    with patch("database.execute_query") as query:
        response = test_client.get(f"/html-preview?lang={language}")

    assert response.status_code == 200
    assert response.headers["content-language"] == language
    assert 'sandbox="allow-scripts"' in response.text
    assert "allow-same-origin" not in response.text
    assert 'id="html-source"' in response.text
    assert 'id="html-preview"' in response.text
    assert "html.title" not in response.text
    assert "html.notice" not in response.text
    assert "FSQR_TAGS" not in response.text
    assert "csrf-token" not in response.text
    assert 'src="https://' not in response.text
    assert not re.search(
        r'<(?:link|script)\b[^>]*(?:href|src)="https://cdn', response.text
    )
    assert response.headers["cache-control"] == "no-store"
    query.assert_not_called()


def test_html_preview_blocks_network_and_ignores_pasted_query(test_client):
    response = test_client.get("/html-preview?html=private-content")
    policy = response.headers["content-security-policy"]
    assert "connect-src https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/" in policy
    assert "style-src 'self' 'unsafe-inline';" in policy
    assert "form-action 'none'" in policy
    assert "object-src 'none'" in policy
    assert "private-content" not in response.text
    assert "https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js" in policy
    assert "https://cdn.jsdelivr.net;" not in policy


def test_html_preview_does_not_accept_uploads(test_client):
    response = test_client.post("/html-preview", json={"html": "private-content"})
    assert response.status_code == 405


def test_html_preview_is_discoverable(test_client):
    for path in ("/", "/fs-qr", "/group", "/note", "/task"):
        assert 'href="/html-preview"' in test_client.get(path).text
    assert "/html-preview" in test_client.get("/sitemap.xml").text
