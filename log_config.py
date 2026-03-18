import logging
import os

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
