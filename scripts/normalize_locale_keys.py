"""Normalize locale phrase keys so they match the actual Japanese template strings.

Some locale files (notably tr, uk, pl, sw, ar, ko, zh-TW, plus parts of fr, es, de, vi, th, id)
contain phrase keys that use ASCII punctuation (".", ",") or stray whitespace where the
template uses Japanese punctuation ("。", "、"). en.json is treated as the canonical source
of truth for keys.

For each language file:
  * For each phrase key K that does NOT exist in en.json's phrases:
      - normalize K (strip whitespace and unify punctuation)
      - look for a normalized en.json key that matches
      - if exactly one match is found, rename K → canonical en key (preserving value)
  * Any keys that cannot be matched are reported and left untouched.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
from collections import defaultdict


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES_DIR = os.path.join(REPO_ROOT, "locales")
TARGET_LANGS = (
    "tr",
    "uk",
    "pl",
    "sw",
    "ar",
    "ko",
    "zh-TW",
    "fr",
    "es",
    "de",
    "vi",
    "th",
    "id",
    "zh-CN",
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


def load_locale(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_locale(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def build_canonical_index(en_phrases: dict) -> dict:
    """Map normalized key form → list of canonical keys (usually len 1)."""
    index: dict[str, list[str]] = defaultdict(list)
    for k in en_phrases.keys():
        index[normalize_for_match(k)].append(k)
    return index


def fuzzy_match(key: str, en_keys_normalized: list[tuple[str, str]], threshold: float = 0.88) -> str | None:
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


def normalize_locale(
    lang: str,
    canonical_index: dict,
    en_keys: set,
    en_keys_normalized: list[tuple[str, str]],
    dry_run: bool = False,
):
    path = os.path.join(LOCALES_DIR, f"{lang}.json")
    data = load_locale(path)
    phrases = data.get("phrases")
    if not isinstance(phrases, dict):
        print(f"[{lang}] no phrases section, skipping")
        return

    renamed: list[tuple[str, str]] = []
    fuzzy_renamed: list[tuple[str, str]] = []
    unmatched: list[str] = []
    ambiguous: list[tuple[str, list[str]]] = []
    new_phrases: dict[str, str] = {}

    for key, value in phrases.items():
        if key in en_keys:
            new_phrases.setdefault(key, value)
            continue
        nk = normalize_for_match(key)
        candidates = canonical_index.get(nk, [])
        if len(candidates) == 1:
            canonical = candidates[0]
            if canonical in new_phrases:
                continue
            new_phrases[canonical] = value
            renamed.append((key, canonical))
            continue
        if len(candidates) > 1:
            ambiguous.append((key, candidates))
            new_phrases[key] = value
            continue
        # Try fuzzy matching for corrupted keys (foreign chars mixed in).
        fuzzy = fuzzy_match(key, en_keys_normalized)
        if fuzzy and fuzzy not in new_phrases:
            new_phrases[fuzzy] = value
            fuzzy_renamed.append((key, fuzzy))
        else:
            unmatched.append(key)
            new_phrases[key] = value

    if not dry_run:
        data["phrases"] = new_phrases
        save_locale(path, data)

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
    en = load_locale(os.path.join(LOCALES_DIR, "en.json"))
    en_keys = set(en["phrases"].keys())
    canonical_index = build_canonical_index(en["phrases"])
    en_keys_normalized = [(normalize_for_match(k), k) for k in en_keys]

    print(f"en.json phrase count: {len(en_keys)}")
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
