"""Product landing page routing and SEO regression tests.

プロダクトLPの公開性、検索メタデータ、主要CTAをまとめて検証する。
"""

import json
import re
import xml.etree.ElementTree as ET

import pytest
from starlette.testclient import TestClient


LANDING_PAGES = (
    (
        "/file-sharing",
        "FS!QR",
        "/fs-qr",
        "登録不要",
    ),
    (
        "/shared-note",
        "FS!QR Note",
        "/create_note_room",
        "リアルタイム",
    ),
    (
        "/group-file-sharing",
        "FS!QR Group",
        "/create_room",
        "ファイル共有",
    ),
)

ILLUSTRATED_LANDING_VISUALS = (
    ("/file-sharing", "apple-touch-icon.png", "fsqr-illustration.jpg"),
    ("/group-file-sharing", "apple-touch-icon2.png", "group-illustration.jpg"),
    ("/shared-note", "apple-touch-icon4.png", "note-illustration.jpg"),
)

PRODUCT_UI_VISUALS = (
    ("/file-sharing", "lp-mockup--fsqr", "共有の準備ができました"),
    ("/shared-note", "lp-process-preview--note", "リアルタイム同期"),
    ("/group-file-sharing", "lp-process-preview--group", "提案資料_最新版.pdf"),
)

HOME_SERVICE_MENU_LINKS = ("/fs-qr_menu", "/group_menu", "/note_menu")


@pytest.mark.parametrize("path,brand,primary_cta,search_marker", LANDING_PAGES)
def test_product_landing_page_has_indexable_seo_content(
    test_client: TestClient,
    path: str,
    brand: str,
    primary_cta: str,
    search_marker: str,
):
    response = test_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-language"] == "ja"
    assert '<meta name="robots" content="index, follow' in response.text
    assert f'<link rel="canonical" href="https://fs-qr.net{path}"' in response.text
    assert '<meta name="description"' in response.text
    assert '<meta property="og:title"' in response.text
    assert '<meta name="twitter:card" content="summary_large_image"' in response.text
    assert brand in response.text
    assert search_marker in response.text
    assert f'href="{primary_cta}"' in response.text
    assert '<main id="main-content"' in response.text
    assert response.text.count("<h1") == 1


@pytest.mark.parametrize("path,_,__,___", LANDING_PAGES)
def test_product_landing_page_exposes_valid_structured_data(
    test_client: TestClient,
    path: str,
    _: str,
    __: str,
    ___: str,
):
    response = test_client.get(path)
    blocks = re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        response.text,
        flags=re.DOTALL,
    )

    assert blocks
    payloads = [json.loads(block) for block in blocks]
    schema_types = {payload.get("@type") for payload in payloads}
    assert "SoftwareApplication" in schema_types
    assert "FAQPage" in schema_types


def test_product_landing_pages_are_listed_in_sitemap(test_client: TestClient):
    response = test_client.get("/sitemap.xml")
    root = ET.fromstring(response.text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {
        node.text for node in root.findall("sm:url/sm:loc", namespace) if node.text
    }

    for path, *_ in LANDING_PAGES:
        assert f"https://fs-qr.net{path}" in locations


def test_home_page_links_to_service_menu_pages(test_client: TestClient):
    """トップページのサービスカードはLPではなく各メニュー画面へ案内する。"""
    response = test_client.get("/")

    assert response.status_code == 200
    for path in HOME_SERVICE_MENU_LINKS:
        assert f'href="{path}"' in response.text

    for path, *_ in LANDING_PAGES:
        assert f'href="{path}"' not in response.text


@pytest.mark.parametrize("path,icon_name,page_image_name", ILLUSTRATED_LANDING_VISUALS)
def test_product_landing_page_uses_service_icon_and_generated_illustration(
    test_client: TestClient,
    path: str,
    icon_name: str,
    page_image_name: str,
):
    """LPのブランドアイコンと、文字を含まない各サービス用イラストを検証する。"""
    response = test_client.get(path)

    assert response.status_code == 200
    assert f"/static/{icon_name}" in response.text
    image_path = f"/static/images/product-landing-pages/{page_image_name}"
    assert image_path in response.text

    image_response = test_client.get(image_path)
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/jpeg"


@pytest.mark.parametrize("path,visual_class,content_marker", PRODUCT_UI_VISUALS)
def test_product_landing_page_also_uses_product_ui_visual(
    test_client: TestClient,
    path: str,
    visual_class: str,
    content_marker: str,
):
    """各LPは生成イラストに加え、利用方法が伝わるUI図解も表示する。"""
    response = test_client.get(path)

    assert response.status_code == 200
    assert visual_class in response.text
    assert content_marker in response.text


@pytest.mark.parametrize("path,_,__,___", LANDING_PAGES)
def test_product_landing_page_normalizes_tracking_queries(
    test_client: TestClient,
    path: str,
    _: str,
    __: str,
    ___: str,
):
    response = test_client.get(f"{path}?utm_source=test", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["location"].endswith(path)
