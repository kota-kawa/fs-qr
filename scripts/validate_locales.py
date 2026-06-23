#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES  # noqa: E402
from locale_store import (  # noqa: E402
    LOCALE_SECTIONS,
    load_locale_section,
    load_locale_section_shards,
    locale_dir_path,
)


LOCALES_DIR = REPO_ROOT / "locales"
BASE_LANGUAGE = "en"
STRICT_KEY_SECTIONS = ("ui", "js")
ARTICLE_PHRASE_SHARD_PREFIX = "articles/"
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
SCRIPT_PATTERNS = {
    "Japanese kana": re.compile(r"[\u3040-\u30ff]"),
    "CJK": re.compile(r"[\u3400-\u9fff]"),
    "Hangul": re.compile(r"[\u1100-\u11ff\uac00-\ud7af]"),
    "Thai": re.compile(r"[\u0e00-\u0e7f]"),
    "Arabic": re.compile(r"[\u0600-\u06ff]"),
    "Devanagari": re.compile(r"[\u0904-\u0939\u0958-\u0961\u0970-\u097f]"),
    "Bengali": re.compile(r"[\u0980-\u09ff]"),
    "Cyrillic": re.compile(r"[\u0400-\u04ff]"),
}
ALLOWED_SCRIPTS_BY_LANGUAGE = {
    "ja": {"Japanese kana", "CJK"},
    "zh-CN": {"CJK"},
    "zh-TW": {"CJK"},
    "ko": {"Hangul"},
    "th": {"Thai"},
    "ar": {"Arabic"},
    "hi": {"Devanagari"},
    "bn": {"Bengali"},
    "ru": {"Cyrillic"},
    "uk": {"Cyrillic"},
}
ALLOWED_STANDALONE_MULTILINGUAL_VALUES = {
    "日本語",
    "简体中文",
    "繁體中文",
    "한국어",
    "ไทย",
    "Українська",
    "Русский",
    "हिन्दी",
    "বাংলা",
    "العربية",
}


class LocaleReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def print(self) -> None:
        for message in self.errors:
            print(f"ERROR: {message}")
        for message in self.warnings:
            print(f"WARN: {message}")
        if not self.errors and not self.warnings:
            print("Locale validation passed.")
        elif not self.errors:
            print("Locale validation passed with warnings.")


def placeholders(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return set(PLACEHOLDER_RE.findall(value))


def validate_legacy_files(report: LocaleReport) -> None:
    legacy_files = sorted(LOCALES_DIR.glob("*.json"))
    for path in legacy_files:
        report.error(
            f"{path.relative_to(REPO_ROOT)} is a legacy monolithic locale file; "
            "use locales/<lang>/<section>.json instead"
        )


def validate_language_dirs(report: LocaleReport) -> None:
    for language in SUPPORTED_LANGUAGES:
        path = locale_dir_path(LOCALES_DIR, language)
        if not path.is_dir():
            report.error(f"missing locale directory {path.relative_to(REPO_ROOT)}")


def validate_section_objects(report: LocaleReport) -> None:
    for language in SUPPORTED_LANGUAGES:
        for section in LOCALE_SECTIONS:
            data = load_locale_section(LOCALES_DIR, language, section)
            if not isinstance(data, dict):
                report.error(f"{language}/{section} must be a JSON object")
                continue
            bad_keys = [key for key in data if not isinstance(key, str)]
            bad_values = [
                key for key, value in data.items() if not isinstance(value, str)
            ]
            if bad_keys:
                report.error(f"{language}/{section} has non-string keys")
            if bad_values:
                sample = ", ".join(str(key) for key in bad_values[:5])
                report.error(f"{language}/{section} has non-string values: {sample}")
            empty_values = [
                key
                for key, value in data.items()
                if isinstance(value, str) and not value
            ]
            if empty_values:
                sample = ", ".join(str(key) for key in empty_values[:5])
                report.error(f"{language}/{section} has empty values: {sample}")


def validate_strict_keys(report: LocaleReport) -> None:
    base_sections = {
        section: load_locale_section(LOCALES_DIR, BASE_LANGUAGE, section)
        for section in STRICT_KEY_SECTIONS
    }
    for language in SUPPORTED_LANGUAGES:
        for section, base in base_sections.items():
            current = load_locale_section(LOCALES_DIR, language, section)
            missing = sorted(set(base) - set(current))
            extra = sorted(set(current) - set(base))
            if missing:
                sample = ", ".join(missing[:8])
                report.error(
                    f"{language}/{section} missing {len(missing)} keys: {sample}"
                )
            if extra:
                sample = ", ".join(extra[:8])
                report.error(
                    f"{language}/{section} has {len(extra)} extra keys: {sample}"
                )


def validate_placeholders(report: LocaleReport) -> None:
    for section in STRICT_KEY_SECTIONS:
        base = load_locale_section(LOCALES_DIR, BASE_LANGUAGE, section)
        expected = {key: placeholders(value) for key, value in base.items()}
        for language in SUPPORTED_LANGUAGES:
            current = load_locale_section(LOCALES_DIR, language, section)
            for key, expected_placeholders in expected.items():
                if key not in current:
                    continue
                actual = placeholders(current[key])
                if actual != expected_placeholders:
                    report.error(
                        f"{language}/{section}/{key} placeholders "
                        f"{sorted(actual)} != {sorted(expected_placeholders)}"
                    )


def validate_locale_value_scripts(report: LocaleReport) -> None:
    for language in SUPPORTED_LANGUAGES:
        allowed_scripts = ALLOWED_SCRIPTS_BY_LANGUAGE.get(language, set())
        for section in LOCALE_SECTIONS:
            data = load_locale_section(LOCALES_DIR, language, section)
            for key, value in data.items():
                if not isinstance(value, str):
                    continue
                if value in ALLOWED_STANDALONE_MULTILINGUAL_VALUES:
                    continue
                for script_name, pattern in SCRIPT_PATTERNS.items():
                    if script_name in allowed_scripts:
                        continue
                    if pattern.search(value):
                        report.error(
                            f"{language}/{section}/{key} contains disallowed "
                            f"{script_name} characters: {value[:80]!r}"
                        )
                        break


def validate_phrase_shards(report: LocaleReport) -> None:
    base_shards = load_locale_section_shards(LOCALES_DIR, BASE_LANGUAGE, "phrases")
    for language in SUPPORTED_LANGUAGES:
        shards = load_locale_section_shards(LOCALES_DIR, language, "phrases")
        if not shards:
            report.warning(f"{language}/phrases has no entries")
            continue

        if "articles" in shards:
            report.error(
                f"{language}/phrases/articles.json is too broad; "
                "use phrases/articles/<slug>.json instead"
            )
        if not any(shard.startswith("articles/") for shard in shards):
            report.warning(f"{language}/phrases has no article-specific shards")

        missing_shards = sorted(set(base_shards) - set(shards))
        extra_shards = sorted(set(shards) - set(base_shards))
        if missing_shards:
            sample = ", ".join(missing_shards[:8])
            report.error(
                f"{language}/phrases missing {len(missing_shards)} shards: {sample}"
            )
        if extra_shards:
            sample = ", ".join(extra_shards[:8])
            report.error(
                f"{language}/phrases has {len(extra_shards)} extra shards: {sample}"
            )

        seen: dict[str, str] = {}
        for shard, data in shards.items():
            for key in data:
                if key in seen:
                    report.error(
                        f"{language}/phrases duplicates key in {seen[key]} and {shard}: "
                        f"{key[:80]!r}"
                    )
                seen[key] = shard

        if language in (BASE_LANGUAGE, DEFAULT_LANGUAGE):
            continue
        for shard, base_data in base_shards.items():
            if not shard.startswith(ARTICLE_PHRASE_SHARD_PREFIX):
                continue
            current = shards.get(shard, {})
            missing_keys = sorted(set(base_data) - set(current))
            extra_keys = sorted(set(current) - set(base_data))
            if missing_keys:
                sample = ", ".join(key[:60] for key in missing_keys[:5])
                report.error(
                    f"{language}/phrases/{shard} missing {len(missing_keys)} keys: "
                    f"{sample}"
                )
            if extra_keys:
                sample = ", ".join(key[:60] for key in extra_keys[:5])
                report.error(
                    f"{language}/phrases/{shard} has {len(extra_keys)} extra keys: "
                    f"{sample}"
                )


def validate_phrase_placeholders(report: LocaleReport) -> None:
    base = load_locale_section(LOCALES_DIR, BASE_LANGUAGE, "phrases")
    expected = {key: placeholders(value) for key, value in base.items()}
    for language in SUPPORTED_LANGUAGES:
        if language in (BASE_LANGUAGE, DEFAULT_LANGUAGE):
            continue
        current = load_locale_section(LOCALES_DIR, language, "phrases")
        for key, expected_placeholders in expected.items():
            if key not in current:
                continue
            actual = placeholders(current[key])
            if actual != expected_placeholders:
                report.error(
                    f"{language}/phrases/{key} placeholders "
                    f"{sorted(actual)} != {sorted(expected_placeholders)}"
                )


def validate_phrase_drift(report: LocaleReport, strict: bool) -> None:
    base = load_locale_section(LOCALES_DIR, BASE_LANGUAGE, "phrases")
    base_keys = set(base)
    for language in SUPPORTED_LANGUAGES:
        if language in (BASE_LANGUAGE, DEFAULT_LANGUAGE):
            continue
        current = load_locale_section(LOCALES_DIR, language, "phrases")
        missing = len(base_keys - set(current))
        extra = len(set(current) - base_keys)
        if not missing and not extra:
            continue
        message = f"{language}/phrases differs from {BASE_LANGUAGE}: missing={missing}, extra={extra}"
        if strict:
            report.error(message)
        else:
            report.warning(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate split locale catalogs.")
    parser.add_argument(
        "--strict-phrases",
        action="store_true",
        help="fail when phrase keys drift from the English catalog",
    )
    args = parser.parse_args()

    report = LocaleReport()
    validate_legacy_files(report)
    validate_language_dirs(report)
    validate_section_objects(report)
    validate_strict_keys(report)
    validate_placeholders(report)
    validate_locale_value_scripts(report)
    validate_phrase_shards(report)
    validate_phrase_placeholders(report)
    validate_phrase_drift(report, strict=args.strict_phrases)
    report.print()
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
