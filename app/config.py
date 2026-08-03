import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-31b-it")

DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "app.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

TARGET_APP_URL = os.environ.get("TARGET_APP_URL", "https://www.demoblaze.com")

# Safety cap so a confused agent can't loop forever during capture or recovery.
MAX_CAPTURE_STEPS = 12
MAX_RECOVERY_ATTEMPTS_PER_STEP = 2
