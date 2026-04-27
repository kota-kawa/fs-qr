import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(__file__)

ADMIN_KEY = os.getenv("ADMIN_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
MANAGEMENT_PASSWORD = os.getenv("MANAGEMENT_PASSWORD")
DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return parsed


FRONTEND_DEBUG = _env_flag("FRONTEND_DEBUG", default=False)
ALLOW_START_WITHOUT_DB = _env_flag("ALLOW_START_WITHOUT_DB", default=False)

UPLOAD_MAX_FILES = _env_int("UPLOAD_MAX_FILES", default=10, minimum=1)
UPLOAD_MAX_TOTAL_SIZE_MB = _env_int("UPLOAD_MAX_TOTAL_SIZE_MB", default=500, minimum=1)
UPLOAD_MAX_TOTAL_SIZE_BYTES = UPLOAD_MAX_TOTAL_SIZE_MB * 1024 * 1024

GROUP_FILE_LIST_REQUEST_TIMEOUT_MS = _env_int(
    "GROUP_FILE_LIST_REQUEST_TIMEOUT_MS", default=10_000, minimum=1
)
GROUP_FILE_LIST_POLL_INTERVAL_MS = _env_int(
    "GROUP_FILE_LIST_POLL_INTERVAL_MS", default=15_000, minimum=1_000
)

NOTE_MAX_CONTENT_LENGTH = _env_int("NOTE_MAX_CONTENT_LENGTH", default=10_000, minimum=1)
NOTE_SELF_EDIT_TIMEOUT_MS = _env_int(
    "NOTE_SELF_EDIT_TIMEOUT_MS", default=12_000, minimum=1
)

SESSION_MAX_AGE_SECONDS = _env_int("SESSION_MAX_AGE_SECONDS", default=3600, minimum=60)
AUTH_SESSION_TIMEOUT_SECONDS = _env_int(
    "AUTH_SESSION_TIMEOUT_SECONDS", default=1800, minimum=60
)
