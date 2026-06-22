"""SEO-related multilingual tests.

These cover:
- sitemap.xml lists canonical URLs without sitemap-managed hreflang alternates
- meta description / og:description / title are translated for every locale on the home page
- geo.region and geo.placename adapt to the request locale
- JSON-LD inLanguage matches the request locale
- Arabic responses set dir="rtl"
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from starlette.testclient import TestClient


SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

DESC_RE = re.compile(r'<meta name="description" content="([^"]+)"')


def test_sitemap_lists_canonical_urls_without_hreflang_alternates(
    test_client: TestClient,
):
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.text)
    urls = root.findall("sm:url", SITEMAP_NS)
    assert urls, "sitemap should contain at least one <url>"

    for url in urls:
        loc = url.find("sm:loc", SITEMAP_NS)
        assert loc is not None and loc.text
        assert "?" not in loc.text
        assert not url.findall("xhtml:link", SITEMAP_NS)


def test_sitemap_includes_terms_page(test_client: TestClient):
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200

    root = ET.fromstring(response.text)
    locs = {loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)}
    assert "https://fs-qr.net/terms" in locs


def test_sitemap_keeps_all_existing_public_pages(test_client: TestClient):
    """AdSense fixes must improve listed pages, not remove them from sitemap."""
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200

    root = ET.fromstring(response.text)
    locs = {loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)}

    expected_locs = {
        "https://fs-qr.net/",
        "https://fs-qr.net/about",
        "https://fs-qr.net/contact",
        "https://fs-qr.net/usage",
        "https://fs-qr.net/privacy-policy",
        "https://fs-qr.net/terms",
        "https://fs-qr.net/site-operator",
        "https://fs-qr.net/articles",
        "https://fs-qr.net/fs-qr_menu",
        "https://fs-qr.net/fs-qr",
        "https://fs-qr.net/group_menu",
        "https://fs-qr.net/group",
        "https://fs-qr.net/create_room",
        "https://fs-qr.net/note_menu",
        "https://fs-qr.net/note",
        "https://fs-qr.net/create_note_room",
    }

    assert expected_locs <= locs


def test_adsense_risk_copy_does_not_reappear_in_public_copy_sources():
    stale_snippets = (
        "最高レベルのセキュリティ",
        "管理画面から短縮・延長",
        "AES-256によるエンドツーエンド暗号化",
        "ダウンロード履歴はダッシュボード",
        "追加でPINコード",
        "PINコードや有効期限",
        "ダッシュボードでダウンロード履歴やアクセス元",
        "PC側でFS!QRの「受け取り」メニュー",
        "4桁〜6桁の短いコード",
        "表示された短縮URL",
    )
    roots = (Path("FSQR"), Path("Articles"), Path("locales"))
    paths = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.suffix in {".html", ".json"}
    ]

    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for snippet in stale_snippets:
            if snippet in text:
                offenders.append(f"{path}: {snippet}")

    assert offenders == []


def test_home_meta_description_is_translated_for_every_locale(
    test_client: TestClient,
):
    """The biggest SEO regression we just fixed: meta description must not
    fall back to English in tr/uk/pl/sw/ar/ko/zh-TW etc.
    """
    from i18n import SUPPORTED_LANGUAGES

    # Markers proving the meta description is in the target language, not Japanese
    # nor English. The first marker must appear in the description content.
    language_markers = {
        "ja": "日本語",
        "en": "free file sharing",
        "zh-CN": "免费",
        "zh-TW": "免費",
        "ko": "무료",
        "fr": "gratuit",
        "es": "gratuito",
        "de": "kostenlos",
        "pt": "gratuito",
        "it": "gratuito",
        "ru": "бесплат",
        "nl": "gratis",
        "hi": "मुफ्त",
        "bn": "বিনামূল্যে",
        "vi": "miễn phí",
        "th": "ฟรี",
        "id": "gratis",
        "tr": "ücretsiz",
        "uk": "безкоштов",
        "pl": "darmow",
        "sw": "bila malipo",
        "ar": "مجاني",
    }

    for language in SUPPORTED_LANGUAGES:
        cookie = {"Cookie": f"fsqr_language={language}"}
        response = test_client.get("/", headers=cookie)
        assert response.status_code == 200, language

        match = DESC_RE.search(response.text)
        assert match, f"{language}: no meta description"
        desc = match.group(1)

        marker = language_markers[language]
        assert marker.lower() in desc.lower(), (
            f"{language}: meta description missing language marker {marker!r}; "
            f"got {desc[:120]!r}"
        )


def test_target_pages_keep_page_specific_meta_descriptions(test_client: TestClient):
    routes = {
        "/": ("登録不要", "no registration"),
        "/group_menu": ("アカウント不要", "without accounts"),
        "/group": ("グループファイル共有ページ", "without registration"),
        "/note_menu": ("リアルタイム同時編集", "collaborative note"),
        "/note": ("議事録を同時編集", "co-edit meeting notes"),
        "/fs-qr_menu": ("アプリ不要", "No app"),
        "/fs-qr": ("共有リンク", "share them by QR code or link"),
    }

    for route, (ja_marker, en_marker) in routes.items():
        response_ja = test_client.get(route)
        assert response_ja.status_code == 200, route
        match_ja = DESC_RE.search(response_ja.text)
        assert match_ja, f"{route}: no Japanese meta description"
        assert ja_marker in match_ja.group(1), route

        response_en = test_client.get(f"{route}?lang=en")
        assert response_en.status_code == 200, route
        match_en = DESC_RE.search(response_en.text)
        assert match_en, f"{route}: no English meta description"
        desc_en = match_en.group(1)
        assert en_marker.lower() in desc_en.lower(), route
        assert "QR code transfers, group file sharing" not in desc_en, route


def test_target_pages_render_seo_intent_text_in_english(test_client: TestClient):
    routes = {
        "/": "file transfer",
        "/group_menu": "shared folder",
        "/group": "shared folder",
        "/note_menu": "meeting notes",
        "/note": "meeting notes",
        "/fs-qr_menu": "time-limited sharing",
        "/fs-qr": "time-limited sharing",
    }

    for route, marker in routes.items():
        response = test_client.get(f"{route}?lang=en")
        assert response.status_code == 200, route
        assert marker in response.text, route
        assert "seo." not in response.text, route


def test_home_geo_region_adapts_to_locale(test_client: TestClient):
    from i18n import GEO_REGION_MAP, SUPPORTED_LANGUAGES

    region_re = re.compile(r'<meta name="geo\.region" content="([^"]+)"')

    for language in SUPPORTED_LANGUAGES:
        region = GEO_REGION_MAP[language][0]
        response = test_client.get("/", headers={"Cookie": f"fsqr_language={language}"})
        assert response.status_code == 200, language
        match = region_re.search(response.text)
        assert match, f"{language}: no geo.region meta"
        assert match.group(1) == region, (
            f"{language}: expected geo.region={region}, got {match.group(1)}"
        )


def test_home_jsonld_inlanguage_matches_request_locale(test_client: TestClient):
    from i18n import SCHEMA_LANGUAGE_MAP, SUPPORTED_LANGUAGES

    pattern = re.compile(r'"inLanguage":\s*"([^"]+)"')

    for language in SUPPORTED_LANGUAGES:
        in_language = SCHEMA_LANGUAGE_MAP[language]
        response = test_client.get("/", headers={"Cookie": f"fsqr_language={language}"})
        assert response.status_code == 200, language
        matches = pattern.findall(response.text)
        assert matches, f"{language}: no JSON-LD inLanguage"
        assert all(m == in_language for m in matches), (
            f"{language}: expected inLanguage={in_language}, got {matches}"
        )


def test_arabic_renders_with_rtl_direction(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=ar"})
    assert response.status_code == 200
    assert re.search(r'<html[^>]*\blang="ar"[^>]*\bdir="rtl"', response.text), (
        'Arabic responses must include dir="rtl" on the <html> element'
    )


def test_home_hreflang_alternates_include_every_supported_language(
    test_client: TestClient,
):
    from i18n import SUPPORTED_LANGUAGES

    response = test_client.get("/")
    assert response.status_code == 200

    hreflangs = set(re.findall(r'rel="alternate"\s+hreflang="([^"]+)"', response.text))
    for language in SUPPORTED_LANGUAGES:
        assert language in hreflangs, f"missing hreflang alternate for {language}"
    assert "x-default" in hreflangs


def test_canonical_url_is_set_on_home(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://fs-qr.net/"' in response.text
    assert "http://127.0.0.1:5000/" not in response.text


def test_canonical_url_uses_public_https_origin(test_client: TestClient):
    response = test_client.get("/note")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://fs-qr.net/note"' in response.text
    assert "http://fs-qr.net/note" not in response.text


def test_social_card_images_use_public_https_urls(test_client: TestClient):
    routes = {
        "/": "fs-qr-og-compressed.jpg",
        "/fs-qr_menu": "fs-qr-og-compressed.jpg",
        "/group_menu": "fs-qr-og-compressed.jpg",
        "/note_menu": "fs-qr-og-compressed.jpg",
        "/safe-sharing": "articles/thumbnails/safe-sharing.jpg",
    }

    for route, image_path in routes.items():
        response = test_client.get(route)
        assert response.status_code == 200, route
        expected = f"https://fs-qr.net/static/{image_path}"
        assert f'<meta property="og:image" content="{expected}"' in response.text
        assert f'<meta name="twitter:image" content="{expected}"' in response.text
        assert f'content="/static/{image_path}' not in response.text


def _read_jpeg_size(path: str) -> tuple[int, int]:
    """JPEG の SOF マーカーから (width, height) を読み取る（標準ライブラリのみ）。"""
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:2] == b"\xff\xd8", f"not a JPEG: {path}"
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15 (フレーム開始) 以外で寸法を持たないマーカーは飛ばす
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        segment_length = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + segment_length
    raise AssertionError(f"no SOF marker found: {path}")


def test_social_card_images_have_x_compatible_aspect_ratio():
    """X(Twitter) summary_large_image は縦横比 1:1〜2:1 の画像でないと
    サムネイルを描画しない。共有カード画像がこの範囲に収まることを保証する。
    """
    import os

    from settings import BASE_DIR

    social_images = [
        "fs-qr-og-compressed.jpg",
    ]

    for name in social_images:
        path = os.path.join(BASE_DIR, "static", name)
        assert os.path.exists(path), f"missing social card image: {name}"
        width, height = _read_jpeg_size(path)
        assert width >= 300 and height >= 157, f"{name} too small: {width}x{height}"
        ratio = width / height
        assert 1.0 <= ratio <= 2.0, f"{name} aspect ratio {ratio:.2f} outside 1:1..2:1"


def _is_progressive_jpeg(path: str) -> bool:
    """JPEG が progressive (SOF2) かどうかを SOF マーカーから判定する。"""
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:2] == b"\xff\xd8", f"not a JPEG: {path}"
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0 (0xC0)=baseline, SOF2 (0xC2)=progressive。他の SOFn も含め寸法を持つ
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return marker == 0xC2
        segment_length = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + segment_length
    raise AssertionError(f"no SOF marker found: {path}")


def test_social_card_images_are_baseline_jpeg():
    """X(Twitter) のカードクローラーは progressive JPEG を描画しないため、
    共有カード画像が baseline JPEG であることを保証する。
    """
    import os

    from settings import BASE_DIR

    social_images = [
        "fs-qr-og-compressed.jpg",
    ]

    for name in social_images:
        path = os.path.join(BASE_DIR, "static", name)
        assert os.path.exists(path), f"missing social card image: {name}"
        assert not _is_progressive_jpeg(path), (
            f"{name} is a progressive JPEG; X(Twitter) does not render it"
        )
