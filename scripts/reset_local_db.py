from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import DATA_DIR

if __name__ == "__main__":
    db_path = DATA_DIR / "card_rewards_mvp.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted {db_path}")
    else:
        print("No local SQLite database found.")
