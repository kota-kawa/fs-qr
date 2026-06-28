from typing import Any

from .catalog import get_translation_value, load_translations
from .constants import LANGUAGE_OPTIONS
from .language import normalize_language


def get_frontend_messages(language: str) -> dict[str, str]:
    translations = load_translations()
    normalized_language = normalize_language(language)
    messages = {}

    # 1. English as base if not current language
    if normalized_language != "en":
        messages.update(translations.get("en", {}).get("js", {}))

    # 2. Current language overrides
    messages.update(translations.get(normalized_language, {}).get("js", {}))

    return messages


def make_translator(language: str):
    normalized_language = normalize_language(language)

    def translate(key: str, **params: Any) -> str:
        value = get_translation_value(normalized_language, "ui", key)
        if params:
            try:
                return value.format(**params)
            except Exception:
                return value
        return value

    return translate


def get_language_options(language: str) -> tuple[dict[str, str], ...]:
    # 言語切り替えドロップダウンは、現在のUI言語に関わらず各言語を
    # その言語自身の名称（自称・endonym。例: English, 日本語, 한국어）で
    # 統一して表示する。こうすることで表示内容が言語ごとに変わらず、
    # 自分の言語を読めないユーザーでも自言語を見つけやすくなる。
    # `language` 引数は将来の利用（並び順など）のために残している。
    options: list[dict[str, str]] = []
    for option in LANGUAGE_OPTIONS:
        options.append(
            {
                "code": option["code"],
                "label": option["label"],
                "flag": option["flag"],
            }
        )
    return tuple(options)
