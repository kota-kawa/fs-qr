import pytest
from starlette.testclient import TestClient

from Articles.articles_registry import (
    ARTICLES,
    TYPE_ARTICLE,
    TYPE_GUIDE,
    get_article_by_slug,
    get_blog_articles_sorted,
    get_guides,
)


def test_articles_index(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200


def test_articles_index_lists_all_articles(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200
    body = response.text
    for article in ARTICLES:
        assert f"/{article['slug']}" in body
        assert article["title"] in body


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: a["slug"])
def test_registered_article_route(test_client: TestClient, article):
    response = test_client.get(f"/{article['slug']}")
    assert response.status_code == 200


# fsqr / group / note いずれかのサービス入口URL
SERVICE_MENU_URLS = ("/fs-qr_menu", "/group_menu", "/note_menu")
SERVICE_CTA_IMAGES = {
    "fs-qr-concept": "/static/fsqr.png",
    "education": "/static/group.png",
    "business": "/static/note.png",
}


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: a["slug"])
def test_article_links_to_a_service(test_client: TestClient, article):
    """全ての記事が fsqr / note / group のいずれかへの導線を持つこと。"""
    body = test_client.get(f"/{article['slug']}").text
    assert any(f'href="{url}"' in body for url in SERVICE_MENU_URLS), (
        f"{article['slug']} has no service CTA"
    )


@pytest.mark.parametrize("slug,image_path", SERVICE_CTA_IMAGES.items())
def test_article_service_cta_renders_service_image(
    test_client: TestClient, slug, image_path
):
    body = test_client.get(f"/{slug}").text
    assert f'src="{image_path}"' in body


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


def test_guides_are_the_default_evergreen_set():
    guides = get_guides()
    assert {g["slug"] for g in guides} == {
        "fs-qr-concept",
        "safe-sharing",
        "encryption",
        "education",
        "business",
        "risk-mitigation",
    }
    assert all(g["type"] == TYPE_GUIDE for g in guides)


def test_blog_articles_sorted_newest_first():
    blog = get_blog_articles_sorted()
    assert all(a["type"] == TYPE_ARTICLE for a in blog)
    dates = [a["date"] for a in blog]
    assert dates == sorted(dates, reverse=True)


def test_articles_index_renders_both_sections(test_client: TestClient):
    body = test_client.get("/articles").text
    assert "サービス解説ガイド" in body
    assert "新着記事" in body


def test_articles_index_does_not_render_new_badge(test_client: TestClient):
    body = test_client.get("/articles").text
    assert "article-new-badge" not in body
    assert ">NEW<" not in body
