from __future__ import annotations

from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Card, ComplaintDraft, ExpectedReward, Merchant, RewardDiscrepancy, RewardRule, Statement, Transaction, User, UserCard


def _count(db: Session, model) -> int:
    return int(db.query(func.count()).select_from(model).scalar() or 0)


def get_admin_dashboard(db: Session) -> dict:
    total_possible_missing = Decimal("0")
    for value, in db.query(RewardDiscrepancy.difference_value_inr).filter(RewardDiscrepancy.complaint_needed == True).all():  # noqa: E712
        if value is not None:
            total_possible_missing += Decimal(str(value))

    recent_users_rows = db.query(User).order_by(User.created_at.desc()).limit(12).all()
    users_rows = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    recent_statements_rows = db.query(Statement).order_by(Statement.uploaded_at.desc()).limit(12).all()
    popular_card_rows = (
        db.query(UserCard.card_id, Card.bank_name, Card.card_name, func.count(UserCard.user_card_id).label("saved_count"))
        .join(Card, UserCard.card_id == Card.card_id)
        .filter(UserCard.card_active_status == "active")
        .group_by(UserCard.card_id, Card.bank_name, Card.card_name)
        .order_by(func.count(UserCard.user_card_id).desc())
        .limit(10)
        .all()
    )

    return {
        "users": _count(db, User),
        "admins": int(db.query(func.count()).select_from(User).filter(User.is_admin == True).scalar() or 0),  # noqa: E712
        "saved_cards": _count(db, UserCard),
        "statements": _count(db, Statement),
        "transactions": _count(db, Transaction),
        "discrepancies": _count(db, RewardDiscrepancy),
        "complaints": _count(db, ComplaintDraft),
        "cards": _count(db, Card),
        "reward_rules": _count(db, RewardRule),
        "merchants": _count(db, Merchant),
        "expected_rewards": _count(db, ExpectedReward),
        "total_possible_missing": float(total_possible_missing),
        "recent_users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name,
                "is_admin": bool(u.is_admin),
                "status": u.status,
                "created_at": str(u.created_at) if u.created_at else None,
                "last_login_at": str(u.last_login_at) if u.last_login_at else None,
            }
            for u in recent_users_rows
        ],
        "users_detail": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name,
                "is_admin": bool(u.is_admin),
                "status": u.status,
                "country": u.country,
                "preferred_reward_type": u.preferred_reward_type,
                "created_at": str(u.created_at) if u.created_at else None,
                "last_login_at": str(u.last_login_at) if u.last_login_at else None,
                "saved_cards": int(db.query(func.count()).select_from(UserCard).filter(UserCard.user_id == u.user_id).scalar() or 0),
                "statements": int(db.query(func.count()).select_from(Statement).filter(Statement.user_id == u.user_id).scalar() or 0),
                "password_status": "Protected hash" if u.password_hash else "No password set",
            }
            for u in users_rows
        ],
        "recent_statements": [
            {
                "statement_id": s.statement_id,
                "user_id": s.user_id,
                "card_id": s.card_id,
                "statement_source": s.statement_source,
                "uploaded_at": str(s.uploaded_at) if s.uploaded_at else None,
                "parser_status": s.parser_status,
            }
            for s in recent_statements_rows
        ],
        "popular_cards": [
            {"card_id": r.card_id, "bank_name": r.bank_name, "card_name": r.card_name, "saved_count": int(r.saved_count or 0)}
            for r in popular_card_rows
        ],
    }
