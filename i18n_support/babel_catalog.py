"""Babel-backed server-side translation catalogs.

The browser still receives the small ``js.json`` catalog.  HTML and server
messages use gettext catalogs instead, so Jinja translates values while it is
rendering the template rather than rewriting the completed document.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Callable

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from babel.support import Translations

from settings import BASE_DIR

from .constants import DEFAULT_LANGUAGE, LANGUAGE_FALLBACKS, SUPPORTED_LANGUAGES
from .language import normalize_language

_BABEL_LOCALE_NAMES = {
    "zh-CN": "zh_CN",
    "zh-TW": "zh_TW",
}


def _po_path(language: str) -> Path:
    return Path(BASE_DIR) / "locales" / language / "LC_MESSAGES" / "messages.po"


def _load_catalog(language: str) -> Translations:
    """Load one PO catalog through Babel's normal PO -> MO reader path."""

    path = _po_path(language)
    if not path.is_file():
        return Translations()

    with path.open("rb") as source:
        catalog = read_po(source, locale=_BABEL_LOCALE_NAMES.get(language, language))

    compiled = BytesIO()
    write_mo(compiled, catalog)
    compiled.seek(0)
    return Translations(compiled, domain="messages")


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def get_translations(language: str) -> Translations:
    """Return a catalog with the project's explicit language fallbacks."""

    normalized = normalize_language(language)
    translations = _load_catalog(normalized)

    for fallback in LANGUAGE_FALLBACKS.get(normalized, ()):
        translations.add_fallback(_load_catalog(fallback))
    if normalized != DEFAULT_LANGUAGE:
        translations.add_fallback(_load_catalog(DEFAULT_LANGUAGE))
    return translations


def get_translator(language: str) -> Callable[[str], str]:
    """Return a gettext callable suitable for Jinja or application messages."""

    translations = get_translations(language)
    return translations.gettext


def get_plural_translator(language: str) -> Callable[[str, str, int], str]:
    """Return Babel's plural gettext callable for Jinja's ``ngettext``."""

    translations = get_translations(language)
    return translations.ngettext


def clear_catalog_cache() -> None:
    """Clear cached catalogs after tests or a catalog deployment."""

    get_translations.cache_clear()
