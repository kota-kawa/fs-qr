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

    translated = translate_rendered_html(content, "en")

    assert '<html lang="en">' in translated
    assert '<meta name="language" content="en">' in translated
    assert '<meta property="og:locale" content="en_US">' in translated
    assert '"inLanguage": "en"' in translated
    assert "Home" in translated


def test_language_query_only_accepts_supported_language_aliases():
    import i18n

    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "en")]))
    )
    assert i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "zh-cn")]))
    )
    assert not i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "fr")]))
    )
    assert not i18n.is_language_query_only(
        DummyRequest(query_params=DummyQueryParams([("lang", "en"), ("page", "1")]))
    )


def test_non_default_frontend_messages_do_not_fallback_to_japanese():
    import i18n

    messages = i18n.get_frontend_messages("en")

    assert messages["alert.notice"] == "Notice"
    assert messages.get("missing.key") is None
    assert "お知らせ" not in messages.values()
