from datetime import date
from pydantic import BaseModel, Field

class CardOut(BaseModel):
    card_id: str
    card_name: str
    bank: str | None = None
    annual_fee: str | None = None
    reward_currency: str | None = None
    mvp_data_quality: str | None = None

class RewardCalculationRequest(BaseModel):
    card_id: str
    merchant_raw: str
    amount_inr: float = Field(gt=0)
    transaction_date: date | None = None
    transaction_channel: str | None = None
    category: str | None = None
    mcc: str | None = None
    is_emi: bool = False
    is_wallet_load: bool = False

class RewardCalculationResponse(BaseModel):
    card_id: str
    card_name: str | None = None
    merchant_raw: str
    merchant_normalized: str | None = None
    merchant_category: str | None = None
    amount_inr: float
    expected_reward_type: str | None = None
    expected_value_inr: float
    expected_points: float | None = None
    rule_id: str | None = None
    rule_name: str | None = None
    reward_rate: str | None = None
    cap_applied: bool = False
    exclusion_applied: bool = False
    confidence: str
    explanation: str
    source_url: str | None = None

class BestCardRequest(BaseModel):
    merchant_raw: str
    amount_inr: float = Field(gt=0)
    transaction_date: date | None = None
    transaction_channel: str | None = None
    category: str | None = None
    mcc: str | None = None
    top_n: int = Field(default=5, ge=1, le=20)
    card_ids: list[str] | None = None

class StatementUploadResult(BaseModel):
    statement_id: str
    card_id: str
    transactions_analyzed: int
    discrepancies_found: int
    total_possible_missing_value_inr: float
    rows: list[dict]
