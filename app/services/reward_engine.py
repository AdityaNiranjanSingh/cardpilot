from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session

from ..models import Card, RewardRule, RuleExclusion
from ..utils import canonical_category, money_from_text, normalize_text, parse_decimal, parse_percentage
from .merchant_mapper import map_merchant

GENERAL_CATEGORY_HINTS = {"offline general", "all eligible retail", "all other eligible spends", "base", "default", "regular spends", "other spends"}

def _to_decimal(value: object | None, default: str = "0") -> Decimal:
    parsed = parse_decimal(value)
    return parsed if parsed is not None else Decimal(default)

def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _date_ok(rule: RewardRule, tx_date: date | None) -> bool:
    if tx_date is None:
        return True
    if rule.valid_from and tx_date < rule.valid_from:
        return False
    if rule.valid_to and tx_date > rule.valid_to:
        return False
    return True

def _minimum_spend_ok(rule: RewardRule, amount: Decimal) -> bool:
    minimum = money_from_text(rule.minimum_spend)
    if minimum is None:
        return True
    return amount >= minimum

def _rate_pct(rule: RewardRule) -> Decimal:
    if rule.estimated_rate_pct is not None:
        return Decimal(str(rule.estimated_rate_pct))
    for field in [rule.effective_reward_rate, rule.reward_rate]:
        parsed = parse_percentage(field)
        if parsed is not None:
            return parsed
    return Decimal("0")

def _category_match_score(rule_category: str | None, tx_category: str | None) -> int:
    if not rule_category or not tx_category:
        return 0
    rule_norm = normalize_text(rule_category)
    tx_norm = normalize_text(tx_category)
    rule_canon = canonical_category(rule_category)
    tx_canon = canonical_category(tx_category)

    if rule_norm == tx_norm:
        return 85
    if rule_canon and tx_canon and rule_canon == tx_canon:
        return 80
    if rule_norm in tx_norm or tx_norm in rule_norm:
        return 65
    if any(hint in rule_norm for hint in GENERAL_CATEGORY_HINTS):
        return 15
    return 0

def _merchant_match_score(rule_merchant: str | None, raw: str | None, normalized: str | None) -> int:
    if not rule_merchant:
        return 0
    rule_norm = normalize_text(rule_merchant)
    raw_norm = normalize_text(raw)
    normalized_norm = normalize_text(normalized)
    if rule_norm in raw_norm or raw_norm in rule_norm:
        return 100
    if rule_norm in normalized_norm or normalized_norm in rule_norm:
        return 100
    # Partner lists often contain slash-separated merchants. Token overlap helps catch these.
    rule_tokens = set(rule_norm.split())
    tx_tokens = set((raw_norm + " " + normalized_norm).split())
    if not rule_tokens or not tx_tokens:
        return 0
    overlap = len(rule_tokens & tx_tokens)
    if overlap:
        return min(95, 50 + overlap * 10)
    return 0

def _rule_match_score(rule: RewardRule, merchant_raw: str, merchant_info: dict, tx_category: str | None, mcc: str | None) -> int:
    score = 0
    score = max(score, _merchant_match_score(rule.merchant, merchant_raw, merchant_info.get("merchant_normalized")))

    categories_to_try = [tx_category, merchant_info.get("category"), merchant_info.get("canonical_category")]
    for category in categories_to_try:
        score = max(score, _category_match_score(rule.merchant_category, category))

    if mcc and rule.mcc and normalize_text(mcc) in normalize_text(rule.mcc):
        score = max(score, 75)

    scope = normalize_text(rule.rule_scope)
    rule_cat = normalize_text(rule.merchant_category)
    if score == 0 and ("default" in scope or "category" in scope or any(h in rule_cat for h in GENERAL_CATEGORY_HINTS)):
        score = 10

    return score

def _exclusion_reason(rule: RewardRule, exclusions: list[RuleExclusion], tx: dict) -> str | None:
    tx_category = canonical_category(tx.get("category"))
    merchant_text = normalize_text(tx.get("merchant_raw"))
    combined = normalize_text(" ".join([rule.exclusions or "", rule.reward_cap or "", rule.source_notes or ""]))

    if tx.get("is_emi") and "emi" in combined:
        return "EMI transactions appear excluded by this rule."
    if tx.get("is_wallet_load") and "wallet" in combined:
        return "Wallet load transactions appear excluded by this rule."

    for row in exclusions:
        ex_cat = canonical_category(row.exclusion_category or row.exclusion_text)
        ex_text = normalize_text(row.exclusion_text)
        if tx.get("is_emi") and "emi" in ex_text:
            return f"Excluded category: {row.exclusion_text}"
        if tx.get("is_wallet_load") and "wallet" in ex_text:
            return f"Excluded category: {row.exclusion_text}"
        if ex_cat and ex_cat in tx_category and ex_cat not in {"offline general", "online shopping"}:
            return f"Excluded category: {row.exclusion_text}"
        if ex_text and len(ex_text) > 3 and ex_text in merchant_text:
            return f"Excluded merchant/category: {row.exclusion_text}"
    return None

def _apply_simple_transaction_cap(rule: RewardRule, expected_value: Decimal) -> tuple[Decimal, bool, str | None]:
    cap = money_from_text(rule.reward_cap)
    cap_period = normalize_text(rule.cap_period)
    cap_text = normalize_text(rule.reward_cap)
    if cap is None:
        return expected_value, False, None
    if "transaction" in cap_period or "per transaction" in cap_text:
        if expected_value > cap:
            return cap, True, f"Applied per-transaction cap of INR {cap}."
    return expected_value, False, None

def calculate_expected_reward(
    db: Session,
    card_id: str,
    merchant_raw: str,
    amount_inr: float | Decimal,
    transaction_date: date | None = None,
    transaction_channel: str | None = None,
    category: str | None = None,
    mcc: str | None = None,
    is_emi: bool = False,
    is_wallet_load: bool = False,
) -> dict:
    card = db.get(Card, card_id)
    if not card:
        raise ValueError(f"Unknown card_id: {card_id}")

    amount = _to_decimal(amount_inr)
    merchant_info = map_merchant(db, merchant_raw)
    tx_category = category or merchant_info.get("category") or merchant_info.get("canonical_category")

    rules = db.query(RewardRule).filter(RewardRule.card_id == card_id).all()
    candidates: list[tuple[int, Decimal, RewardRule]] = []
    for rule in rules:
        if not _date_ok(rule, transaction_date):
            continue
        if not _minimum_spend_ok(rule, amount):
            continue
        score = _rule_match_score(rule, merchant_raw, merchant_info, tx_category, mcc)
        if score <= 0:
            continue
        candidates.append((score, _rate_pct(rule), rule))

    if not candidates:
        return {
            "card_id": card.card_id,
            "card_name": card.card_name,
            "merchant_raw": merchant_raw,
            "merchant_normalized": merchant_info.get("merchant_normalized"),
            "merchant_category": tx_category,
            "amount_inr": float(amount),
            "expected_reward_type": None,
            "expected_value_inr": 0.0,
            "expected_points": None,
            "rule_id": None,
            "rule_name": None,
            "reward_rate": None,
            "cap_applied": False,
            "exclusion_applied": False,
            "confidence": "Low",
            "explanation": "No matching reward rule found for this card and transaction.",
            "source_url": None,
        }

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    score, rate_pct, rule = candidates[0]
    exclusions = db.query(RuleExclusion).filter(RuleExclusion.rule_id == rule.rule_id).all()
    exclusion_reason = _exclusion_reason(
        rule,
        exclusions,
        {
            "merchant_raw": merchant_raw,
            "category": tx_category,
            "is_emi": is_emi,
            "is_wallet_load": is_wallet_load,
        },
    )

    if exclusion_reason:
        confidence = "High" if score >= 80 else "Medium"
        return {
            "card_id": card.card_id,
            "card_name": card.card_name,
            "merchant_raw": merchant_raw,
            "merchant_normalized": merchant_info.get("merchant_normalized"),
            "merchant_category": tx_category,
            "amount_inr": float(amount),
            "expected_reward_type": rule.reward_type,
            "expected_value_inr": 0.0,
            "expected_points": None,
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_scope,
            "reward_rate": rule.reward_rate,
            "cap_applied": False,
            "exclusion_applied": True,
            "confidence": confidence,
            "explanation": exclusion_reason,
            "source_url": rule.source_url,
        }

    expected_value = _round_money(amount * rate_pct / Decimal("100"))
    expected_value, cap_applied, cap_explanation = _apply_simple_transaction_cap(rule, expected_value)

    confidence_parts = []
    if score >= 80:
        confidence_parts.append("merchant/category match")
    if rule.rule_confidence:
        confidence_parts.append(f"rule confidence: {rule.rule_confidence}")
    if rule.needs_manual_review:
        confidence = "Medium" if score >= 80 else "Low"
    else:
        confidence = "High" if score >= 80 else "Medium"

    explanation = f"Applied rule {rule.rule_id}: {rule.reward_rate or rate_pct} on INR {amount}. Estimated reward value = INR {expected_value}."
    if cap_explanation:
        explanation += " " + cap_explanation
    if confidence_parts:
        explanation += " Evidence: " + "; ".join(confidence_parts) + "."

    return {
        "card_id": card.card_id,
        "card_name": card.card_name,
        "merchant_raw": merchant_raw,
        "merchant_normalized": merchant_info.get("merchant_normalized"),
        "merchant_category": tx_category,
        "amount_inr": float(amount),
        "expected_reward_type": rule.reward_type,
        "expected_value_inr": float(expected_value),
        "expected_points": None,
        "rule_id": rule.rule_id,
        "rule_name": rule.rule_scope,
        "reward_rate": rule.reward_rate,
        "cap_applied": cap_applied,
        "exclusion_applied": False,
        "confidence": confidence,
        "explanation": explanation,
        "source_url": rule.source_url,
    }

def recommend_best_cards(
    db: Session,
    merchant_raw: str,
    amount_inr: float,
    transaction_date: date | None = None,
    transaction_channel: str | None = None,
    category: str | None = None,
    mcc: str | None = None,
    top_n: int = 5,
    card_ids: list[str] | None = None,
) -> list[dict]:
    query = db.query(Card).filter((Card.status == None) | (Card.status.ilike("%active%")))  # noqa: E711
    if card_ids:
        query = query.filter(Card.card_id.in_(card_ids))
    cards = query.all()

    results = []
    for card in cards:
        try:
            result = calculate_expected_reward(
                db=db,
                card_id=card.card_id,
                merchant_raw=merchant_raw,
                amount_inr=amount_inr,
                transaction_date=transaction_date,
                transaction_channel=transaction_channel,
                category=category,
                mcc=mcc,
            )
            if result["rule_id"]:
                result["annual_fee"] = card.annual_fee
                result["bank_name"] = card.bank_name
                results.append(result)
        except Exception:
            continue
    results.sort(key=lambda row: (row.get("expected_value_inr") or 0, row.get("confidence") == "High"), reverse=True)
    return results[:top_n]
