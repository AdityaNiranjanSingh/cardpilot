from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'card_rewards_mvp.db'}")
# Render/Railway often provide postgres:// or postgresql:// URLs. Normalize to psycopg for SQLAlchemy.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
SEED_WORKBOOK_PATH = os.getenv("SEED_WORKBOOK_PATH", str(DATA_DIR / "credit_card_rewards_mvp_database.xlsx"))

SECRET_KEY = os.getenv("SECRET_KEY", "cardpilot-local-dev-change-this-before-hosting")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "cardpilot_session")
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "14"))
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "0").strip().lower() in {"1", "true", "yes"}
CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if item.strip()]

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@cardpilot.local")
ADMIN_NAME = os.getenv("ADMIN_NAME", "CardPilot Admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@12345")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
