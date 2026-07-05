from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Card, Merchant
from ..utils import normalize_text, parse_decimal
from .reward_engine import calculate_expected_reward

CATEGORY_OPTIONS = [
    "online shopping",
    "food delivery",
    "dining",
    "grocery",
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
    "rent",
    "jewellery",
    "department stores",
    "home improvement",
    "beauty wellness",
    "financial services",
    "government taxes",
    "offline / general",
]

REPRESENTATIVE_MERCHANTS = {
    "online shopping": "Amazon",
    "food delivery": "Swiggy",
    "dining": "EazyDiner",
    "grocery": "BigBasket",
    "travel": "MakeMyTrip",
    "fuel": "Indian Oil",
    "mobility": "Uber",
    "utilities": "Electricity Bill",
    "telecom": "Airtel",
    "entertainment": "BookMyShow",
    "fashion": "Myntra",
    "electronics": "Croma",
    "healthcare": "Apollo Pharmacy",
    "education": "Coursera",
    "insurance": "Policybazaar",
    "rent": "NoBroker Rent Pay",
    "jewellery": "Tanishq",
    "department stores": "Reliance Retail",
    "home improvement": "IKEA",
    "beauty wellness": "Cult Fit",
    "financial services": "CRED",
    "government taxes": "Income Tax",
    "offline / general": "Reliance Retail",
}

FEE_BUDGETS = {
    "no_fee": Decimal("0"),
    "low_fee": Decimal("1000"),
    "mid_fee": Decimal("3000"),
    "premium": Decimal("10000"),
    "any": None,
}


def get_category_options() -> list[str]:
    return CATEGORY_OPTIONS


def get_merchant_dropdown_options(db: Session, limit: int = 600) -> list[dict]:
    rows = (
        db.query(Merchant)
        .order_by(Merchant.category, Merchant.normalized_merchant)
        .limit(limit)
        .all()
    )
    seen = set()
    options: list[dict] = []
    for row in rows:
        name = row.normalized_merchant or row.raw_merchant_pattern
        key = normalize_text(name)
        if not name or key in seen:
            continue
        seen.add(key)
        options.append(
            {
                "name": name,
                "category": row.category or "offline / general",
                "mcc": row.mcc or "",
                "label": f"{name} - {row.category or 'general'}",
            }
        )
    return options


def parse_annual_fee(card: Card) -> Decimal:
    for value in [card.annual_fee, card.renewal_fee]:
        parsed = parse_decimal(value)
        if parsed is not None:
            return parsed
    text = normalize_text(" ".join([card.annual_fee or "", card.renewal_fee or ""]))
    if any(word in text for word in ["nil", "free", "zero", "lifetime free", "no annual fee"]):
        return Decimal("0")
    return Decimal("0")


def _fee_ok(fee: Decimal, annual_fee_preference: str) -> bool:
    budget = FEE_BUDGETS.get(annual_fee_preference, None)
    if budget is None:
        return True
    return fee <= budget


def _preference_boost(card: Card, reward_preference: str, travel_frequency: str) -> int:
    text = normalize_text(" ".join([card.card_name, card.reward_currency or "", card.card_family or "", card.source_notes or ""]))
    boost = 0
    pref = normalize_text(reward_preference)
    travel = normalize_text(travel_frequency)

    if "cashback" in pref and "cashback" in text:
        boost += 16
    if ("points" in pref or "rewards" in pref) and any(word in text for word in ["reward", "points", "rp"]):
        boost += 10
    if ("miles" in pref or "travel" in pref) and any(word in text for word in ["travel", "miles", "atlas", "vistara", "air", "hotel"]):
        boost += 18
    if travel in {"often", "frequent"} and any(word in text for word in ["travel", "lounge", "miles", "atlas", "regalia", "infinia"]):
        boost += 15
    if travel in {"rarely", "never"} and "cashback" in text:
        boost += 8
    return boost


def _card_type_label(card: Card, primary_category: str, reward_preference: str) -> str:
    text = normalize_text(" ".join([card.card_name, card.reward_currency or "", primary_category, reward_preference]))
    if "cashback" in text:
        return "Cashback card"
    if any(word in text for word in ["travel", "miles", "atlas", "regalia", "vistara", "air"]):
        return "Travel rewards card"
    if any(word in text for word in ["fuel", "bpcl", "hpcl", "indian oil"]):
        return "Fuel-focused card"
    if any(word in text for word in ["upi", "rupay"]):
        return "UPI / everyday card"
    return "Rewards card"


@dataclass
class SpendScenario:
    category: str
    weight: Decimal


def _build_scenarios(primary_category: str, secondary_category: str | None) -> list[SpendScenario]:
    secondary = secondary_category if secondary_category and secondary_category != primary_category else "offline / general"
    return [
        SpendScenario(primary_category, Decimal("0.60")),
        SpendScenario(secondary, Decimal("0.25")),
        SpendScenario("offline / general", Decimal("0.15")),
    ]


def suggest_cards_for_profile(
    db: Session,
    monthly_spend_inr: float,
    primary_category: str,
    secondary_category: str | None = None,
    reward_preference: str = "cashback",
    annual_fee_preference: str = "low_fee",
    travel_frequency: str = "sometimes",
    top_n: int = 8,
) -> dict:
    monthly_spend = Decimal(str(monthly_spend_inr or 0))
    if monthly_spend <= 0:
        raise ValueError("Monthly spend must be greater than zero.")

    scenarios = _build_scenarios(primary_category, secondary_category)
    cards = db.query(Card).filter((Card.status == None) | (Card.status.ilike("%active%"))).all()  # noqa: E711
    candidates: list[dict] = []

    for card in cards:
        fee = parse_annual_fee(card)
        if not _fee_ok(fee, annual_fee_preference):
            continue

        monthly_value = Decimal("0")
        evidence: list[str] = []
        high_confidence_hits = 0
        matched_rules = set()

        for scenario in scenarios:
            scenario_amount = monthly_spend * scenario.weight
            merchant = REPRESENTATIVE_MERCHANTS.get(scenario.category, scenario.category)
            try:
                calc = calculate_expected_reward(
                    db=db,
                    card_id=card.card_id,
                    merchant_raw=merchant,
                    amount_inr=scenario_amount,
                    transaction_date=date.today(),
                    transaction_channel="online" if scenario.category in {"online shopping", "food delivery", "travel", "utilities", "telecom", "entertainment"} else "unknown",
                    category=scenario.category,
                )
            except Exception:
                continue

            value = Decimal(str(calc.get("expected_value_inr") or 0))
            monthly_value += value
            if calc.get("rule_id"):
                matched_rules.add(calc.get("rule_id"))
                evidence.append(f"{scenario.category}: INR {value:.2f}")
                if calc.get("confidence") == "High":
                    high_confidence_hits += 1

        annual_value = monthly_value * Decimal("12")
        net_value = annual_value - fee
        boost = _preference_boost(card, reward_preference, travel_frequency)
        # Boost is intentionally small compared with rupee value. It only breaks ties
        # and makes the output more aligned with the customer preference.
        score = net_value + Decimal(boost)

        if annual_value <= 0 and not evidence:
            continue

        reason_parts = []
        if evidence:
            reason_parts.append("Estimated monthly value: " + "; ".join(evidence[:3]))
        if fee:
            reason_parts.append(f"Annual fee considered: INR {fee:.0f}")
        if reward_preference:
            reason_parts.append(f"Preference: {reward_preference}")

        candidates.append(
            {
                "card_id": card.card_id,
                "bank_name": card.bank_name,
                "card_name": card.card_name,
                "card_type": _card_type_label(card, primary_category, reward_preference),
                "annual_fee": card.annual_fee or "Not available",
                "reward_currency": card.reward_currency or "Rewards",
                "estimated_monthly_value_inr": float(monthly_value),
                "estimated_annual_value_inr": float(annual_value),
                "estimated_net_annual_value_inr": float(net_value),
                "matched_rules": len(matched_rules),
                "confidence": "High" if high_confidence_hits >= 2 else "Medium" if matched_rules else "Low",
                "score": float(score),
                "reason": ". ".join(reason_parts) or "Potential match based on available card rules.",
                "source_url": card.source_url,
            }
        )

    candidates.sort(key=lambda row: (row["score"], row["estimated_net_annual_value_inr"], row["matched_rules"]), reverse=True)
    return {
        "monthly_spend_inr": float(monthly_spend),
        "primary_category": primary_category,
        "secondary_category": secondary_category or "offline / general",
        "reward_preference": reward_preference,
        "annual_fee_preference": annual_fee_preference,
        "travel_frequency": travel_frequency,
        "recommendations": candidates[:top_n],
    }
