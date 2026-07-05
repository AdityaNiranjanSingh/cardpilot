from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Card
from ..schemas import CardOut

router = APIRouter(prefix="/cards", tags=["cards"])

@router.get("", response_model=list[CardOut])
def list_cards(q: str | None = Query(None), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(Card)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Card.card_name.ilike(pattern), Card.bank_name.ilike(pattern), Card.card_id.ilike(pattern)))
    cards = query.order_by(Card.bank_name, Card.card_name).limit(limit).all()
    return [CardOut(card_id=c.card_id, card_name=c.card_name, bank=c.bank_name, annual_fee=c.annual_fee, reward_currency=c.reward_currency, mvp_data_quality=c.mvp_data_quality) for c in cards]

@router.get("/{card_id}")
def get_card(card_id: str, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return {
        "card_id": card.card_id,
        "card_name": card.card_name,
        "bank": card.bank_name,
        "annual_fee": card.annual_fee,
        "reward_currency": card.reward_currency,
        "source_url": card.source_url,
        "mvp_data_quality": card.mvp_data_quality,
        "rules": [
            {
                "rule_id": r.rule_id,
                "rule_scope": r.rule_scope,
                "merchant": r.merchant,
                "merchant_category": r.merchant_category,
                "reward_type": r.reward_type,
                "reward_rate": r.reward_rate,
                "estimated_rate_pct": float(r.estimated_rate_pct) if r.estimated_rate_pct is not None else None,
                "reward_cap": r.reward_cap,
                "exclusions": r.exclusions,
                "rule_confidence": r.rule_confidence,
                "needs_manual_review": r.needs_manual_review,
            }
            for r in card.reward_rules
        ],
    }
