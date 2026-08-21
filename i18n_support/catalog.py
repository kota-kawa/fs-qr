import logging
import os
from functools import lru_cache

from locale_store import load_language_translations
from settings import BASE_DIR

from .babel_catalog import get_translations
from .constants import LANGUAGE_FALLBACKS, SUPPORTED_LANGUAGES
from .language import normalize_language

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_translations():
    locales_dir = os.path.join(BASE_DIR, "locales")
    translations = {}
    for lang in SUPPORTED_LANGUAGES:
        try:
            translations[lang] = load_language_translations(locales_dir, lang)
        except Exception as e:
            logger.error("Error loading translation for %s: %s", lang, e)
            translations[lang] = {}
    return translations


def get_translation_value(language: str, section: str, key: str) -> str:
    if section in {"ui", "phrases"}:
        return get_translations(language).gettext(key)

    # JS catalogs remain JSON because they are serialized into the browser.
    translations = load_translations()
    normalized_language = normalize_language(language)
    value = translations.get(normalized_language, {}).get(section, {}).get(key)
    if value:
        return value

    for fallback in LANGUAGE_FALLBACKS.get(normalized_language, ()):
        value = translations.get(fallback, {}).get(section, {}).get(key)
        if value:
            return value

    if normalized_language != "en":
        value = translations.get("en", {}).get(section, {}).get(key)
        if value:
            return value

    if normalized_language != "ja":
        value = translations.get("ja", {}).get(section, {}).get(key)
        if value:
            return value

    return key


def get_phrase_translation(language: str, source: str) -> str | None:
    translated = get_translations(language).gettext(source)
    return translated if translated != source else None
