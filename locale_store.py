from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any


LOCALE_SECTIONS = ("ui", "js", "phrases")
DEFAULT_PHRASE_SHARD = "legacy"


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json_object(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def legacy_locale_path(locales_dir: str | Path, language: str) -> Path:
    return Path(locales_dir) / f"{language}.json"


def locale_dir_path(locales_dir: str | Path, language: str) -> Path:
    return Path(locales_dir) / language


def section_file_path(locales_dir: str | Path, language: str, section: str) -> Path:
    return locale_dir_path(locales_dir, language) / f"{section}.json"


def section_dir_path(locales_dir: str | Path, language: str, section: str) -> Path:
    return locale_dir_path(locales_dir, language) / section


def section_shard_path(
    locales_dir: str | Path, language: str, section: str, shard: str
) -> Path:
    return section_dir_path(locales_dir, language, section) / f"{shard}.json"


def _section_shard_files(
    locales_dir: str | Path, language: str, section: str
) -> list[Path]:
    section_dir = section_dir_path(locales_dir, language, section)
    if not section_dir.is_dir():
        return []
    return sorted(section_dir.rglob("*.json"))


def _shard_name(section_dir: Path, shard_path: Path) -> str:
    return shard_path.relative_to(section_dir).with_suffix("").as_posix()


def _validate_section(section: str) -> None:
    if section not in LOCALE_SECTIONS:
        allowed = ", ".join(LOCALE_SECTIONS)
        raise ValueError(f"Unsupported locale section {section!r}; expected {allowed}")


def load_legacy_language(locales_dir: str | Path, language: str) -> dict[str, Any]:
    path = legacy_locale_path(locales_dir, language)
    if not path.exists():
        return {}
    return _read_json_object(path)


def load_locale_section(
    locales_dir: str | Path, language: str, section: str
) -> dict[str, Any]:
    _validate_section(section)

    legacy = load_legacy_language(locales_dir, language)
    legacy_section = legacy.get(section, {})
    data: dict[str, Any] = dict(legacy_section) if isinstance(legacy_section, dict) else {}

    section_file = section_file_path(locales_dir, language, section)
    if section_file.exists():
        data.update(_read_json_object(section_file))

    section_dir = section_dir_path(locales_dir, language, section)
    for shard_path in _section_shard_files(locales_dir, language, section):
        data.update(_read_json_object(shard_path))

    return data


def load_locale_section_shards(
    locales_dir: str | Path, language: str, section: str
) -> OrderedDict[str, dict[str, Any]]:
    _validate_section(section)

    shards: OrderedDict[str, dict[str, Any]] = OrderedDict()
    legacy = load_legacy_language(locales_dir, language)
    legacy_section = legacy.get(section, {})
    if isinstance(legacy_section, dict) and legacy_section:
        shards["legacy"] = dict(legacy_section)

    section_file = section_file_path(locales_dir, language, section)
    if section_file.exists():
        shards[section] = _read_json_object(section_file)

    section_dir = section_dir_path(locales_dir, language, section)
    for shard_path in _section_shard_files(locales_dir, language, section):
        shards[_shard_name(section_dir, shard_path)] = _read_json_object(shard_path)

    return shards


def load_language_translations(
    locales_dir: str | Path, language: str
) -> dict[str, dict[str, Any]]:
    return {
        section: load_locale_section(locales_dir, language, section)
        for section in LOCALE_SECTIONS
    }


def load_all_translations(
    locales_dir: str | Path, languages: tuple[str, ...]
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        language: load_language_translations(locales_dir, language)
        for language in languages
    }


def save_locale_section(
    locales_dir: str | Path, language: str, section: str, data: dict[str, Any]
) -> None:
    _validate_section(section)
    _write_json_object(section_file_path(locales_dir, language, section), data)


def save_locale_section_shard(
    locales_dir: str | Path,
    language: str,
    section: str,
    shard: str,
    data: dict[str, Any],
) -> None:
    _validate_section(section)
    _write_json_object(section_shard_path(locales_dir, language, section, shard), data)


def choose_writable_shard(
    locales_dir: str | Path,
    language: str,
    section: str,
    preferred_shard: str = DEFAULT_PHRASE_SHARD,
) -> str:
    _validate_section(section)
    section_dir = section_dir_path(locales_dir, language, section)
    if section_dir.is_dir():
        return preferred_shard
    return section
