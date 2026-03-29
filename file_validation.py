"""ファイル関連の共通バリデーション。"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Sequence

from fastapi import UploadFile
from werkzeug.utils import secure_filename

_DANGEROUS_FILENAME_PATTERNS = ("..", "/", "\\", "\x00")


def has_dangerous_filename_pattern(filename: str) -> bool:
    return any(pattern in filename for pattern in _DANGEROUS_FILENAME_PATTERNS)


def validate_requested_filename(filename: str) -> str | None:
    if has_dangerous_filename_pattern(filename):
        return "不正なファイル名が検出されました。"
    if not filename.strip():
        return "無効なファイル名です。"
    return None


def count_total_upload_size(files: Iterable[UploadFile]) -> int:
    total_size = 0
    for file in files:
        if not file.filename:
            continue
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)
        total_size += file_size
    return total_size


def validate_upload_limits(
    files: Sequence[UploadFile],
    *,
    max_files: int,
    max_total_size_bytes: int,
    max_total_size_mb: int,
    too_many_files_message: str | None = None,
    too_large_total_size_message: str | None = None,
) -> str | None:
    if len(files) > max_files:
        return too_many_files_message or f"ファイル数は最大{max_files}個までです。"

    if count_total_upload_size(files) > max_total_size_bytes:
        return (
            too_large_total_size_message
            or f"ファイルの合計サイズは{max_total_size_mb}MBまでです。"
        )

    return None


def normalize_upload_filename(filename: str) -> str:
    return secure_filename(filename or "")


def sanitize_group_upload_filename(filename: str) -> str:
    safe_filename = filename

    if has_dangerous_filename_pattern(filename):
        safe_filename = secure_filename(filename)

    if not safe_filename or safe_filename.startswith("."):
        _, ext = os.path.splitext(filename)
        safe_filename = f"file_{int(time.time())}{ext}"

    return safe_filename
