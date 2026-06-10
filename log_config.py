import logging
import os
import re

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "error.log")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


def _build_error_handler():
    try:
        handler = logging.FileHandler(LOG_FILE)
    except OSError:
        return None

    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


# 旧形式 /fs-qr/{room_id}/{password} は URL パスに認証情報を含むため、
# 共有リンクのトークン /fs-qr/s/{token} とあわせてアクセスログから伏せる。
_SENSITIVE_PATH_PATTERNS = (
    (re.compile(r"/fs-qr/s/[^/?#\s\"]+"), "/fs-qr/s/[redacted]"),
    (
        re.compile(r"/fs-qr/(?!s/|delete/)[^/?#\s\"]+/[^/?#\s\"]+"),
        "/fs-qr/[redacted]/[redacted]",
    ),
)


def redact_sensitive_paths(text: str) -> str:
    for pattern, replacement in _SENSITIVE_PATH_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SensitivePathRedactionFilter(logging.Filter):
    """アクセスログのレコードから認証情報入りパスを伏せる。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_paths(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_sensitive_paths(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def _install_redaction_filter() -> None:
    # uvicorn.access: UvicornWorker 経由のアクセスログ
    # gunicorn.access: gunicorn ネイティブのアクセスログ（フォールバック）
    for logger_name in ("uvicorn.access", "gunicorn.access"):
        target = logging.getLogger(logger_name)
        if not any(isinstance(f, SensitivePathRedactionFilter) for f in target.filters):
            target.addFilter(SensitivePathRedactionFilter())


_install_redaction_filter()

root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)

    error_handler = _build_error_handler()
    if error_handler is not None:
        root_logger.addHandler(error_handler)
    else:
        root_logger.warning(
            "File logging is disabled because %s is not writable.", LOG_FILE
        )
