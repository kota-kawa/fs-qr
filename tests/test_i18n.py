from pathlib import Path
from types import SimpleNamespace


class DummyRequest:
    def __init__(
        self, cookies=None, headers=None, client_host="8.8.8.8", query_params=None
    ):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = SimpleNamespace(host=client_host)
        self.query_params = query_params or DummyQueryParams([])


class DummyQueryParams:
    def __init__(self, items):
        self._items = list(items)

    def __len__(self):
        return len(self._items)

    def get(self, key, default=None):
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        return default

    def multi_items(self):
        return list(self._items)


class DummyGeoIPReader:
    def __init__(self, country_code):
        self.country_code = country_code

    def get(self, ip_address):
        return {"country": {"iso_code": self.country_code}}


class DummyFlatGeoIPReader:
    def __init__(self, country_code):
        self.country_code = country_code

    def get(self, ip_address):
        return {"country_code": self.country_code}


def test_language_from_country_maps_japan_to_japanese():
    from i18n import language_from_country

    assert language_from_country("JP") == "ja"


def test_language_from_country_maps_other_country_to_english():
    from i18n import language_from_country

    assert language_from_country("US") == "en"


def test_language_from_country_maps_china_to_simplified_chinese():
    from i18n import language_from_country

    assert language_from_country("CN") == "zh-CN"


def test_language_from_country_maps_taiwan_to_traditional_chinese():
    from i18n import language_from_country

    assert language_from_country("TW") == "zh-TW"


def test_language_from_country_maps_korea_to_korean():
    from i18n import language_from_country

    assert language_from_country("KR") == "ko"


def test_language_from_country_maps_turkey_to_turkish():
    from i18n import language_from_country

    assert language_from_country("TR") == "tr"


def test_language_from_country_maps_ukraine_to_ukrainian():
    from i18n import language_from_country

    assert language_from_country("UA") == "uk"


def test_language_from_country_maps_poland_to_polish():
    from i18n import language_from_country

    assert language_from_country("PL") == "pl"


def test_language_from_country_maps_tanzania_to_swahili():
    from i18n import language_from_country

    assert language_from_country("TZ") == "sw"


def test_language_from_country_maps_saudi_arabia_to_arabic():
    from i18n import language_from_country

    assert language_from_country("SA") == "ar"


def test_resolve_language_prefers_cookie_over_geoip(monkeypatch):
    import i18n

    monkeypatch.setattr(i18n, "_get_geoip_reader", lambda: DummyGeoIPReader("US"))

    request = DummyRequest(cookies={"fsqr_language": "ja"}, client_host="8.8.8.8")

    assert i18n.resolve_language(request) == "ja"


def test_resolve_language_uses_geoip_when_cookie_missing(monkeypatch):
    import i18n

    monkeypatch.setattr(i18n, "_get_geoip_reader", lambda: DummyGeoIPReader("US"))

    request = DummyRequest(client_host="8.8.8.8")

    assert i18n.resolve_language(request) == "en"


def test_resolve_language_supports_flat_country_code_schema(monkeypatch):
    import i18n

    monkeypatch.setattr(i18n, "_get_geoip_reader", lambda: DummyFlatGeoIPReader("CN"))

    request = DummyRequest(client_host="8.8.8.8")

    assert i18n.resolve_language(request) == "zh-CN"


def test_resolve_language_falls_back_to_japanese_without_geoip(monkeypatch):
    import i18n

    monkeypatch.setattr(i18n, "_get_geoip_reader", lambda: None)

    request = DummyRequest(client_host="8.8.8.8")

    assert i18n.resolve_language(request) == "ja"


def test_resolve_language_falls_back_to_japanese_for_private_ip(monkeypatch):
    import i18n

    monkeypatch.setattr(i18n, "_get_geoip_reader", lambda: DummyGeoIPReader("US"))

    request = DummyRequest(client_host="127.0.0.1")

    assert i18n.resolve_language(request) == "ja"


def test_translate_rendered_html_updates_language_metadata():
    from i18n import translate_rendered_html

    content = (
        '<html lang="ja"><head>'
        '<meta name="language" content="ja">'
        '<meta property="og:locale" content="ja_JP">'
        '<script>{"inLanguage": "ja-JP"}</script>'
        "</head><body>ホーム</body></html>"
    )

    # Test English (LTR)
    translated_en = translate_rendered_html(content, "en")
    assert '<html lang="en" dir="ltr">' in translated_en
    assert '<meta name="language" content="en">' in translated_en
    assert '<meta property="og:locale" content="en_US">' in translated_en
    assert '"inLanguage": "en"' in translated_en
    assert "Home" in translated_en

    # Test Arabic (RTL)
    translated_ar = translate_rendered_html(content, "ar")
    assert '<html lang="ar" dir="rtl">' in translated_ar
    assert '<meta name="language" content="ar">' in translated_ar
    assert '<meta property="og:locale" content="ar_SA">' in translated_ar
    assert '"inLanguage": "ar"' in translated_ar
    assert "الرئيسية" in translated_ar


def test_language_query_only_accepts_supported_language_aliases():
    import i18n

    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "en")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "zh-cn")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "zh-tw")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "ko")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "fr")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "es")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "de-DE")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "vi-VN")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "th-TH")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "id-ID")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "tr")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "uk")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "pl")]))
    )
    assert not i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "xyz")]))
    )
    assert not i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "en"), ("page", "1")]))
    )


def test_cookie_consent_script_uses_rendered_supported_language_list():
    source = Path("static/cookie-consent.js").read_text(encoding="utf-8")

    assert "supportedLanguages" in source
    assert "['ja', 'en', 'zh-CN', 'zh-TW', 'ko']" not in source


def test_language_options_never_expose_translation_keys():
    import i18n

    for language in i18n.SUPPORTED_LANGUAGES:
        options = i18n.get_language_options(language)
        assert len(options) == len(i18n.SUPPORTED_LANGUAGES)
        for option in options:
            assert not option["label"].startswith("language.option.")


def test_language_options_fallback_to_native_labels_when_missing_translation():
    import i18n

    labels = {
        option["code"]: option["label"] for option in i18n.get_language_options("ja")
    }

    assert labels["vi"] == "Tiếng Việt"
    assert labels["th"] == "ไทย"


def test_language_dropdown_is_scrollable_for_many_languages():
    source = Path("static/cookie-consent.css").read_text(encoding="utf-8")
    script = Path("static/cookie-consent.js").read_text(encoding="utf-8")

    assert ".lang-select-list" in source
    assert "max-height:" in source
    assert "overflow-y: auto" in source
    assert "z-index: 1110" in source
    assert "z-index: calc(var(--z-modal, 1100) + 10)" in source
    assert "body > .lang-select-list.lang-select-list" in source
    assert "closeOpenLangSelects" in script
    # 言語選択は summary / settings 両ビューともドロップダウン方式
    assert ".lang-select-trigger" in source
    assert ".lang-select-option" in source


def test_non_default_frontend_messages_do_not_fallback_to_japanese():
    import i18n

    messages = i18n.get_frontend_messages("en")

    assert messages["alert.notice"] == "Notice"
    assert messages.get("missing.key") is None
    assert "お知らせ" not in messages.values()


def test_normalize_language_supports_new_aliases():
    import i18n

    assert i18n.normalize_language("zh-tw") == "zh-TW"
    assert i18n.normalize_language("zh_hant") == "zh-TW"
    assert i18n.normalize_language("kr") == "ko"
