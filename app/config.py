import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
INCOMING_DIR = DATA_DIR / "incoming"
DB_PATH = DATA_DIR / "factory.db"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
INCOMING_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables (.env with fallback to .env.example)
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
elif (BASE_DIR / ".env.example").exists():
    load_dotenv(BASE_DIR / ".env.example")


# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Operational defaults
DEFAULT_REORDER_DAYS = int(os.getenv("DEFAULT_REORDER_DAYS", "14"))
DEFAULT_LOW_STOCK_THRESHOLD = float(os.getenv("DEFAULT_LOW_STOCK_THRESHOLD", "10.0"))
