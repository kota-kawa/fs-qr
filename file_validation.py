"""ファイル関連の共通バリデーション。"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Sequence
from urllib.parse import quote

from fastapi import UploadFile
from werkzeug.utils import secure_filename

try:
    import magic
except ImportError:  # pragma: no cover - production dependency guard
    magic = None

_DANGEROUS_FILENAME_PATTERNS = ("..", "/", "\\", "\x00", "\r", "\n")
_DISALLOWED_UPLOAD_EXTENSIONS = {".html", ".htm", ".xhtml", ".svg", ".svgz"}
_DISALLOWED_UPLOAD_MIME_TYPES = {
    "application/xhtml+xml",
    "image/svg+xml",
    "text/html",
}
_MIME_DETECTOR = magic.Magic(mime=True) if magic is not None else None


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


def _strip_header_unsafe_chars(value: str) -> str:
    cleaned = "".join(ch for ch in (value or "") if 32 <= ord(ch) != 127)
    return cleaned.replace('"', "").replace("\\", "").strip()


def sanitize_download_filename(filename: str, default: str = "download") -> str:
    cleaned = _strip_header_unsafe_chars(filename)
    if cleaned:
        return cleaned
    return default


def build_content_disposition_attachment(
    filename: str,
    *,
    fallback_filename: str = "download",
) -> str:
    safe_filename = sanitize_download_filename(filename, default=fallback_filename)
    ascii_fallback = safe_filename.encode("ascii", "ignore").decode("ascii")
    ascii_fallback = sanitize_download_filename(
        ascii_fallback, default=fallback_filename
    )
    utf8_filename = quote(safe_filename, safe="!#$&+-.^_`|~")
    return (
        f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_filename}"
    )


def detect_upload_mime_type(upload_file: UploadFile, *, sniff_size: int = 8192) -> str:
    if _MIME_DETECTOR is None:
        raise RuntimeError("python-magic is not available.")

    current_position = upload_file.file.tell()
    upload_file.file.seek(0)
    sample = upload_file.file.read(sniff_size)
    upload_file.file.seek(current_position)
    if not sample:
        return "application/octet-stream"
    detected_mime = _MIME_DETECTOR.from_buffer(sample)
    if not detected_mime:
        return "application/octet-stream"
    return detected_mime


def validate_upload_file_content(upload_file: UploadFile) -> str | None:
    if _MIME_DETECTOR is None:
        return (
            "サーバーのファイル種別判定が利用できません。管理者へお問い合わせください。"
        )

    filename = upload_file.filename or ""
    _, ext = os.path.splitext(filename.lower())
    if ext in _DISALLOWED_UPLOAD_EXTENSIONS:
        return "HTML/SVG ファイルはアップロードできません。"

    detected_mime = detect_upload_mime_type(upload_file)
    if detected_mime in _DISALLOWED_UPLOAD_MIME_TYPES:
        return "HTML/SVG ファイルはアップロードできません。"

    return None
