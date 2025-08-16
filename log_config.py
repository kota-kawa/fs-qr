import logging
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'error.log')
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)

    error_handler = logging.FileHandler(LOG_FILE)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(error_handler)
