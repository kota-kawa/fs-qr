#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from article_locale_shards import (  # noqa: E402
    ARTICLE_SHARED_SHARD,
    article_phrase_shard_for_key,
)
from locale_store import save_locale_section, save_locale_section_shard  # noqa: E402


LOCALES_DIR = REPO_ROOT / "locales"
APP_SOURCE_ROOTS = (
    REPO_ROOT / "Articles",
    REPO_ROOT / "FSQR",
    REPO_ROOT / "Group",
    REPO_ROOT / "Note",
    REPO_ROOT / "templates",
)
SOURCE_SUFFIXES = {".html", ".py", ".js"}
PUBLIC_PAGE_TEMPLATES = {
    "about.html",
    "contact.html",
    "privacy.html",
    "site_operator.html",
    "terms.html",
    "usage.html",
}


def read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def discover_source_files() -> list[Path]:
    files: list[Path] = []
    for root in APP_SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files.append(path)
    return sorted(files)


def build_phrase_index(source_files: list[Path]) -> list[tuple[Path, str]]:
    indexed: list[tuple[Path, str]] = []
    for path in source_files:
        try:
            indexed.append((path, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return indexed


def classify_phrase(source: str, indexed_sources: list[tuple[Path, str]]) -> str:
    matches = [path for path, text in indexed_sources if source and source in text]
    if not matches:
        return "legacy"

    if any("Articles" in path.parts for path in matches):
        return article_phrase_shard_for_key(source) or ARTICLE_SHARED_SHARD

    if any(path.name in PUBLIC_PAGE_TEMPLATES for path in matches):
        return "pages"

    if any(path.suffix == ".html" and "templates" in path.parts for path in matches):
        return "product"

    return "product"


def split_phrase_shards(
    phrases: dict[str, Any], indexed_sources: list[tuple[Path, str]]
) -> dict[str, dict[str, Any]]:
    shards: dict[str, dict[str, Any]] = defaultdict(dict)
    for key, value in phrases.items():
        shard = classify_phrase(key, indexed_sources)
        shards[shard][key] = value
    return dict(sorted(shards.items()))


def migrate_locale(
    path: Path, indexed_sources: list[tuple[Path, str]], apply: bool
) -> None:
    language = path.stem
    data = read_json_object(path)

    ui = data.get("ui", {})
    js = data.get("js", {})
    phrases = data.get("phrases", {})
    if (
        not isinstance(ui, dict)
        or not isinstance(js, dict)
        or not isinstance(phrases, dict)
    ):
        raise ValueError(f"{path} has invalid section data")

    phrase_shards = split_phrase_shards(phrases, indexed_sources)
    shard_summary = ", ".join(
        f"{name}={len(values)}" for name, values in sorted(phrase_shards.items())
    )
    print(f"{language}: ui={len(ui)} js={len(js)} phrases({shard_summary})")

    if not apply:
        return

    save_locale_section(LOCALES_DIR, language, "ui", ui)
    save_locale_section(LOCALES_DIR, language, "js", js)
    for shard, values in phrase_shards.items():
        save_locale_section_shard(LOCALES_DIR, language, "phrases", shard, values)


def remove_legacy_files(locale_files: list[Path], apply: bool) -> None:
    for path in locale_files:
        print(f"remove legacy {path.relative_to(REPO_ROOT)}")
        if apply:
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split locales/<lang>.json into locales/<lang>/<section>.json files."
    )
    parser.add_argument("--apply", action="store_true", help="write split locale files")
    parser.add_argument(
        "--remove-legacy",
        action="store_true",
        help="delete locales/<lang>.json after split files are written",
    )
    args = parser.parse_args()

    locale_files = sorted(
        path for path in LOCALES_DIR.glob("*.json") if path.name != "manifest.json"
    )
    if not locale_files:
        print("No legacy locale files found.")
        return

    indexed_sources = build_phrase_index(discover_source_files())
    for path in locale_files:
        migrate_locale(path, indexed_sources, apply=args.apply)

    if args.remove_legacy:
        if not args.apply:
            print("--remove-legacy requires --apply; dry-run only")
            return
        remove_legacy_files(locale_files, apply=True)


if __name__ == "__main__":
    main()
