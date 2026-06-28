import logging
import os
from functools import lru_cache

from locale_store import load_language_translations
from settings import BASE_DIR

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
    translations = load_translations()
    normalized_language = normalize_language(language)

    # 1. Try specified language
    value = translations.get(normalized_language, {}).get(section, {}).get(key)
    if value:
        return value

    # 2. Try fallbacks
    fallbacks = LANGUAGE_FALLBACKS.get(normalized_language, ())
    for fallback in fallbacks:
        value = translations.get(fallback, {}).get(section, {}).get(key)
        if value:
            return value

    # 3. Try English if not already tried
    if normalized_language != "en" and "en" not in fallbacks:
        value = translations.get("en", {}).get(section, {}).get(key)
        if value:
            return value

    # 4. Try Japanese if not already tried
    if normalized_language != "ja" and "ja" not in fallbacks:
        value = translations.get("ja", {}).get(section, {}).get(key)
        if value:
            return value

    return key


def get_phrase_translation(language: str, source: str) -> str | None:
    translations = load_translations()
    normalized_language = normalize_language(language)

    language_phrases = translations.get(normalized_language, {}).get("phrases", {})
    if isinstance(language_phrases, dict):
        value = language_phrases.get(source)
        if isinstance(value, str) and value:
            return value

    fallbacks = LANGUAGE_FALLBACKS.get(normalized_language, ())
    for fallback in fallbacks:
        fallback_phrases = translations.get(fallback, {}).get("phrases", {})
        if isinstance(fallback_phrases, dict):
            value = fallback_phrases.get(source)
            if isinstance(value, str) and value:
                return value

    if normalized_language != "en" and "en" not in fallbacks:
        english_phrases = translations.get("en", {}).get("phrases", {})
        if isinstance(english_phrases, dict):
            value = english_phrases.get(source)
            if isinstance(value, str) and value:
                return value

    return None
