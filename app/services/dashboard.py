from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import BASE_DIR
from ..models import (
    ActualReward,
    Card,
    ExpectedReward,
    Merchant,
    RewardDiscrepancy,
    RewardRule,
    RuleExclusion,
    Statement,
    Transaction,
    User,
    UserCard,
)
from .analysis import analyze_statement_rows
from .portfolio import add_demo_user_card, get_demo_card_ids, get_user_card_ids
from .reward_engine import calculate_expected_reward, recommend_best_cards
from .card_advisor import suggest_cards_for_profile
from .statement_parser import parse_statement_file


def _count(db: Session, model: Any) -> int:
    return int(db.query(func.count()).select_from(model).scalar() or 0)


def get_dashboard_stats(db: Session, user_id: str | None = None) -> dict:
    saved_card_ids = get_user_card_ids(db, user_id) if user_id else []

    statements_q = db.query(Statement)
    transactions_q = db.query(Transaction)
    discrepancies_q = db.query(RewardDiscrepancy).join(Transaction, RewardDiscrepancy.transaction_id == Transaction.transaction_id)
    if user_id:
        statements_q = statements_q.filter(Statement.user_id == user_id)
        transactions_q = transactions_q.filter(Transaction.user_id == user_id)
        discrepancies_q = discrepancies_q.filter(Transaction.user_id == user_id)

    recent_discrepancies = discrepancies_q.order_by(RewardDiscrepancy.created_at.desc()).limit(10).all()
    total_possible_missing = Decimal("0")
    for item in recent_discrepancies:
        if item.difference_value_inr is not None:
            total_possible_missing += Decimal(str(item.difference_value_inr))

    return {
        "cards": _count(db, Card),
        "rules": _count(db, RewardRule),
        "exclusions": _count(db, RuleExclusion),
        "merchants": _count(db, Merchant),
        "statements": int(statements_q.count()),
        "transactions": int(transactions_q.count()),
        "expected_rewards": _count(db, ExpectedReward),
        "actual_rewards": _count(db, ActualReward),
        "discrepancies": int(discrepancies_q.count()),
        "saved_cards": len(saved_card_ids),
        "recent_possible_missing_inr": float(total_possible_missing),
    }


def get_card_database_rows(db: Session, q: str | None = None, limit: int = 150) -> list[dict]:
    query = db.query(Card)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (Card.card_name.ilike(pattern))
            | (Card.bank_name.ilike(pattern))
            | (Card.card_id.ilike(pattern))
            | (Card.reward_currency.ilike(pattern))
        )
    rows = query.order_by(Card.bank_name, Card.card_name).limit(limit).all()
    return [
        {
            "card_id": row.card_id,
            "bank_name": row.bank_name,
            "card_name": row.card_name,
            "annual_fee": row.annual_fee,
            "reward_currency": row.reward_currency,
            "status": row.status,
            "data_quality": row.mvp_data_quality,
            "next_action": row.mvp_next_action,
            "source_url": row.source_url,
            "rules_count": len(row.reward_rules),
        }
        for row in rows
    ]


def run_cardpilot_self_check(db: Session) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})

    try:
        stats = get_dashboard_stats(db)
        add("Database has cards", stats["cards"] > 0, f"{stats['cards']} cards loaded")
        add("Database has reward rules", stats["rules"] > 0, f"{stats['rules']} reward rules loaded")
        add("Database has merchants", stats["merchants"] >= 300, f"{stats['merchants']} merchant mappings loaded")
    except Exception as exc:
        stats = {}
        add("Database counts", False, str(exc))

    sample_csv = BASE_DIR / "data" / "sample_statement.csv"
    try:
        rows = parse_statement_file(sample_csv.name, sample_csv.read_bytes())
        add("Sample statement parser", len(rows) > 0, f"Parsed {len(rows)} sample transactions")
    except Exception as exc:
        rows = []
        add("Sample statement parser", False, str(exc))

    try:
        result = calculate_expected_reward(
            db=db,
            card_id="CC001",
            merchant_raw="Amazon",
            amount_inr=5000,
            transaction_channel="online",
            category="online shopping",
        )
        add(
            "Reward calculation engine",
            bool(result.get("rule_id")) and float(result.get("expected_value_inr") or 0) >= 0,
            f"Rule {result.get('rule_id')}; expected INR {result.get('expected_value_inr')}",
        )
    except Exception as exc:
        add("Reward calculation engine", False, str(exc))

    try:
        recommendations = recommend_best_cards(
            db=db,
            merchant_raw="Amazon",
            amount_inr=5000,
            category="online shopping",
            top_n=5,
        )
        add("Best-card recommendation", len(recommendations) > 0, f"Returned {len(recommendations)} recommendations")
    except Exception as exc:
        add("Best-card recommendation", False, str(exc))

    try:
        advisor = suggest_cards_for_profile(
            db=db,
            monthly_spend_inr=50000,
            primary_category="online shopping",
            secondary_category="travel",
            reward_preference="cashback",
            annual_fee_preference="low_fee",
            travel_frequency="sometimes",
            top_n=5,
        )
        add("Card Advisor", len(advisor.get("recommendations", [])) > 0, f"Returned {len(advisor.get('recommendations', []))} card suggestions")
    except Exception as exc:
        add("Card Advisor", False, str(exc))

    try:
        add_demo_user_card(db, "CC001", "0000")
        saved_ids = get_demo_card_ids(db)
        add("My Cards module", True, f"{len(saved_ids)} saved card(s) for profile")
    except Exception as exc:
        add("My Cards module", False, str(exc))

    try:
        if rows:
            analysis = analyze_statement_rows(
                db=db,
                card_id="CC001",
                rows=rows,
                source_name="self_check_sample_statement.csv",
                file_content=sample_csv.read_bytes(),
            )
            add(
                "Statement analysis flow",
                analysis.get("transactions_analyzed", 0) > 0,
                f"Analyzed {analysis.get('transactions_analyzed')} transactions; found {analysis.get('discrepancies_found')} possible issue(s)",
            )
        else:
            add("Statement analysis flow", False, "Skipped because parser returned no rows")
    except Exception as exc:
        add("Statement analysis flow", False, str(exc))

    passed = sum(1 for item in checks if item["ok"])
    failed = len(checks) - passed
    return {
        "app_name": "CardPilot",
        "passed": passed,
        "failed": failed,
        "checks": checks,
        "stats": stats,
    }


def get_category_options() -> list[str]:
    return [
        "online shopping",
        "grocery",
        "food delivery",
        "dining",
        "travel",
        "fuel",
        "mobility",
        "utilities",
        "telecom",
        "entertainment",
        "fashion",
        "electronics",
        "healthcare",
        "education",
        "insurance",
        "financial services",
        "rent",
        "jewellery",
        "department stores",
        "home improvement",
        "beauty wellness",
        "government taxes",
    ]


def get_merchant_dropdown_options(db: Session, limit: int = 700) -> list[dict]:
    rows = (
        db.query(Merchant)
        .order_by(Merchant.category, Merchant.normalized_merchant)
        .limit(limit)
        .all()
    )
    seen: set[tuple[str, str | None]] = set()
    options: list[dict] = []
    for row in rows:
        key = (row.normalized_merchant, row.category)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            {
                "merchant_id": row.merchant_id,
                "name": row.normalized_merchant,
                "category": row.category or "general",
                "mcc": row.mcc,
            }
        )
    return options
