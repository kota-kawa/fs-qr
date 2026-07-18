import xml.etree.ElementTree as ET
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from Articles.articles_app import ARTICLES_PER_PAGE
from Articles.articles_registry import (
    ARTICLES,
    TYPE_ARTICLE,
    TYPE_GUIDE,
    get_article_by_slug,
    get_blog_articles_sorted,
    get_indexable_articles,
    get_indexable_blog_articles_sorted,
    get_indexable_guides,
    get_guides,
    is_indexable_article,
)
from i18n import SUPPORTED_LANGUAGES

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_articles_index(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200


def test_articles_index_lists_indexable_articles(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200
    body = response.text
    for article in get_indexable_guides():
        assert f"/{article['slug']}" in body
        assert article["title"] in body
    for article in get_indexable_blog_articles_sorted()[:ARTICLES_PER_PAGE]:
        assert f"/{article['slug']}" in body
        assert article["title"] in body
    hidden_articles = [
        article
        for article in ARTICLES
        if (
            not is_indexable_article(article)
            or article in get_indexable_blog_articles_sorted()[ARTICLES_PER_PAGE:]
        )
    ]
    for article in hidden_articles:
        assert f"/{article['slug']}" not in body


def test_off_topic_ai_articles_are_not_indexable():
    """FS!QRの主題外記事は一覧・sitemap・AdSense対象から除外する。"""
    excluded_slugs = {
        "ai-live-translation-practical-guide",
        "ai-ad-transparency-guide",
    }
    articles_by_slug = {article["slug"]: article for article in ARTICLES}
    for slug in excluded_slugs:
        assert slug in articles_by_slug
        assert not is_indexable_article(articles_by_slug[slug])


def test_public_articles_do_not_claim_unsupported_deletion_guarantees():
    """記事の機能説明が実装範囲を超えないようにする。"""
    article_templates = [
        PROJECT_ROOT / "Articles" / "templates" / name
        for name in (
            "auto-delete-benefits.html",
            "browser-based-sharing.html",
            "event-material-distribution.html",
            "no-registration-file-sharing.html",
            "pc-mobile-transfer.html",
            "pdf-compression-free.html",
            "school-meeting-class-examples.html",
            "smartphone-receiving.html",
            "business.html",
            "telework-security.html",
        )
    ]
    forbidden_phrases = (
        "物理的に完全消去",
        "バックアップやゴミ箱といった一時退避場所にも残らない",
        "ダウンロードが完了した時点で",
        "漏洩リスクをほぼゼロ",
        "【1時間】リアルタイムでの受け渡し",
        "多くの企業セキュリティポリシーに適合",
        "不正アクセスや辞書攻撃（総当たり攻撃）によるダウンロードを強力に遮断",
        "安全性を劇的に向上させる",
    )
    for path in article_templates:
        body = path.read_text(encoding="utf-8")
        assert not any(phrase in body for phrase in forbidden_phrases), path


def test_auto_delete_period_translations_are_specific_per_locale():
    """自動削除記事の保持期間説明を各言語で書き分ける。"""
    locale_dir = PROJECT_ROOT / "locales"
    intro_key = (
        "FS!QRは、「保存」ではなく「共有（受け渡し）」そのものにフォーカスして設計されたサービスです。"
        "その最大の特徴である「自動削除機能」は、設定した保持期間が終わると、サービス上の共有データと登録情報を削除します。"
        "不要になった共有を残し続けないことで、管理の手間と、古いリンクが有効なまま残る期間を減らせます。"
        "ここでは、自動削除を安全な運用に組み込む方法と、利用時に確認したい点を解説します。"
    )
    period_keys = (
        "メールやチャットでファイルを送り、相手が当日中に確認・ダウンロードする予定のときに向いています。"
        "時差がある相手には、受け取りに必要な時間を見積もって設定してください。"
        "期限を短くしても誤送信や端末への保存を防ぐものではありません。",
        "数日間のイベントや週次の進捗確認など、一定期間内に複数回アクセスする予定がある場合に向いています。"
        "参加者やメンバーへ期限を事前に伝え、受け渡しが終わったら必要に応じて手動削除も行いましょう。",
        "月単位のプロジェクトなど、短期共有より長い期間が必要な場合に選択肢になります。"
        "30日を超えて保管したい資料や、監査・契約で保存が求められる情報は、共有ではなく正式なストレージへ移してください。",
    )
    for lang in SUPPORTED_LANGUAGES:
        path = locale_dir / lang / "phrases" / "articles" / "auto-delete-benefits.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert intro_key in data, f"{lang}: auto-delete introduction is missing"
        period_values = [data[key] for key in period_keys]
        assert len(set(period_values)) == 3, (
            f"{lang}: 1/7/30-day guidance must be translated separately"
        )


def test_article_base_shows_editorial_date(test_client: TestClient):
    """記事本文に公開日を表示し、構造化データだけに依存しない。"""
    response = test_client.get("/safe-sharing")
    assert response.status_code == 200
    assert '<p class="article-byline"' in response.text
    assert (
        '<time datetime="2025-08-30T00:00:00+09:00">2025-08-30</time>' in response.text
    )
    assert (
        '<time datetime="2026-07-18T00:00:00+09:00">2026-07-18</time>' in response.text
    )


def test_article_heading_and_hero_alt_are_descriptive(test_client: TestClient):
    """記事の主見出しとヒーロー画像altは本文タイトルを反映する。"""
    for slug, title in (
        ("safe-sharing", "ファイル共有の送信前・受信後チェックリスト"),
        ("fs-qr-concept", "QRコードで一時共有する仕組みと、向いている場面"),
    ):
        response = test_client.get(f"/{slug}")
        assert response.status_code == 200
        assert f'<h1 class="mb-4">{title}</h1>' in response.text
        assert f'alt="{title}"' in response.text
        assert '<p class="article-byline"' in response.text


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: a["slug"])
def test_registered_article_thumbnail_file_exists(article):
    thumbnail = article.get("thumbnail")
    assert thumbnail
    assert (PROJECT_ROOT / "static" / thumbnail).is_file()


def test_articles_index_renders_visible_article_thumbnails(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200
    body = response.text
    visible_articles = [
        *get_indexable_guides(),
        *get_indexable_blog_articles_sorted()[:ARTICLES_PER_PAGE],
    ]
    for article in visible_articles:
        assert f"/static/{article['thumbnail']}?v=" in body


def test_articles_second_page_is_not_created_for_the_curated_set(
    test_client: TestClient,
):
    response = test_client.get("/articles/page/2")
    assert response.status_code == 404


def test_adsense_review_keeps_only_curated_public_articles():
    expected = {
        "fs-qr-concept",
        "safe-sharing",
        "encryption",
        "education",
        "business",
        "risk-mitigation",
        "file-sharing-troubleshooting",
        "group-room-access-troubleshooting",
        "shared-note-sync-troubleshooting",
        "remove-photo-location-data",
        "send-photos-without-quality-loss",
    }
    assert {article["slug"] for article in get_indexable_articles()} == expected


def test_articles_page_one_redirects_to_canonical_index(test_client: TestClient):
    response = test_client.get("/articles/page/1")
    assert response.status_code == 301
    assert response.headers["location"] == "http://testserver/articles"


def test_articles_out_of_range_page_returns_404(test_client: TestClient):
    response = test_client.get("/articles/page/999")
    assert response.status_code == 404


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: a["slug"])
def test_registered_article_route(test_client: TestClient, article):
    response = test_client.get(f"/{article['slug']}")
    assert response.status_code == 200
    assert f"/static/{article['thumbnail']}?v=" in response.text
    assert (
        f'<meta property="og:image" content="https://fs-qr.net/static/{article["thumbnail"]}"'
        in response.text
    )
    if is_indexable_article(article):
        assert '<meta name="robots" content="index, follow"' in response.text
    else:
        assert '<meta name="robots" content="noindex, follow"' in response.text


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
    for article in get_indexable_articles():
        assert f"https://fs-qr.net/{article['slug']}" in response.text
    for article in ARTICLES:
        if not is_indexable_article(article):
            assert f"https://fs-qr.net/{article['slug']}" not in response.text


def test_article_sitemap_uses_visible_modified_date(test_client: TestClient):
    """本文の更新日と個別sitemapのlastmodを一致させる。"""
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(response.text)
    entries = {
        url.find("sm:loc", ns).text: url.find("sm:lastmod", ns).text
        for url in root.findall("sm:url", ns)
        if url.find("sm:loc", ns) is not None and url.find("sm:lastmod", ns) is not None
    }
    assert entries["https://fs-qr.net/safe-sharing"] == "2026-07-18"


def test_article_sitemap_lastmod_uses_template_modified_date(test_client: TestClient):
    """article_modified指定がある記事はsitemapにも同じ更新日を出す。"""
    from app import _article_lastmod

    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ET.fromstring(response.text)
    entries = {
        url.find(
            "sm:loc", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        ).text: url
        for url in root.findall(
            "sm:url", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        )
        if url.find("sm:loc", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"})
        is not None
    }
    for article in get_indexable_articles():
        entry = entries[f"https://fs-qr.net/{article['slug']}"]
        lastmod = entry.find(
            "sm:lastmod", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        )
        assert lastmod is not None
        assert lastmod.text == _article_lastmod(article)


def test_articles_index_sitemap_lastmod_tracks_newest_article(test_client: TestClient):
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(response.text)
    for url in root.findall("sm:url", ns):
        loc = url.find("sm:loc", ns)
        if loc is not None and loc.text == "https://fs-qr.net/articles":
            lastmod = url.find("sm:lastmod", ns)
            assert lastmod is not None
            from app import _articles_lastmod, _template_lastmod

            expected_lastmod = max(
                _template_lastmod("Articles/templates/articles.html"),
                _articles_lastmod(),
            )
            assert lastmod.text == expected_lastmod
            break
    else:
        raise AssertionError("/articles entry is missing from sitemap")


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


def test_blog_articles_sorted_uses_later_registry_order_for_same_day():
    blog = get_blog_articles_sorted()
    indexes = {article["slug"]: index for index, article in enumerate(ARTICLES)}
    for previous, current in zip(blog, blog[1:]):
        if previous["date"] == current["date"]:
            assert indexes[previous["slug"]] > indexes[current["slug"]]


def test_articles_index_renders_both_sections(test_client: TestClient):
    body = test_client.get("/articles").text
    assert "サービス解説ガイド" in body
    assert "新着記事" in body


def test_articles_index_does_not_render_new_badge(test_client: TestClient):
    body = test_client.get("/articles").text
    assert "article-new-badge" not in body
    assert ">NEW<" not in body
