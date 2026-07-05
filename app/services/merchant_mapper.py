from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import Merchant
from ..utils import canonical_category, normalize_text

def _token_overlap_score(a: str, b: str) -> int:
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return 0
    overlap = len(a_tokens & b_tokens)
    return int(100 * overlap / max(len(a_tokens), len(b_tokens)))

def map_merchant(db: Session, merchant_raw: str | None) -> dict:
    raw_norm = normalize_text(merchant_raw)
    if not raw_norm:
        return {
            "merchant_id": None,
            "merchant_normalized": None,
            "category": None,
            "mcc": None,
            "confidence": "Low",
            "score": 0,
        }

    best = None
    best_score = 0
    merchants = db.query(Merchant).all()
    for merchant in merchants:
        candidates = [merchant.raw_merchant_pattern, merchant.normalized_merchant]
        candidate_norms = [normalize_text(c) for c in candidates if c]
        score = 0
        for cand in candidate_norms:
            if cand and cand == raw_norm:
                score = max(score, 100)
            elif cand and (cand in raw_norm or raw_norm in cand):
                score = max(score, 90)
            else:
                score = max(score, _token_overlap_score(raw_norm, cand))
        if score > best_score:
            best = merchant
            best_score = score

    if best and best_score >= 45:
        confidence = "High" if best_score >= 90 else "Medium"
        return {
            "merchant_id": best.merchant_id,
            "merchant_normalized": best.normalized_merchant,
            "category": best.category,
            "canonical_category": canonical_category(best.category or best.normalized_merchant),
            "mcc": best.mcc,
            "confidence": confidence,
            "score": best_score,
        }

    return {
        "merchant_id": None,
        "merchant_normalized": merchant_raw,
        "category": canonical_category(merchant_raw),
        "canonical_category": canonical_category(merchant_raw),
        "mcc": None,
        "confidence": "Low",
        "score": best_score,
    }
