#!/usr/bin/env python3
"""Verify that file paths referenced from the repository documents exist.

ドキュメント内のパス参照が実在するかを検証する。

対象は AGENTS.md、ARCHITECTURE.md、spec.md、docs/ 配下、locales/README.md、
.github/ 配下の Markdown で、次の 2 種類の参照を確認する。

- Markdown リンク ``[text](relative/path.md#anchor)``
- インラインコード ``\\`path/to/file.py\\``` のうちパスの形をしているもの

存在判定は ``git ls-files``（index に載っている追跡済みファイル）を基準にし、CI の
shallow checkout と同じ結果になるようにする。新しく作った文書やファイルは
``git add``（または ``git add -N``）してから実行する。``.env`` や ``.venv/`` など
git 管理外の実行時パスは IGNORED_* で除外する。Glob (``*``) やプレースホルダー
(``<...>``) を含むトークンは検査しない。

制約: ``/`` を含まないファイル名だけの参照（``js.json`` など）と、``/`` を含む
部分パス（``LC_MESSAGES/messages.po`` など）は、追跡ファイルのいずれかと末尾が
一致すれば存在とみなす。文書ごとの相対位置までは検証しない。

Usage:
    python3 scripts/check_doc_paths.py            # 既定の文書集合を検査
    python3 scripts/check_doc_paths.py docs/x.md  # リポジトリ内の文書だけを指定可
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 検査対象の文書。README.md は公開向け説明で本番ホストのパス例を含むため対象外。
DEFAULT_DOC_GLOBS = (
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CLAUDE.md",
    "spec.md",
    "docs/**/*.md",
    "locales/README.md",
    ".github/**/*.md",
)

# 実行時に生成される、または git 管理外のため追跡対象に無いパス。
# IGNORED_TOKENS は Markdown リンク先にも使われうる単独名、IGNORED_PREFIXES は
# 配下すべてを除外するディレクトリ。
IGNORED_TOKENS = frozenset({".env"})
IGNORED_PREFIXES = (
    ".claude/",
    ".deploy/",
    ".venv/",
    "logs/",
    "storage/",
    "geoip/",
    "hocuspocus/node_modules/",
    "node_modules/",
    "static/qrcode/",
    "static/upload/",
    "static/group_uploads",
)
# 先頭がドットでも検査したい設定サンプル。
DOTFILES_TO_CHECK = frozenset({".env.example"})
# 技術判断の記録は当時のパスを残すため、Markdown リンクだけを検査する。
HISTORICAL_DIRS = ("docs/decisions/",)

PATH_EXTENSIONS = (
    ".py",
    ".md",
    ".sql",
    ".yml",
    ".yaml",
    ".json",
    ".html",
    ".js",
    ".css",
    ".conf",
    ".sh",
    ".txt",
    ".toml",
    ".ini",
    ".po",
    ".cfg",
    ".example",
)

LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
# 相対パスの形。空白・glob・プレースホルダー・URL・絶対パスは除外する。
PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*/?$")


def ignored(token: str) -> bool:
    return token in IGNORED_TOKENS or token.startswith(IGNORED_PREFIXES)


def tracked_paths() -> set[str]:
    """Return tracked files plus every ancestor directory (with trailing slash)."""
    try:
        output = subprocess.run(  # noqa: S603 - fixed argv, no user input
            ["git", "ls-files", "-z"],  # noqa: S607 - git is a CI prerequisite
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
        files = [item for item in output.split("\0") if item]
    except (OSError, subprocess.CalledProcessError):
        files = [
            str(path.relative_to(REPO_ROOT))
            for path in REPO_ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
    known: set[str] = set()
    for item in files:
        known.add(item)
        parent = Path(item).parent
        while str(parent) not in {".", ""}:
            known.add(f"{parent.as_posix()}/")
            known.add(parent.as_posix())
            parent = parent.parent
    return known


def looks_like_path(token: str) -> bool:
    if ignored(token):
        return False
    if not PATH_TOKEN_RE.match(token):
        return False
    if (
        token.startswith((".", "-"))
        and "/" not in token
        and token not in DOTFILES_TO_CHECK
    ):
        # ".venv" や "-q" のような単独トークンはパスとして扱わない。
        return False
    if "/" in token:
        return True
    return token.endswith(PATH_EXTENSIONS)


def normalize(target: str) -> str:
    target = target.split("#", 1)[0]
    return target.rstrip("/") + ("/" if target.endswith("/") else "")


def candidates(doc: Path, target: str) -> list[str]:
    """Resolve a reference relative to the document, then to the repository root."""
    results: list[str] = []
    for base in (doc.parent, REPO_ROOT):
        resolved = (base / target).resolve()
        try:
            relative = resolved.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if target.endswith("/"):
            relative += "/"
        results.append(relative)
    return results


def iter_references(doc: Path, *, links_only: bool = False):
    """Yield (line_number, target, kind) for each path-like reference."""
    in_fence = False
    for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_RE.finditer(line):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            yield number, normalize(target), "link"
        if links_only:
            continue
        for match in INLINE_CODE_RE.finditer(line):
            token = match.group(1).strip()
            if looks_like_path(token):
                yield number, normalize(token), "code"


def exists(doc: Path, target: str, known: set[str]) -> bool:
    """Accept exact paths, then bare file names or path suffixes of tracked files."""
    options = candidates(doc, target)
    if any(option in known or option.rstrip("/") in known for option in options):
        return True
    suffix = "/" + target.rstrip("/")
    return any(item == target or item.endswith(suffix) for item in known)


def check_document(doc: Path, known: set[str]) -> list[str]:
    problems: list[str] = []
    rel_doc = doc.relative_to(REPO_ROOT).as_posix()
    links_only = rel_doc.startswith(HISTORICAL_DIRS)
    for number, target, kind in iter_references(doc, links_only=links_only):
        if not target or ignored(target):
            continue
        if exists(doc, target, known):
            continue
        problems.append(f"{rel_doc}:{number}: missing path ({kind}): {target}")
    return problems


def collect_documents(arguments: list[str]) -> list[Path]:
    if arguments:
        return [Path(argument).resolve() for argument in arguments]
    documents: list[Path] = []
    for pattern in DEFAULT_DOC_GLOBS:
        documents.extend(
            path
            for path in sorted(REPO_ROOT.glob(pattern))
            if path.is_file() and ".claude" not in path.parts
        )
    return documents


def main(arguments: list[str]) -> int:
    known = tracked_paths()
    problems: list[str] = []
    documents = collect_documents(arguments)
    for doc in documents:
        problems.extend(check_document(doc, known))
    if problems:
        print("Documentation references paths that do not exist in the repository:")
        print("\n".join(problems))
        return 1
    print(f"OK: {len(documents)} documents reference only existing paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
