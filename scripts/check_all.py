from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Merchant
from app.services.auth import ensure_default_admin, migrate_auth_schema_if_needed
from app.services.seed_data import ensure_professional_seed_data

ADMIN_EMAIL = "admin@cardpilot.local"
ADMIN_PASSWORD = "Admin@12345"


def record(results: list[tuple[str, bool, str]], name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def main() -> int:
    init_db()
    with SessionLocal() as db:
        migrate_auth_schema_if_needed(db)
        ensure_professional_seed_data(db)
        ensure_default_admin(db)

    results: list[tuple[str, bool, str]] = []
    with TestClient(app) as client:
        response = client.get("/health")
        record(results, "Health endpoint", response.status_code == 200 and response.json().get("status") == "ok", str(response.json()))

        response = client.get("/")
        record(results, "Landing page", response.status_code == 200 and "Professional credit card decisions" in response.text, f"HTTP {response.status_code}")

        response = client.get("/login")
        record(results, "Login page", response.status_code == 200 and "Sign in" in response.text, f"HTTP {response.status_code}")

        response = client.post(
            "/auth/login",
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "next": "/app"},
            follow_redirects=False,
        )
        record(results, "Admin login", response.status_code == 303 and response.headers.get("location") == "/app", f"HTTP {response.status_code}")

        response = client.get("/app")
        record(results, "Authenticated workspace", response.status_code == 200 and "My Cards" in response.text and "Best Card Finder" in response.text, f"HTTP {response.status_code}")

        response = client.get("/admin")
        record(results, "Admin portal", response.status_code == 200 and "Operate CardPilot" in response.text, f"HTTP {response.status_code}")

        admin_user_id = None
        with SessionLocal() as db:
            admin_user = ensure_default_admin(db)
            admin_user_id = admin_user.user_id
        response = client.post(
            "/admin/users/reset-password",
            data={"user_id": admin_user_id, "new_password": ADMIN_PASSWORD},
            follow_redirects=True,
        )
        record(results, "Admin password reset action", response.status_code == 200 and "Password reset" in response.text, f"HTTP {response.status_code}")

        response = client.get("/database")
        record(results, "Database page", response.status_code == 200 and "CardPilot database" in response.text, f"HTTP {response.status_code}")

        with SessionLocal() as db:
            merchant_count = db.query(Merchant).count()
        record(results, "Expanded merchant database", merchant_count >= 300, f"{merchant_count} merchants loaded")

        response = client.get("/cards?limit=5")
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else []
        record(results, "Cards API", response.status_code == 200 and isinstance(data, list) and len(data) > 0, f"returned {len(data) if isinstance(data, list) else 'non-list'} cards")

        response = client.get("/cards/CC001")
        record(results, "Single card API", response.status_code == 200 and response.json().get("card_id") == "CC001", f"HTTP {response.status_code}")

        response = client.post(
            "/rewards/calculate",
            json={"card_id": "CC001", "merchant_raw": "Amazon", "amount_inr": 5000, "transaction_channel": "online", "category": "online shopping"},
        )
        calc = response.json()
        record(results, "Reward calculation API", response.status_code == 200 and calc.get("rule_id") is not None, f"rule={calc.get('rule_id')} expected={calc.get('expected_value_inr')}")

        response = client.post(
            "/rewards/recommend-best-card",
            json={"merchant_raw": "Amazon", "amount_inr": 5000, "transaction_channel": "online", "category": "online shopping", "top_n": 5},
        )
        recs = response.json().get("recommendations", []) if response.status_code == 200 else []
        record(results, "Best card API", response.status_code == 200 and len(recs) > 0, f"returned {len(recs)} recommendations")

        response = client.post("/ui/my-cards/add", data={"card_id": "CC001", "masked_last4": "1234"}, follow_redirects=True)
        record(results, "My Cards UI add", response.status_code == 200 and "SBI Cashback" in response.text, f"HTTP {response.status_code}")

        response = client.post(
            "/ui/recommend",
            data={"merchant_raw": "Amazon", "amount_inr": "5000", "category": "online shopping", "use_my_cards_only": "yes"},
        )
        record(results, "Best card UI", response.status_code == 200 and "Purchase recommendation" in response.text, f"HTTP {response.status_code}")

        response = client.post(
            "/ui/card-advisor",
            data={
                "monthly_spend_inr": "50000",
                "primary_category": "online shopping",
                "secondary_category": "travel",
                "reward_preference": "cashback",
                "annual_fee_preference": "low_fee",
                "travel_frequency": "sometimes",
            },
        )
        record(results, "Card Advisor UI", response.status_code == 200 and "Suggested cards for a new customer" in response.text, f"HTTP {response.status_code}")

        sample_csv = ROOT / "data" / "sample_statement.csv"
        with sample_csv.open("rb") as f:
            response = client.post(
                "/ui/analyze",
                data={"card_id": "CC001", "statement_password": ""},
                files={"file": ("sample_statement.csv", f, "text/csv")},
            )
        record(results, "Statement upload UI", response.status_code == 200 and "Reward review results" in response.text and "Possible missing value" in response.text, f"HTTP {response.status_code}")

        with sample_csv.open("rb") as f:
            response = client.post(
                "/statements/upload",
                data={"card_id": "CC001", "statement_password": ""},
                files={"file": ("sample_statement.csv", f, "text/csv")},
            )
        upload = response.json() if response.status_code == 200 else {}
        record(results, "Statement upload API", response.status_code == 200 and upload.get("transactions_analyzed", 0) > 0, f"transactions={upload.get('transactions_analyzed')}")

        sample_pdf = ROOT / "data" / "sample_statement_text_pdf.pdf"
        with sample_pdf.open("rb") as f:
            response = client.post(
                "/ui/analyze",
                data={"card_id": "CC001", "statement_password": ""},
                files={"file": ("sample_statement_text_pdf.pdf", f, "application/pdf")},
            )
        record(results, "PDF statement upload UI", response.status_code == 200 and "Reward review results" in response.text and "Expected only" in response.text, f"HTTP {response.status_code}")

        with sample_pdf.open("rb") as f:
            response = client.post(
                "/statements/upload",
                data={"card_id": "CC001", "statement_password": ""},
                files={"file": ("sample_statement_text_pdf.pdf", f, "application/pdf")},
            )
        pdf_upload = response.json() if response.status_code == 200 else {}
        record(results, "PDF statement upload API", response.status_code == 200 and pdf_upload.get("transactions_analyzed", 0) > 0, f"transactions={pdf_upload.get('transactions_analyzed')}")

        response = client.get("/api/me")
        me = response.json() if response.status_code == 200 else {}
        record(results, "Mobile me API", response.status_code == 200 and me.get("email") == ADMIN_EMAIL, f"HTTP {response.status_code}")

        response = client.get("/api/my-cards")
        user_cards = response.json().get("cards", []) if response.status_code == 200 else []
        record(results, "Mobile my-cards API", response.status_code == 200 and any(item.get("card_id") == "CC001" for item in user_cards), f"cards={len(user_cards)}")

        response = client.get("/api/admin/stats")
        admin_stats = response.json() if response.status_code == 200 else {}
        record(results, "Admin stats API", response.status_code == 200 and admin_stats.get("users", 0) >= 1, f"users={admin_stats.get('users')}")

        response = client.get("/self-test.json")
        report = response.json() if response.status_code == 200 else {}
        record(results, "Self-test route", response.status_code == 200 and report.get("failed") == 0, f"passed={report.get('passed')} failed={report.get('failed')}")

    failed = [name for name, ok, _ in results if not ok]
    print("\nSummary")
    print("-------")
    print(f"Passed: {len(results) - len(failed)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print("Failed checks:")
        for item in failed:
            print(f"- {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
