#!/usr/bin/env python3
"""Keep ``.env.example`` in sync with the environment variables the code reads.

コードが実行時に読む環境変数と ``.env.example`` の記載を突き合わせる。

- コード側: ``settings.py`` などの ``os.getenv(...)`` / ``os.environ[...]`` /
  ``_env_int(...)`` のような env ヘルパー呼び出しに渡された大文字の文字列リテラル、
  ``hocuspocus/*.js`` の ``process.env.NAME``、``docker-compose.yml`` の ``${NAME}`` を抽出する。
  Python の ``#`` コメント行は読み飛ばすが、docstring 内の擬似コードは拾うので、
  例を書くときは引用符付きリテラルを避ける。
- 文書側: ``.env.example`` の ``NAME=`` 行（``# NAME=`` のコメント行も含む）。

どちらか一方にしか無い名前があれば一覧を表示して終了コード 1 を返す。
テスト専用・CI 専用の変数は対象外にしている。

Usage:
    python3 scripts/check_env_documentation.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# 走査しないディレクトリ・ファイル。テストとスモーク検証はデプロイ設定ではない。
EXCLUDED_PREFIXES = (
    "tests/",
    ".github/",
    "static/",  # ブラウザ向け JS（bundle 済みを含む）はサーバー環境変数を読まない
    "hocuspocus/node_modules/",
)
EXCLUDED_SUFFIXES = (".test.js",)
# 自分自身は抽出パターンの説明を含むため走査しない。
EXCLUDED_FILES = frozenset(
    {
        "hocuspocus/docker-smoke.js",
        Path(__file__).resolve().relative_to(REPO_ROOT).as_posix(),
    }
)

# 抽出パターン。os.getenv / os.environ.get / os.environ[...] / _env_int / _int_env に
# 渡された大文字の文字列リテラルを 1 つの正規表現で拾う。
PYTHON_ENV_RE = re.compile(
    r"\b[A-Za-z_]*env[A-Za-z_]*\s*(?:\.get)?\s*[\(\[]\s*[\"']([A-Z][A-Z0-9_]*)[\"']"
)
# process.env.NAME / process.env[...] / positiveEnvNumber(...) の 3 形式
JS_ENV_RE = re.compile(
    r"process\.env(?:\.([A-Z][A-Z0-9_]*)|\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']\s*\])"
    r"|\b[A-Za-z]*Env[A-Za-z]*\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']"
)
COMPOSE_ENV_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)")
ENV_EXAMPLE_RE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=")


def tracked_files() -> list[str]:
    output = subprocess.run(  # noqa: S603 - fixed argv, no user input
        ["git", "ls-files", "-z"],  # noqa: S607 - git is a CI prerequisite
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return [item for item in output.split("\0") if item]


def is_scanned(path: str) -> bool:
    if path in EXCLUDED_FILES or path.startswith(EXCLUDED_PREFIXES):
        return False
    if path.endswith(EXCLUDED_SUFFIXES):
        return False
    return path.endswith((".py", ".js", ".mjs")) or path == "docker-compose.yml"


def variables_in_code() -> dict[str, set[str]]:
    """Map each environment variable name to the files that read it."""
    found: dict[str, set[str]] = {}
    for path in tracked_files():
        if not is_scanned(path):
            continue
        text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")
        if path == "docker-compose.yml":
            names = COMPOSE_ENV_RE.findall(text)
        elif path.endswith(".py"):
            code_lines = [
                line for line in text.splitlines() if not line.lstrip().startswith("#")
            ]
            names = PYTHON_ENV_RE.findall("\n".join(code_lines))
        else:
            names = [
                next(group for group in match if group)
                for match in JS_ENV_RE.findall(text)
            ]
        for name in names:
            found.setdefault(name, set()).add(path)
    return found


def variables_in_env_example() -> set[str]:
    names: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = ENV_EXAMPLE_RE.match(line)
        if match:
            names.add(match.group(1))
    return names


def main() -> int:
    in_code = variables_in_code()
    documented = variables_in_env_example()

    undocumented = sorted(set(in_code) - documented)
    unused = sorted(documented - set(in_code))

    if undocumented:
        print("Environment variables read by the code but missing from .env.example:")
        for name in undocumented:
            print(f"  {name}  <- {', '.join(sorted(in_code[name]))}")
    if unused:
        print("Entries in .env.example that no code reads (stale documentation):")
        for name in unused:
            print(f"  {name}")
    if undocumented or unused:
        return 1
    print(f"OK: {len(documented)} environment variables are documented and in use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
