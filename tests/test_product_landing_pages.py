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
    (
        "/shared-task",
        "FS!QR Task",
        "/create_task_room",
        "カンバン",
    ),
)

ILLUSTRATED_LANDING_VISUALS = (
    ("/file-sharing", "apple-touch-icon.png", "fsqr-illustration.jpg"),
    ("/group-file-sharing", "apple-touch-icon2.png", "group-illustration.jpg"),
    ("/shared-note", "apple-touch-icon4.png", "note-illustration.jpg"),
    ("/shared-task", "apple-touch-icon5.png", "task-illustration.jpg"),
)

HOME_SERVICE_MENU_LINKS = ("/fs-qr_menu", "/group_menu", "/note_menu", "/task_menu")


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


def test_group_landing_page_offers_instant_share_box(test_client: TestClient):
    """Group LPは、ルームを作らずファイルを選べる共有ボックスを先頭に置く。"""
    response = test_client.get("/group-file-sharing")

    assert response.status_code == 200
    body = response.text

    assert 'id="instant-share-box"' in body
    assert "data-instant-share-box" in body
    assert "data-instant-dropzone" in body
    assert "data-instant-publish" in body
    assert '<meta name="csrf-token"' in body
    assert "/static/js/group_landing/instant-share.js" in body
    # 送信前の検証は共有モジュールを再利用する
    assert "/static/js/shared/upload-validation.js" in body

    # ヒーローより下の CTA を待たずにファイルを置ける位置にあること
    assert body.index('id="instant-share-box"') < body.index('id="how-it-works"')

    # 従来のルーム作成導線も残す
    assert 'href="/create_room"' in body


def test_group_landing_page_shows_share_details_after_publishing(
    test_client: TestClient,
):
    """発行後の共有情報（URL・QR・ID・パスワード）をLP上で提示する枠を持つ。"""
    response = test_client.get("/group-file-sharing")

    assert response.status_code == 200
    body = response.text

    assert "data-instant-share-panel" in body
    for marker in (
        "data-instant-share-url",
        "data-instant-room-id",
        "data-instant-password",
        "data-instant-qr",
        "data-instant-open",
    ):
        assert marker in body, marker

    assert "/static/qrcode.min.js" in body


def test_fsqr_landing_page_offers_instant_upload_box(test_client: TestClient):
    """FS!QR LPは、ページ上でファイルを選んで発行できる共有ボックスを置く。"""
    response = test_client.get("/file-sharing")

    assert response.status_code == 200
    body = response.text

    assert 'id="instant-upload-box"' in body
    assert "data-instant-fsqr" in body
    assert "data-instant-dropzone" in body
    assert "data-instant-publish" in body
    assert "data-instant-retention" in body
    assert '<meta name="csrf-token"' in body
    assert "/static/js/fsqr_landing/instant-upload.js" in body
    assert "/static/js/fs_qr_upload/encryption.js" in body
    assert "/static/js/shared/upload-validation.js" in body

    # ヒーロー直下でファイルを選べる位置にあること
    assert body.index('id="instant-upload-box"') < body.index('id="how-it-works"')

    # 詳細設定へ進む従来導線も残す
    assert 'href="/fs-qr"' in body


def test_fsqr_landing_page_shows_share_details_after_publishing(
    test_client: TestClient,
):
    """発行後の共有URL・QR・ID・パスワードを表示する枠を持つ。"""
    response = test_client.get("/file-sharing")

    assert response.status_code == 200
    body = response.text

    assert "data-instant-share-panel" in body
    for marker in (
        "data-instant-share-url",
        "data-instant-id",
        "data-instant-password",
        "data-instant-qr",
        "data-instant-open",
    ):
        assert marker in body, marker
    assert "/static/qrcode.min.js" in body


def test_group_landing_page_does_not_include_room_ui_mockup(
    test_client: TestClient,
):
    """実際の画面と異なるファイルルームのモックアップを掲載しない。"""
    response = test_client.get("/group-file-sharing")

    assert response.status_code == 200
    assert "lp-process-preview--group" not in response.text
    assert "提案資料_最新版.pdf" not in response.text


def test_group_landing_page_does_not_include_qr_code_decoration(
    test_client: TestClient,
):
    """共有リンクの案内に、実物らしく見えるQRコード装飾を使用しない。"""
    response = test_client.get("/group-file-sharing")

    assert response.status_code == 200
    assert "lp-share-visual__qr" not in response.text
    assert "lp-share-visual__recipients" in response.text


@pytest.mark.parametrize(
    ("path", "visual_class"),
    (
        ("/file-sharing", "lp-mockup--fsqr"),
        ("/shared-note", "lp-process-preview--note"),
    ),
)
def test_product_landing_pages_do_not_include_generated_ui_mockups(
    test_client: TestClient,
    path: str,
    visual_class: str,
):
    """実画面と誤認されうるUIモックアップを掲載しない。"""
    response = test_client.get(path)

    assert response.status_code == 200
    assert visual_class not in response.text


def test_note_landing_page_offers_instant_draft_editor(test_client: TestClient):
    """Note LPは、ルームを作らずその場で書ける下書きエディタを先頭に置く。"""
    response = test_client.get("/shared-note")

    assert response.status_code == 200
    body = response.text

    # エディタ本体と、JS が必要とする設定・CSRF トークンが揃っていること
    assert 'id="instant-note-editor"' in body
    assert "data-instant-note" in body
    assert "data-instant-share" in body
    assert '<meta name="csrf-token"' in body
    assert "/static/js/note_landing/instant-draft.js" in body

    # ヒーローより下の CTA を待たずに書き始められる位置にあること
    assert body.index('id="instant-note-editor"') < body.index('id="how-it-works"')

    # 従来のルーム作成導線も残す
    assert 'href="/create_note_room"' in body


def test_note_landing_page_shows_share_details_after_publishing(
    test_client: TestClient,
):
    """発行後の共有情報（URL・QR・ID・パスワード）をLP上で提示する枠を持つ。"""
    response = test_client.get("/shared-note")

    assert response.status_code == 200
    body = response.text

    assert "data-instant-share-panel" in body
    for marker in (
        "data-instant-share-url",
        "data-instant-room-id",
        "data-instant-password",
        "data-instant-qr",
        "data-instant-open",
    ):
        assert marker in body, marker

    # QRコード描画に使うライブラリを読み込んでいること
    assert "/static/qrcode.min.js" in body


def test_group_landing_page_use_cases_do_not_include_abstract_scenes(
    test_client: TestClient,
):
    """Group LPの利用シーンは装飾図ではなく、読みやすい文章カードで案内する。"""
    response = test_client.get("/group-file-sharing")

    assert response.status_code == 200
    assert "lp-use-card__scene" not in response.text
    assert "プロジェクト資料の集約" in response.text


def test_task_landing_page_offers_instant_draft_board(test_client: TestClient):
    """Task LPは、ルームを作らずタスクを書き出せる下書きボードを先頭に置く。"""
    response = test_client.get("/shared-task")

    assert response.status_code == 200
    body = response.text

    assert 'id="instant-board"' in body
    assert "data-instant-board" in body
    assert "data-instant-add-form" in body
    assert "data-instant-publish" in body
    assert '<meta name="csrf-token"' in body
    assert "/static/js/task_landing/instant-board.js" in body

    # ヒーローより下の CTA を待たずにタスクを書ける位置にあること
    assert body.index('id="instant-board"') < body.index('id="how-it-works"')

    # 従来のルーム作成導線も残す
    assert 'href="/create_task_room"' in body


def test_task_landing_page_shows_share_details_after_publishing(
    test_client: TestClient,
):
    """発行後の共有情報（URL・QR・ID・パスワード）をLP上で提示する枠を持つ。"""
    response = test_client.get("/shared-task")

    assert response.status_code == 200
    body = response.text

    assert "data-instant-share-panel" in body
    for marker in (
        "data-instant-share-url",
        "data-instant-room-id",
        "data-instant-password",
        "data-instant-qr",
        "data-instant-open",
    ):
        assert marker in body, marker

    assert "/static/qrcode.min.js" in body


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
