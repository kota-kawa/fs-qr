import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(__file__)

ADMIN_KEY = os.getenv("ADMIN_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
MANAGEMENT_PASSWORD = os.getenv("MANAGEMENT_PASSWORD")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
