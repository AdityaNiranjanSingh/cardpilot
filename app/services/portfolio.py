from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import Card, User, UserCard

DEMO_USER_ID = "demo_user"


def ensure_demo_user(db: Session) -> User:
    user = db.get(User, DEMO_USER_ID)
    if user:
        return user
    user = User(
        user_id=DEMO_USER_ID,
        email="demo@cardpilot.local",
        email_hash="demo",
        full_name="Demo User",
        status="active",
        country="IN",
        consent_status="demo",
        notes="Self-check demo user.",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_user_cards(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.query(UserCard, Card)
        .join(Card, UserCard.card_id == Card.card_id)
        .filter(UserCard.user_id == user_id, UserCard.card_active_status == "active")
        .order_by(Card.bank_name, Card.card_name)
        .all()
    )
    return [
        {
            "user_card_id": user_card.user_card_id,
            "card_id": card.card_id,
            "bank_name": card.bank_name,
            "card_name": card.card_name,
            "masked_last4": user_card.masked_last4,
            "annual_fee": card.annual_fee,
            "reward_currency": card.reward_currency,
            "mvp_data_quality": card.mvp_data_quality,
        }
        for user_card, card in rows
    ]


def get_user_card_ids(db: Session, user_id: str) -> list[str]:
    return [
        row.card_id
        for row in db.query(UserCard).filter(UserCard.user_id == user_id, UserCard.card_active_status == "active").all()
    ]


def add_user_card(db: Session, user_id: str, card_id: str, masked_last4: str | None = None) -> UserCard:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found. Please sign in again.")
    card = db.get(Card, card_id)
    if not card:
        raise ValueError(f"Card not found: {card_id}")

    masked_last4 = (masked_last4 or "").strip()[-4:]
    existing = (
        db.query(UserCard)
        .filter(UserCard.user_id == user_id, UserCard.card_id == card_id, UserCard.card_active_status == "active")
        .first()
    )
    if existing:
        if masked_last4:
            existing.masked_last4 = masked_last4
        db.commit()
        return existing

    user_card = UserCard(
        user_card_id=f"uc_{uuid4().hex[:12]}",
        user_id=user_id,
        card_id=card_id,
        masked_last4=masked_last4 or None,
        card_active_status="active",
        notes="Added from CardPilot account dashboard.",
    )
    db.add(user_card)
    db.commit()
    db.refresh(user_card)
    return user_card


def ensure_user_card_for_analysis(db: Session, user_id: str, card_id: str) -> UserCard:
    if user_id == DEMO_USER_ID:
        ensure_demo_user(db)
    user_card = (
        db.query(UserCard)
        .filter(UserCard.user_id == user_id, UserCard.card_id == card_id, UserCard.card_active_status == "active")
        .first()
    )
    if user_card:
        return user_card
    return add_user_card(db, user_id=user_id, card_id=card_id, masked_last4=None)


def remove_user_card(db: Session, user_id: str, user_card_id: str) -> None:
    user_card = db.get(UserCard, user_card_id)
    if not user_card or user_card.user_id != user_id:
        raise ValueError("Saved card not found.")
    user_card.card_active_status = "removed"
    db.commit()


def list_demo_user_cards(db: Session) -> list[dict]:
    ensure_demo_user(db)
    return list_user_cards(db, DEMO_USER_ID)


def get_demo_card_ids(db: Session) -> list[str]:
    ensure_demo_user(db)
    return get_user_card_ids(db, DEMO_USER_ID)


def add_demo_user_card(db: Session, card_id: str, masked_last4: str | None = None) -> UserCard:
    ensure_demo_user(db)
    return add_user_card(db, DEMO_USER_ID, card_id, masked_last4)


def remove_demo_user_card(db: Session, user_card_id: str) -> None:
    return remove_user_card(db, DEMO_USER_ID, user_card_id)


def find_or_create_user_card(db: Session, user_id: str, card_id: str) -> UserCard:
    return ensure_user_card_for_analysis(db, user_id=user_id, card_id=card_id)
