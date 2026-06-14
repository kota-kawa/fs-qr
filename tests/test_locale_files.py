from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


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


def test_article_phrase_keys_route_to_article_shards():
    from article_locale_shards import ARTICLE_SHARED_SHARD, article_phrase_shard_for_key

    assert (
        article_phrase_shard_for_key(
            "写真を画質を落とさずに送る方法｜送ると劣化する原因と対策"
        )
        == "articles/send-photos-without-quality-loss"
    )
    assert (
        article_phrase_shard_for_key(
            "スマートウォッチのシリコンバンドでかぶれる・蒸れる時の対策と代替バンドの選び方"
        )
        == "articles/smartwatch-band-rash"
    )
    assert article_phrase_shard_for_key("デジタル豆知識") == ARTICLE_SHARED_SHARD
    assert article_phrase_shard_for_key("安全") == ARTICLE_SHARED_SHARD
    assert article_phrase_shard_for_key("この記事には存在しない文言") is None
    assert article_phrase_shard_for_key("") is None


def test_locale_store_loads_recursive_phrase_shards(tmp_path: Path):
    from locale_store import (
        choose_writable_shard,
        load_all_translations,
        load_language_translations,
        load_locale_section,
        load_locale_section_shards,
        save_locale_section,
        save_locale_section_shard,
        section_shard_path,
    )

    save_locale_section(tmp_path, "en", "ui", {"settings.title": "Settings"})
    save_locale_section_shard(
        tmp_path,
        "en",
        "phrases",
        "articles/example-article",
        {"記事タイトル": "Article title"},
    )
    save_locale_section_shard(
        tmp_path,
        "en",
        "phrases",
        "legacy",
        {"URLをコピー": "Copy URL"},
    )

    assert (
        section_shard_path(tmp_path, "en", "phrases", "articles/example-article")
        == tmp_path / "en" / "phrases" / "articles" / "example-article.json"
    )
    assert load_locale_section(tmp_path, "en", "phrases") == {
        "記事タイトル": "Article title",
        "URLをコピー": "Copy URL",
    }
    assert list(load_locale_section_shards(tmp_path, "en", "phrases")) == [
        "articles/example-article",
        "legacy",
    ]
    assert load_language_translations(tmp_path, "en")["ui"] == {
        "settings.title": "Settings"
    }
    assert (
        load_all_translations(tmp_path, ("en",))["en"]["phrases"]["記事タイトル"]
        == "Article title"
    )
    assert choose_writable_shard(tmp_path, "en", "phrases") == "legacy"


def test_locale_store_rejects_invalid_sections_and_json_shapes(tmp_path: Path):
    from locale_store import load_locale_section, save_locale_section

    with pytest.raises(ValueError, match="Unsupported locale section"):
        save_locale_section(tmp_path, "en", "unknown", {})

    invalid_path = tmp_path / "en" / "ui.json"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_locale_section(tmp_path, "en", "ui")


def test_locale_validation_script_passes_for_default_checks():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/validate_locales.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _load_locale_section_keys(language: str, section: str) -> set[str]:
    from locale_store import load_locale_section

    return set(load_locale_section("locales", language, section))


def test_locale_catalogs_are_covered_before_english_fallback():
    """設定言語の画面に英語フォールバックが混ざらないよう辞書欠落を検出する。

    対象言語にも英語より前のフォールバック言語にもキーがない場合、ui/js/phrases
    のどの領域でも LANGUAGE_FALLBACKS により英語訳が画面へ混入するため、CI で落とす。
    """
    from i18n import LANGUAGE_FALLBACKS, SUPPORTED_LANGUAGES

    sections = ("ui", "js", "phrases")

    failures: list[str] = []
    for section in sections:
        english_keys = _load_locale_section_keys("en", section)
        assert english_keys, f"English {section} catalog must not be empty"

        for language in SUPPORTED_LANGUAGES:
            if language in {"ja", "en"}:
                continue

            covered_keys = _load_locale_section_keys(language, section)
            for fallback_language in LANGUAGE_FALLBACKS.get(language, ()):
                if fallback_language == "en":
                    break
                covered_keys.update(
                    _load_locale_section_keys(fallback_language, section)
                )

            missing_keys = sorted(english_keys - covered_keys)
            if missing_keys:
                examples = "; ".join(key[:80] for key in missing_keys[:5])
                failures.append(
                    f"{language}/{section}: {len(missing_keys)} missing keys "
                    f"before English fallback. Examples: {examples}"
                )

    assert failures == [], "\n".join(failures)
