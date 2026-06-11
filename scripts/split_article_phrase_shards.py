#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from article_locale_shards import ARTICLE_SHARED_SHARD, article_phrase_shard_for_key  # noqa: E402
from i18n import SUPPORTED_LANGUAGES  # noqa: E402
from locale_store import (  # noqa: E402
    load_locale_section_shards,
    save_locale_section_shard,
    section_shard_path,
)


LOCALES_DIR = REPO_ROOT / "locales"
HIGH_PRIORITY_SOURCE_SHARDS = {"quality_fill"}


def split_language(language: str, apply: bool) -> tuple[int, int]:
    shards = load_locale_section_shards(LOCALES_DIR, language, "phrases")
    updated = {shard: dict(values) for shard, values in shards.items()}
    moved = 0
    target_count = 0

    for shard, values in list(shards.items()):
        for key, value in values.items():
            target_shard = article_phrase_shard_for_key(key)
            if not target_shard:
                continue
            if shard == target_shard:
                continue

            updated.setdefault(shard, {}).pop(key, None)
            target = updated.setdefault(target_shard, {})
            if key not in target or shard in HIGH_PRIORITY_SOURCE_SHARDS:
                target[key] = value
            moved += 1

    article_shards = sorted(shard for shard in updated if shard.startswith("articles/"))
    target_count = len(article_shards)

    if apply:
        all_shards = set(shards) | set(updated)
        for shard in sorted(all_shards):
            values = updated.get(shard, {})
            path = section_shard_path(LOCALES_DIR, language, "phrases", shard)
            if values:
                save_locale_section_shard(
                    LOCALES_DIR, language, "phrases", shard, values
                )
            elif path.exists():
                path.unlink()

    return moved, target_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move article phrase translations into locales/<lang>/phrases/articles/<slug>.json."
    )
    parser.add_argument(
        "--apply", action="store_true", help="write split article shards"
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")
    print(f"Shared article shard: {ARTICLE_SHARED_SHARD}")

    for language in SUPPORTED_LANGUAGES:
        moved, target_count = split_language(language, apply=args.apply)
        print(f"{language}: moved={moved} article_shards={target_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
