from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Card, User
from ..services.auth import authenticate_user, create_access_token, create_user, get_current_user, revoke_bearer_token
from ..services.card_advisor import suggest_cards_for_profile
from ..services.portfolio import add_user_card, get_user_card_ids, list_user_cards, remove_user_card
from ..services.reward_engine import recommend_best_cards

router = APIRouter(prefix="/api", tags=["mobile-api"])


class RegisterPayload(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None
    preferred_reward_type: str | None = "cashback"


class LoginPayload(BaseModel):
    email: str
    password: str


class AddCardPayload(BaseModel):
    card_id: str
    masked_last4: str | None = None


class RecommendPayload(BaseModel):
    merchant_raw: str
    amount_inr: float = Field(gt=0)
    category: str | None = None
    use_my_cards_only: bool = True
    top_n: int = Field(default=5, ge=1, le=20)


class AdvisorPayload(BaseModel):
    monthly_spend_inr: float = Field(gt=0)
    primary_category: str
    secondary_category: str | None = None
    reward_preference: str = "cashback"
    annual_fee_preference: str = "low_fee"
    travel_frequency: str = "sometimes"


def user_payload(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "preferred_reward_type": user.preferred_reward_type,
        "is_admin": bool(user.is_admin),
    }


@router.post("/auth/register")
def api_register(payload: RegisterPayload, request: Request, db: Session = Depends(get_db)):
    try:
        user = create_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            preferred_reward_type=payload.preferred_reward_type,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = create_access_token(db, user, token_name="mobile-app")
    return {"token": token, "user": user_payload(user)}


@router.post("/auth/login")
def api_login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)):
    user = authenticate_user(db, email=payload.email, password=payload.password, request=request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(db, user, token_name="mobile-app")
    return {"token": token, "user": user_payload(user)}


@router.post("/auth/logout")
def api_logout(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("authorization", "")
    revoked = False
    if header.lower().startswith("bearer "):
        revoked = revoke_bearer_token(db, header.split(" ", 1)[1].strip())
    return {"ok": True, "revoked": revoked}


@router.get("/me")
def api_me(current_user: User = Depends(get_current_user)):
    return {"user": user_payload(current_user)}


@router.get("/cards")
def api_cards(q: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    query = db.query(Card)
    if q:
        pattern = f"%{q}%"
        query = query.filter((Card.card_name.ilike(pattern)) | (Card.bank_name.ilike(pattern)) | (Card.card_id.ilike(pattern)))
    rows = query.order_by(Card.bank_name, Card.card_name).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "card_id": c.card_id,
            "bank_name": c.bank_name,
            "card_name": c.card_name,
            "annual_fee": c.annual_fee,
            "reward_currency": c.reward_currency,
            "data_quality": c.mvp_data_quality,
        }
        for c in rows
    ]


@router.get("/my-cards")
def api_my_cards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"cards": list_user_cards(db, current_user.user_id)}


@router.post("/my-cards")
def api_add_my_card(payload: AddCardPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        add_user_card(db, current_user.user_id, payload.card_id, payload.masked_last4)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"cards": list_user_cards(db, current_user.user_id)}


@router.delete("/my-cards/{user_card_id}")
def api_remove_my_card(user_card_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        remove_user_card(db, current_user.user_id, user_card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"cards": list_user_cards(db, current_user.user_id)}


@router.post("/recommend")
def api_recommend(payload: RecommendPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card_ids = get_user_card_ids(db, current_user.user_id) if payload.use_my_cards_only else None
    if payload.use_my_cards_only and not card_ids:
        raise HTTPException(status_code=400, detail="Add at least one card first.")
    return {
        "merchant_raw": payload.merchant_raw,
        "amount_inr": payload.amount_inr,
        "recommendations": recommend_best_cards(
            db=db,
            merchant_raw=payload.merchant_raw,
            amount_inr=payload.amount_inr,
            category=payload.category,
            top_n=payload.top_n,
            card_ids=card_ids,
        ),
    }


@router.post("/advisor")
def api_advisor(payload: AdvisorPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return suggest_cards_for_profile(db=db, **payload.model_dump(), top_n=8)
