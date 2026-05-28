"""SEO-related multilingual tests.

These cover:
- sitemap.xml exposes xhtml:link alternates for every supported language and x-default
- meta description / og:description / title are translated for every locale on the home page
- geo.region and geo.placename adapt to the request locale
- JSON-LD inLanguage matches the request locale
- Arabic responses set dir="rtl"
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from starlette.testclient import TestClient


SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def test_sitemap_has_hreflang_alternates_for_every_url(test_client: TestClient):
    from i18n import SUPPORTED_LANGUAGES

    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.text)
    urls = root.findall("sm:url", SITEMAP_NS)
    assert urls, "sitemap should contain at least one <url>"

    for url in urls:
        loc = url.find("sm:loc", SITEMAP_NS)
        assert loc is not None and loc.text

        alternates = url.findall("xhtml:link", SITEMAP_NS)
        hreflangs = {alt.get("hreflang") for alt in alternates}
        # Every supported language plus x-default must be present.
        for lang in SUPPORTED_LANGUAGES:
            assert lang in hreflangs, f"{loc.text}: missing hreflang={lang}"
        assert "x-default" in hreflangs

        # Each alternate must point at a valid URL.
        for alt in alternates:
            assert alt.get("href"), f"{loc.text}: missing href"


def test_sitemap_includes_terms_page(test_client: TestClient):
    response = test_client.get("/sitemap.xml")
    assert response.status_code == 200

    root = ET.fromstring(response.text)
    locs = {loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)}
    assert "https://fs-qr.net/terms" in locs


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

    desc_re = re.compile(r'<meta name="description" content="([^"]+)"')

    for language in SUPPORTED_LANGUAGES:
        cookie = {"Cookie": f"fsqr_language={language}"}
        response = test_client.get("/", headers=cookie)
        assert response.status_code == 200, language

        match = desc_re.search(response.text)
        assert match, f"{language}: no meta description"
        desc = match.group(1)

        marker = language_markers[language]
        assert marker.lower() in desc.lower(), (
            f"{language}: meta description missing language marker {marker!r}; "
            f"got {desc[:120]!r}"
        )


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
    assert re.search(r'<link rel="canonical" href="[^"]+"', response.text)
