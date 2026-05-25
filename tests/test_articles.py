import pytest
from starlette.testclient import TestClient

from Articles.articles_registry import ARTICLES, get_article_by_slug


def test_articles_index(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200


def test_articles_index_lists_all_articles(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200
    body = response.text
    for article in ARTICLES:
        assert f'/{article["slug"]}' in body
        assert article["title"] in body


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: a["slug"])
def test_registered_article_route(test_client: TestClient, article):
    response = test_client.get(f"/{article['slug']}")
    assert response.status_code == 200


def test_default_articles_present():
    """既存6記事がデフォルトとして維持されていること。"""
    default_slugs = {a["slug"] for a in ARTICLES if a.get("default")}
    expected = {
        "fs-qr-concept",
        "safe-sharing",
        "encryption",
        "education",
        "business",
        "risk-mitigation",
    }
    assert expected <= default_slugs


def test_article_sitemap_entries(test_client: TestClient):
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200
    for article in ARTICLES:
        assert f"https://fs-qr.net/{article['slug']}" in response.text


def test_get_article_by_slug():
    assert get_article_by_slug("fs-qr-concept") is not None
    assert get_article_by_slug("does-not-exist") is None
