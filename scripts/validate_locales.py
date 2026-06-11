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
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


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


def validate_phrase_shards(report: LocaleReport) -> None:
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

        seen: dict[str, str] = {}
        for shard, data in shards.items():
            for key in data:
                if key in seen:
                    report.error(
                        f"{language}/phrases duplicates key in {seen[key]} and {shard}: "
                        f"{key[:80]!r}"
                    )
                seen[key] = shard


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
    validate_phrase_shards(report)
    validate_phrase_drift(report, strict=args.strict_phrases)
    report.print()
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
