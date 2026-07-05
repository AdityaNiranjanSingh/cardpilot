from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata

ALIASES = {
    "amzn": "amazon",
    "amazonpay": "amazon pay",
    "mmt": "makemytrip",
    "make my trip": "makemytrip",
    "bms": "bookmyshow",
}

CATEGORY_KEYWORDS = [
    ("wallet", ["wallet", "paytm wallet", "mobikwik", "amazon pay balance"]),
    ("fuel", ["fuel", "petrol", "hpcl", "iocl", "bpcl"]),
    ("rent", ["rent", "nobroker", "redgirraffe"]),
    ("utilities", ["utility", "electricity", "gas", "water", "bill payment"]),
    ("insurance", ["insurance", "lic", "premium"]),
    ("travel", ["travel", "flight", "airline", "hotel", "makemytrip", "cleartrip", "yatra", "goibibo"]),
    ("food", ["food", "restaurant", "dining", "swiggy", "zomato"]),
    ("grocery", ["grocery", "bigbasket", "grofers", "blinkit", "dmart"]),
    ("online shopping", ["online", "shopping", "amazon", "flipkart", "myntra", "ajio", "ecommerce", "e-commerce"]),
    ("offline / general", ["offline", "general", "retail", "eligible retail"]),
]

def normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    compact = text.replace(" ", "")
    for src, dst in ALIASES.items():
        if src in compact:
            text = text + " " + dst
    return text

def canonical_category(value: object | None) -> str:
    text = normalize_text(value)
    for canonical, keywords in CATEGORY_KEYWORDS:
        if any(normalize_text(k) in text for k in keywords):
            return canonical
    return text

def parse_bool(value: object | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = normalize_text(value)
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    return None

def parse_decimal(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value)
    text = text.replace(",", "")
    text = text.replace("INR", "")
    text = text.replace("Rs.", "")
    text = text.replace("Rs", "")
    text = text.replace("₹", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None

def parse_date(value: object | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if normalize_text(text) in {"unverified", "current", "ongoing", "na", "n a"}:
        return None
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None

def parse_percentage(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).lower().replace(",", "")
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        return Decimal(percent_match.group(1))
    # Common reward notation: 5 points per INR 100. Treat as rough value percentage only when explicit percentage is unavailable.
    per_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rp|points|miles|edge miles)?\s*per\s*(?:inr|rs|₹)?\s*(\d+(?:\.\d+)?)", text)
    if per_match:
        numerator = Decimal(per_match.group(1))
        denominator = Decimal(per_match.group(2))
        # This returns earn-rate units per rupee, not redemption value. Use only as fallback score.
        return (numerator / denominator) * Decimal("100")
    return None

def money_from_text(value: object | None) -> Decimal | None:
    return parse_decimal(value)

def decimal_to_float(value: object | None) -> float | None:
    if value is None:
        return None
    return float(value)
