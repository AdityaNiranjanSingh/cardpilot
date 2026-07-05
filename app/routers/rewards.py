from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BestCardRequest, RewardCalculationRequest, RewardCalculationResponse
from ..services.reward_engine import calculate_expected_reward, recommend_best_cards

router = APIRouter(prefix="/rewards", tags=["rewards"])

@router.post("/calculate", response_model=RewardCalculationResponse)
def calculate_reward(payload: RewardCalculationRequest, db: Session = Depends(get_db)):
    try:
        return calculate_expected_reward(db=db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/recommend-best-card")
def recommend_best_card(payload: BestCardRequest, db: Session = Depends(get_db)):
    return {
        "merchant_raw": payload.merchant_raw,
        "amount_inr": payload.amount_inr,
        "recommendations": recommend_best_cards(db=db, **payload.model_dump()),
    }
