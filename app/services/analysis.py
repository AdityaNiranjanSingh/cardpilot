from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import (
    ActualReward,
    Card,
    ComplaintDraft,
    ExpectedReward,
    RewardDiscrepancy,
    Statement,
    Transaction,
)
from ..utils import decimal_to_float
from .complaint_generator import draft_complaint_email
from .merchant_mapper import map_merchant
from .portfolio import ensure_user_card_for_analysis
from .reward_engine import calculate_expected_reward


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def analyze_statement_rows(
    db: Session,
    card_id: str,
    rows: list[dict],
    source_name: str,
    file_content: bytes | None = None,
    user_id: str = "demo_user",
) -> dict:
    card = db.get(Card, card_id)
    if not card:
        raise ValueError(f"Unknown card_id: {card_id}")
    user_card = ensure_user_card_for_analysis(db, user_id=user_id, card_id=card_id)

    statement = Statement(
        statement_id=_id("stmt"),
        user_id=user_id,
        user_card_id=user_card.user_card_id,
        card_id=card_id,
        statement_source=source_name,
        file_hash=sha256(file_content or b"").hexdigest() if file_content is not None else None,
        parser_status="parsed",
        parser_confidence=90,
    )
    db.add(statement)
    db.flush()

    result_rows = []
    discrepancies_found = 0
    total_missing = Decimal("0")

    for row in rows:
        merchant_info = map_merchant(db, row.get("merchant_raw"))
        calc = calculate_expected_reward(
            db=db,
            card_id=card_id,
            merchant_raw=row["merchant_raw"],
            amount_inr=row["amount_inr"],
            transaction_date=row.get("transaction_date"),
            transaction_channel=row.get("transaction_channel"),
            category=row.get("category") or merchant_info.get("category"),
            mcc=row.get("mcc") or merchant_info.get("mcc"),
            is_emi=row.get("is_emi", False),
            is_wallet_load=row.get("is_wallet_load", False),
        )

        txn = Transaction(
            transaction_id=_id("txn"),
            statement_id=statement.statement_id,
            user_id=user_id,
            user_card_id=user_card.user_card_id,
            card_id=card_id,
            transaction_date=row.get("transaction_date"),
            merchant_raw=row.get("merchant_raw"),
            merchant_id=merchant_info.get("merchant_id"),
            merchant_normalized=merchant_info.get("merchant_normalized"),
            amount_inr=row.get("amount_inr"),
            currency="INR",
            transaction_channel=row.get("transaction_channel"),
            mcc=row.get("mcc") or merchant_info.get("mcc"),
            category=row.get("category") or merchant_info.get("category"),
            is_emi=row.get("is_emi", False),
            is_wallet_load=row.get("is_wallet_load", False),
            parser_confidence=90,
        )
        db.add(txn)
        db.flush()

        expected = ExpectedReward(
            expected_reward_id=_id("exp"),
            transaction_id=txn.transaction_id,
            rule_id=calc.get("rule_id"),
            calculation_status="calculated" if calc.get("rule_id") else "no_rule",
            expected_reward_type=calc.get("expected_reward_type"),
            expected_value_inr=calc.get("expected_value_inr") or 0,
            expected_points=calc.get("expected_points"),
            cap_applied=calc.get("cap_applied"),
            exclusion_applied=calc.get("exclusion_applied"),
            calculation_explanation=calc.get("explanation"),
            confidence=calc.get("confidence"),
        )
        db.add(expected)
        db.flush()

        actual_present = row.get("actual_value_inr") is not None
        actual_value = row.get("actual_value_inr") if actual_present else None
        actual = ActualReward(
            actual_reward_id=_id("act"),
            transaction_id=txn.transaction_id,
            statement_id=statement.statement_id,
            actual_reward_type=calc.get("expected_reward_type") or "unknown",
            actual_value_inr=actual_value,
            extraction_confidence=85 if actual_present else 15,
            notes="Actual reward value was found in uploaded data." if actual_present else "Actual reward was not visible in this statement row; expected reward is shown for review only.",
        )
        db.add(actual)
        db.flush()

        expected_value = Decimal(str(calc.get("expected_value_inr") or 0))
        actual_decimal = Decimal(str(actual_value)) if actual_present else None
        difference = expected_value - actual_decimal if actual_decimal is not None else Decimal("0")
        threshold = max(Decimal("10"), expected_value * Decimal("0.10"))
        complaint_needed = bool(actual_present and difference > threshold and not calc.get("exclusion_applied"))
        if not actual_present:
            status = "expected_reward_only"
            suspected_reason = "Actual credited reward was not found in the uploaded statement, so CardPilot calculated expected value only."
        elif complaint_needed:
            status = "possible_missing_reward"
            suspected_reason = "Expected reward is meaningfully higher than actual reward found in uploaded data."
        else:
            status = "ok_or_needs_review"
            suspected_reason = "No significant discrepancy detected."

        discrepancy = RewardDiscrepancy(
            discrepancy_id=_id("disc"),
            transaction_id=txn.transaction_id,
            expected_reward_id=expected.expected_reward_id,
            actual_reward_id=actual.actual_reward_id,
            expected_value_inr=expected_value,
            actual_value_inr=actual_decimal,
            difference_value_inr=max(Decimal("0"), difference) if actual_present else None,
            discrepancy_status=status,
            suspected_reason=suspected_reason,
            complaint_needed=complaint_needed,
        )
        db.add(discrepancy)
        db.flush()

        complaint_draft_id = None
        complaint_subject = None
        complaint_body = None
        if complaint_needed:
            draft = draft_complaint_email(
                card=card,
                merchant=row.get("merchant_raw"),
                amount_inr=row.get("amount_inr"),
                transaction_date=str(row.get("transaction_date")),
                expected_value_inr=expected_value,
                actual_value_inr=actual_decimal,
                difference_value_inr=difference,
                rule_id=calc.get("rule_id"),
                explanation=calc.get("explanation"),
            )
            complaint = ComplaintDraft(
                complaint_draft_id=_id("cmp"),
                discrepancy_id=discrepancy.discrepancy_id,
                bank=card.bank_name,
                card_name=card.card_name,
                support_channel="copy_email_manually",
                subject=draft["subject"],
                email_body=draft["email_body"],
                status="draft",
            )
            db.add(complaint)
            db.flush()
            discrepancy.complaint_draft_id = complaint.complaint_draft_id
            complaint_draft_id = complaint.complaint_draft_id
            complaint_subject = complaint.subject
            complaint_body = complaint.email_body
            discrepancies_found += 1
            total_missing += difference

        result_rows.append({
            "transaction_id": txn.transaction_id,
            "transaction_date": str(row.get("transaction_date")),
            "merchant_raw": row.get("merchant_raw"),
            "merchant_normalized": merchant_info.get("merchant_normalized"),
            "amount_inr": decimal_to_float(row.get("amount_inr")),
            "actual_value_inr": decimal_to_float(actual_decimal),
            "actual_value_found": actual_present,
            "expected_value_inr": decimal_to_float(expected_value),
            "difference_value_inr": decimal_to_float(max(Decimal("0"), difference)) if actual_present else None,
            "status": status,
            "confidence": calc.get("confidence"),
            "rule_id": calc.get("rule_id"),
            "reward_rate": calc.get("reward_rate"),
            "explanation": calc.get("explanation"),
            "complaint_draft_id": complaint_draft_id,
            "complaint_subject": complaint_subject,
            "complaint_body": complaint_body,
        })

    db.commit()
    return {
        "statement_id": statement.statement_id,
        "card_id": card_id,
        "transactions_analyzed": len(result_rows),
        "discrepancies_found": discrepancies_found,
        "total_possible_missing_value_inr": float(total_missing),
        "rows": result_rows,
    }
