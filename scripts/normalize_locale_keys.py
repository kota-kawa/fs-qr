"""Normalize locale phrase keys so they match the actual Japanese template strings.

Some locale files (notably tr, uk, pl, sw, ar, ko, zh-TW, plus parts of fr, es, de, vi, th, id)
contain phrase keys that use ASCII punctuation (".", ",") or stray whitespace where the
template uses Japanese punctuation ("。", "、"). The English phrase catalog is treated
as the canonical source of truth for keys.

For each language file:
  * For each phrase key K that does NOT exist in the English phrases:
      - normalize K (strip whitespace and unify punctuation)
      - look for a normalized en.json key that matches
      - if exactly one match is found, rename K → canonical en key (preserving value)
  * Any keys that cannot be matched are reported and left untouched.
"""

from __future__ import annotations

import difflib
import re
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from locale_store import (  # noqa: E402
    load_locale_section,
    load_locale_section_shards,
    save_locale_section_shard,
)


LOCALES_DIR = REPO_ROOT / "locales"
TARGET_LANGS = (
    "zh-CN",
    "zh-TW",
    "ko",
    "fr",
    "es",
    "de",
    "pt",
    "it",
    "vi",
    "th",
    "id",
    "tr",
    "uk",
    "ru",
    "nl",
    "hi",
    "bn",
    "pl",
    "sw",
    "ar",
)


def normalize_for_match(s: str) -> str:
    """Loose key normalization for matching.

    Rationale: keys can differ from en.json only in punctuation (ASCII "." vs "。" / ","
    vs "、") and whitespace artifacts. Collapsing both eliminates those differences while
    leaving the semantic content intact for comparison.
    """
    # Map ASCII punctuation to Japanese equivalents when appearing in Japanese text.
    s = s.replace(".", "。").replace(",", "、")
    # Remove all whitespace (ASCII space, full-width space, tabs, newlines).
    s = re.sub(r"[\s　]+", "", s)
    return s


def build_canonical_index(en_phrases: dict) -> dict:
    """Map normalized key form → list of canonical keys (usually len 1)."""
    index: dict[str, list[str]] = defaultdict(list)
    for k in en_phrases.keys():
        index[normalize_for_match(k)].append(k)
    return index


def fuzzy_match(
    key: str, en_keys_normalized: list[tuple[str, str]], threshold: float = 0.88
) -> str | None:
    """Return the canonical en key whose normalized form has highest ratio above threshold."""
    nk = normalize_for_match(key)
    best_ratio = 0.0
    best_canonical: str | None = None
    for nk_en, canonical in en_keys_normalized:
        # Quick length filter to avoid expensive comparisons.
        if abs(len(nk) - len(nk_en)) > max(40, int(len(nk) * 0.25)):
            continue
        ratio = difflib.SequenceMatcher(None, nk, nk_en).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_canonical = canonical
    if best_ratio >= threshold:
        return best_canonical
    return None


def add_if_unseen(
    target: dict[str, str], seen_keys: set[str], key: str, value: str
) -> bool:
    if key in seen_keys:
        return False
    target[key] = value
    seen_keys.add(key)
    return True


def normalize_phrase_key(
    key: str,
    value: str,
    new_phrases: dict[str, str],
    seen_keys: set[str],
    canonical_index: dict[str, list[str]],
    en_keys: set[str],
    en_keys_normalized: list[tuple[str, str]],
) -> tuple[str, str | list[str] | None]:
    if key in en_keys:
        add_if_unseen(new_phrases, seen_keys, key, value)
        return "unchanged", None

    candidates = canonical_index.get(normalize_for_match(key), [])
    if len(candidates) == 1:
        canonical = candidates[0]
        if add_if_unseen(new_phrases, seen_keys, canonical, value):
            return "renamed", canonical
        return "duplicate", canonical

    if len(candidates) > 1:
        add_if_unseen(new_phrases, seen_keys, key, value)
        return "ambiguous", candidates

    fuzzy = fuzzy_match(key, en_keys_normalized)
    if fuzzy and add_if_unseen(new_phrases, seen_keys, fuzzy, value):
        return "fuzzy", fuzzy

    add_if_unseen(new_phrases, seen_keys, key, value)
    return "unmatched", None


def normalize_locale(
    lang: str,
    canonical_index: dict,
    en_keys: set,
    en_keys_normalized: list[tuple[str, str]],
    dry_run: bool = False,
):
    phrase_shards = load_locale_section_shards(LOCALES_DIR, lang, "phrases")
    if not phrase_shards:
        print(f"[{lang}] no phrases section, skipping")
        return

    renamed: list[tuple[str, str]] = []
    fuzzy_renamed: list[tuple[str, str]] = []
    unmatched: list[str] = []
    ambiguous: list[tuple[str, list[str]]] = []
    seen_keys: set[str] = set()
    new_shards: dict[str, dict[str, str]] = {}

    for shard, phrases in phrase_shards.items():
        new_phrases: dict[str, str] = {}
        for key, value in phrases.items():
            status, detail = normalize_phrase_key(
                key,
                value,
                new_phrases,
                seen_keys,
                canonical_index,
                en_keys,
                en_keys_normalized,
            )
            if status == "renamed" and isinstance(detail, str):
                renamed.append((key, detail))
            elif status == "fuzzy" and isinstance(detail, str):
                fuzzy_renamed.append((key, detail))
            elif status == "ambiguous" and isinstance(detail, list):
                ambiguous.append((key, detail))
            elif status == "unmatched":
                unmatched.append(key)
        new_shards[shard] = new_phrases

    if not dry_run:
        for shard, phrases in new_shards.items():
            save_locale_section_shard(LOCALES_DIR, lang, "phrases", shard, phrases)

    total = len(renamed) + len(fuzzy_renamed)
    print(
        f"[{lang}] renamed={len(renamed)}, fuzzy={len(fuzzy_renamed)}, "
        f"total={total}, unmatched={len(unmatched)}, ambiguous={len(ambiguous)}"
    )
    for key, canonical in fuzzy_renamed[:5]:
        print(f"  FUZZY: {key[:55]!r}\n     -> {canonical[:55]!r}")
    for key, candidates in ambiguous[:5]:
        print(f"  AMBIG: {key[:60]!r} → {[c[:40] for c in candidates]}")
    for key in unmatched[:8]:
        print(f"  UNMATCH: {key[:80]!r}")


def main():
    dry_run = "--apply" not in sys.argv
    en_phrases = load_locale_section(LOCALES_DIR, "en", "phrases")
    en_keys = set(en_phrases.keys())
    canonical_index = build_canonical_index(en_phrases)
    en_keys_normalized = [(normalize_for_match(k), k) for k in en_keys]

    print(f"English phrase count: {len(en_keys)}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print()

    for lang in TARGET_LANGS:
        normalize_locale(
            lang,
            canonical_index,
            en_keys,
            en_keys_normalized,
            dry_run=dry_run,
        )


if __name__ == "__main__":
    main()
