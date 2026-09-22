"""Tests for the repository documentation / configuration consistency scripts.

scripts/check_doc_paths.py と scripts/check_env_documentation.py の抽出ロジックと、
リポジトリ全体が現在それらの検証を通ることを確認する。
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


check_doc_paths = _load("check_doc_paths")
check_env_documentation = _load("check_env_documentation")


# --- check_doc_paths ---------------------------------------------------------


def test_looks_like_path_accepts_relative_paths_and_known_extensions():
    assert check_doc_paths.looks_like_path("docs/knowledge/debugging.md")
    assert check_doc_paths.looks_like_path("settings.py")
    assert check_doc_paths.looks_like_path("templates/")
    # 単語や CLI フラグ、glob、プレースホルダー、URL、絶対パスは対象外。
    assert not check_doc_paths.looks_like_path("pytest")
    assert not check_doc_paths.looks_like_path("-q")
    assert not check_doc_paths.looks_like_path("*_app.py")
    assert not check_doc_paths.looks_like_path("test_<対象>.py")
    assert not check_doc_paths.looks_like_path("https://example.com/x.md")
    assert not check_doc_paths.looks_like_path("/var/www/fs-qr")
    # git 管理外の実行時パスは検査しない。
    assert not check_doc_paths.looks_like_path(".env")
    assert not check_doc_paths.looks_like_path("storage/fsqr_uploads")


def test_check_document_reports_missing_links_and_code_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(check_doc_paths, "REPO_ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    doc = tmp_path / "docs" / "guide.md"
    doc.write_text(
        "\n".join(
            [
                "See [debugging](debugging.md) and [missing](nowhere.md).",
                "Edit `settings.py`, `ghost/file.py` and `js.json`.",
                "```bash",
                "python3 scripts/not_checked_in_fences.py",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    known = {
        "docs/debugging.md",
        "docs/",
        "docs",
        "settings.py",
        "locales/en/js.json",
        "locales/en/",
        "locales/",
    }
    problems = check_doc_paths.check_document(doc, known)
    assert problems == [
        "docs/guide.md:1: missing path (link): nowhere.md",
        "docs/guide.md:2: missing path (code): ghost/file.py",
    ]


def test_historical_decisions_only_check_links(tmp_path, monkeypatch):
    monkeypatch.setattr(check_doc_paths, "REPO_ROOT", tmp_path)
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    doc = tmp_path / "docs" / "decisions" / "0001-old.md"
    doc.write_text("Old code lived in `Note/note_ws.py`.\n", encoding="utf-8")
    assert check_doc_paths.check_document(doc, set()) == []


# --- check_env_documentation -------------------------------------------------


def test_python_pattern_extracts_helper_and_direct_reads():
    text = """
SECRET = os.getenv("SECRET_KEY")
HOST = os.environ["SQL_HOST"]
PORT = os.environ.get("SQL_PORT", "3306")
LIMIT = _env_int(
    "UPLOAD_MAX_FILES", default=30, minimum=1
)
WORKERS = _int_env("WEB_CONCURRENCY", 4)
"""
    names = set(check_env_documentation.PYTHON_ENV_RE.findall(text))
    assert names == {
        "SECRET_KEY",
        "SQL_HOST",
        "SQL_PORT",
        "UPLOAD_MAX_FILES",
        "WEB_CONCURRENCY",
    }


def test_js_and_compose_patterns_extract_names():
    js = """
const port = Number(process.env.HOCUSPOCUS_PORT || 1234);
const secret = process.env["NOTE_YJS_SECRET"];
const limit = positiveEnvNumber("NOTE_MAX_CONNECTIONS_PER_ROOM", 100, 1);
"""
    found = {
        next(group for group in match if group)
        for match in check_env_documentation.JS_ENV_RE.findall(js)
    }
    assert found == {
        "HOCUSPOCUS_PORT",
        "NOTE_YJS_SECRET",
        "NOTE_MAX_CONNECTIONS_PER_ROOM",
    }
    compose = "      - SQL_HOST=${SQL_HOST:-db}\n      - SECRET_KEY=${SECRET_KEY}\n"
    assert set(check_env_documentation.COMPOSE_ENV_RE.findall(compose)) == {
        "SQL_HOST",
        "SECRET_KEY",
    }


def test_env_example_pattern_accepts_commented_entries():
    lines = ["SQL_HOST=db", "# OPTIONAL_FLAG=", "# 説明だけの行", "lower=1"]
    names = {
        match.group(1)
        for line in lines
        if (match := check_env_documentation.ENV_EXAMPLE_RE.match(line))
    }
    assert names == {"SQL_HOST", "OPTIONAL_FLAG"}


# --- repository-wide -----------------------------------------------------------


def test_repository_documents_reference_existing_paths():
    assert check_doc_paths.main([]) == 0


def test_repository_env_example_matches_code():
    assert check_env_documentation.main() == 0
