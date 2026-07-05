from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.services.reward_engine import calculate_expected_reward
from scripts.import_workbook import import_workbook

def test_sbi_cashback_amazon_demo():
    init_db()
    import_workbook(ROOT / "data" / "credit_card_rewards_mvp_database.xlsx")
    with SessionLocal() as db:
        result = calculate_expected_reward(db, card_id="CC001", merchant_raw="Amazon", amount_inr=5000, transaction_channel="online", category="online shopping")
    assert result["rule_id"] is not None
    assert result["expected_value_inr"] >= 0
    assert result["confidence"] in {"High", "Medium", "Low"}
