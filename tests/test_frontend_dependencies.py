"""Regression checks for vendored and CDN-hosted frontend dependencies."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CDN_ASSETS = {
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css": (
        "sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB"
    ),
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js": (
        "sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI"
    ),
    "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js": (
        "sha384-+mbV2IY1Zk/X1p/nWllGySJSUN8uMs+gUAN10Or95UBH0fpj6GfKgPmgC5EXieXG"
    ),
    "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@7.3.0/css/all.min.css": (
        "sha384-sTlsophtwz/I4myskS3OIJf5VvEojkXKZyBTWZm0YD/K1pN7C5wpBPLyrsbr1SU2"
    ),
}

LEGACY_VERSION_MARKERS = (
    "bootstrap@5.3.0",
    "Bootstrap v5.0.2",
    "jszip/3.7.1",
    "font-awesome/6.0.0-beta3",
    "font-awesome/6.5.2",
)


def _frontend_sources() -> list[Path]:
    template_roots = (
        PROJECT_ROOT / "templates",
        PROJECT_ROOT / "Admin" / "templates",
        PROJECT_ROOT / "Articles" / "templates",
        PROJECT_ROOT / "FSQR" / "templates",
        PROJECT_ROOT / "Group" / "templates",
        PROJECT_ROOT / "Note" / "templates",
    )
    return [path for root in template_roots for path in root.rglob("*.html")] + [
        PROJECT_ROOT / "static" / "bootstrap.min.css"
    ]


def test_frontend_dependency_versions_are_current() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in _frontend_sources()
    )

    for marker in LEGACY_VERSION_MARKERS:
        assert marker not in combined
    for url in EXPECTED_CDN_ASSETS:
        assert url in combined


def test_cdn_asset_sri_values_match_pinned_files() -> None:
    asset_tag = re.compile(
        r'(?:href|src)="(?P<url>https://[^\"]+)"[^>]*'
        r'integrity="(?P<integrity>sha384-[^\"]+)"'
    )

    found_assets: dict[str, set[str]] = {}
    for path in _frontend_sources():
        if path.suffix != ".html":
            continue
        for match in asset_tag.finditer(path.read_text(encoding="utf-8")):
            url = match.group("url")
            if url in EXPECTED_CDN_ASSETS:
                found_assets.setdefault(url, set()).add(match.group("integrity"))

    assert found_assets == {
        url: {integrity} for url, integrity in EXPECTED_CDN_ASSETS.items()
    }


def test_vendored_bootstrap_matches_official_5_3_8_css() -> None:
    css = (PROJECT_ROOT / "static" / "bootstrap.min.css").read_bytes()
    digest = base64.b64encode(hashlib.sha384(css).digest()).decode("ascii")

    assert b"Bootstrap  v5.3.8" in css
    assert (
        f"sha384-{digest}"
        == EXPECTED_CDN_ASSETS[
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css"
        ]
    )
