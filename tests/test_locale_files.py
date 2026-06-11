from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_locale_catalogs_are_split_by_language_and_section():
    from i18n import SUPPORTED_LANGUAGES

    locales_dir = Path("locales")

    assert not sorted(locales_dir.glob("*.json"))

    for language in SUPPORTED_LANGUAGES:
        language_dir = locales_dir / language
        assert language_dir.is_dir()
        assert (language_dir / "ui.json").is_file()
        assert (language_dir / "js.json").is_file()
        assert (language_dir / "phrases").is_dir()
        assert sorted((language_dir / "phrases").glob("*.json"))
        assert not (language_dir / "phrases" / "articles.json").exists()
        assert (language_dir / "phrases" / "articles").is_dir()
        assert (language_dir / "phrases" / "articles" / "_shared.json").is_file()
        assert sorted((language_dir / "phrases" / "articles").glob("*.json"))


def test_i18n_loads_split_locale_catalogs():
    import i18n

    i18n.load_translations.cache_clear()
    translations = i18n.load_translations()

    assert translations["en"]["ui"]["settings.title"] == "Settings"
    assert translations["ja"]["js"]["alert.notice"] == "お知らせ"
    assert translations["fr"]["phrases"]["URLをコピー"] == "Copier l'URL"


def test_locale_validation_script_passes_for_default_checks():
    result = subprocess.run(
        [sys.executable, "scripts/validate_locales.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
