#!/usr/bin/env python3
"""Generate Babel PO catalogs from the maintained locale JSON catalogs.

``ui.json`` uses stable keys while ``phrases`` contains legacy/source strings
that are now called explicitly from Jinja.  Both are valid gettext message
IDs, so this script preserves the existing translations while moving runtime
rendering to Babel/Jinja.
"""

from __future__ import annotations

import argparse
import ast
import re
from datetime import datetime, timezone
from functools import lru_cache
import sys
from io import BytesIO
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from i18n_support.constants import SUPPORTED_LANGUAGES  # noqa: E402
from locale_store import load_language_translations  # noqa: E402

LOCALES_DIR = REPO_ROOT / "locales"
LOCALE_NAMES = {"zh-CN": "zh_CN", "zh-TW": "zh_TW"}
BRACE_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
PERCENT_RE = re.compile(r"%(?!\([A-Za-z_][A-Za-z0-9_]*\)s)")
GENERATED_BY_RE = re.compile(rb'"Generated-By: Babel [^\\n]+\\n"')
PO_HEADER_LINE_END = b'\\n"\n'
GETTEXT_CALL_RE = re.compile(
    r"_\(\s*(?P<quote>['\"])(?P<body>(?:\\.|(?! (?P=quote) ).)*)"
    r"(?P=quote)\s*\)",
    re.VERBOSE,
)
TEMPLATE_ROOTS = tuple(
    REPO_ROOT / directory
    for directory in (
        "templates",
        "FSQR/templates",
        "Group/templates",
        "Note/templates",
        "Task/templates",
        "Admin/templates",
        "Articles/templates",
    )
)


def _gettext_format(value: str) -> str:
    """Convert the existing ``str.format`` placeholders to gettext syntax."""

    value = BRACE_PLACEHOLDER_RE.sub(r"%(\1)s", value)
    return PERCENT_RE.sub("%%", value)


def _messages(language: str) -> dict[str, str]:
    sections = load_language_translations(LOCALES_DIR, language)
    messages: dict[str, str] = {}

    for key, value in sections["ui"].items():
        messages[key] = _gettext_format(value)
    for key, value in sections["phrases"].items():
        # Stable UI keys take precedence if a legacy phrase happens to have
        # the same msgid.
        messages.setdefault(key, _gettext_format(value))

    # Template msgids are collected from the actual Jinja source.  This allows
    # a long text node to be one gettext message even when older phrase JSON
    # translated a shorter substring inside it.
    phrase_map = sections["phrases"]
    for msgid in _template_msgids():
        translated = _replace_phrases(msgid, phrase_map)
        if translated != msgid or language == "ja":
            messages.setdefault(msgid, _gettext_format(translated))
    return messages


@lru_cache(maxsize=1)
def _template_msgids() -> tuple[str, ...]:
    values: set[str] = set()
    for root in TEMPLATE_ROOTS:
        for path in root.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            for match in GETTEXT_CALL_RE.finditer(text):
                values.add(ast.literal_eval(match.group(0)[2:-1].strip()))
    return tuple(sorted(values))


def _replace_phrases(source: str, phrases: dict[str, str]) -> str:
    """Preserve the old catalog's established translations for new msgids."""

    for phrase in sorted(phrases, key=len, reverse=True):
        value = phrases[phrase]
        if isinstance(value, str):
            source = source.replace(phrase, value)
    return source


def _normalize_po_headers(output: bytes) -> bytes:
    """Keep non-semantic PO header formatting stable across Babel versions."""

    output = GENERATED_BY_RE.sub(b'"Generated-By: Babel 2.17.0\\n"', output, count=1)

    lines = output.splitlines(keepends=True)
    for start, line in enumerate(lines):
        if not line.startswith(b'"Plural-Forms:'):
            continue
        for end in range(start, len(lines)):
            if not lines[end].endswith(PO_HEADER_LINE_END):
                continue
            header = b"".join(lines[start : end + 1])
            # Babel 2.8 omitted the terminal semicolon; current Babel versions
            # add it. Both forms have the same meaning, so emit the canonical
            # form without touching the following MIME header.
            if not header[: -len(PO_HEADER_LINE_END)].endswith(b";"):
                header = header[: -len(PO_HEADER_LINE_END)] + b";" + PO_HEADER_LINE_END
            lines[start : end + 1] = [header]
            break
        break
    return b"".join(lines)


def _render(language: str) -> bytes:
    catalog = Catalog(
        locale=LOCALE_NAMES.get(language, language),
        domain="messages",
        project="FS!QR",
        version="1.0",
        copyright_holder="FS!QR",
        creation_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        revision_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for msgid, message in sorted(_messages(language).items()):
        catalog.add(msgid, string=message)

    output = BytesIO()
    write_po(output, catalog, no_location=True, sort_output=True)
    # Keep committed catalogs stable when a developer and CI use different
    # Babel patch versions.  The runtime package remains pinned in
    # requirements.txt; this only removes non-semantic source churn.
    normalized = _normalize_po_headers(output.getvalue())
    return normalized.rstrip(b"\n") + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when a generated catalog differs from the working tree",
    )
    args = parser.parse_args()

    changed: list[Path] = []
    for language in SUPPORTED_LANGUAGES:
        path = LOCALES_DIR / language / "LC_MESSAGES" / "messages.po"
        expected = _render(language)
        actual = path.read_bytes() if path.exists() else None
        if actual != expected:
            changed.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected)

    if changed and args.check:
        for path in changed:
            print(f"Out-of-date catalog: {path.relative_to(REPO_ROOT)}")
        return 1
    if changed:
        print(f"Generated {len(changed)} Babel catalogs.")
    else:
        print("Babel catalogs are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
