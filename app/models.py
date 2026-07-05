from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Bank(Base):
    __tablename__ = "banks"

    bank_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bank_name: Mapped[str] = mapped_column(Text, nullable=False)
    card_count_in_seed: Mapped[str | None] = mapped_column(Text)
    source_domain: Mapped[str | None] = mapped_column(Text)
    support_email: Mapped[str | None] = mapped_column(Text)
    support_page_url: Mapped[str | None] = mapped_column(Text)
    mvp_status: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    cards = relationship("Card", back_populates="bank")

class Card(Base):
    __tablename__ = "cards"

    card_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bank_id: Mapped[str | None] = mapped_column(Text, ForeignKey("banks.bank_id"))
    bank_name: Mapped[str | None] = mapped_column("bank", Text)
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    network: Mapped[str | None] = mapped_column(Text)
    card_family: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    launch_date: Mapped[str | None] = mapped_column(Text)
    discontinued_date: Mapped[str | None] = mapped_column(Text)
    annual_fee: Mapped[str | None] = mapped_column(Text)
    renewal_fee: Mapped[str | None] = mapped_column(Text)
    fee_waiver_spend: Mapped[str | None] = mapped_column(Text)
    forex_markup: Mapped[str | None] = mapped_column(Text)
    reward_currency: Mapped[str | None] = mapped_column(Text)
    reward_expiry_months: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[Date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_notes: Mapped[str | None] = mapped_column(Text)
    mvp_data_quality: Mapped[str | None] = mapped_column(Text)
    mvp_next_action: Mapped[str | None] = mapped_column(Text)

    bank = relationship("Bank", back_populates="cards")
    reward_rules = relationship("RewardRule", back_populates="card")

class RewardRule(Base):
    __tablename__ = "reward_rules"

    rule_id: Mapped[str] = mapped_column(Text, primary_key=True)
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.card_id"), nullable=False)
    card_name: Mapped[str | None] = mapped_column(Text)
    bank_id: Mapped[str | None] = mapped_column(Text)
    bank: Mapped[str | None] = mapped_column(Text)
    rule_scope: Mapped[str | None] = mapped_column(Text)
    merchant: Mapped[str | None] = mapped_column(Text)
    merchant_category: Mapped[str | None] = mapped_column(Text)
    mcc: Mapped[str | None] = mapped_column(Text)
    reward_type: Mapped[str | None] = mapped_column(Text)
    reward_rate: Mapped[str | None] = mapped_column(Text)
    reward_cap: Mapped[str | None] = mapped_column(Text)
    cap_period: Mapped[str | None] = mapped_column(Text)
    minimum_spend: Mapped[str | None] = mapped_column(Text)
    effective_reward_rate: Mapped[str | None] = mapped_column(Text)
    estimated_rate_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    estimated_reward_on_inr_1000: Mapped[float | None] = mapped_column(Numeric(12, 2))
    exclusions: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[Date | None] = mapped_column(Date)
    valid_to: Mapped[Date | None] = mapped_column(Date)
    rule_version: Mapped[str | None] = mapped_column(Text, default="v1")
    rule_confidence: Mapped[str | None] = mapped_column(Text)
    needs_manual_review: Mapped[bool | None] = mapped_column(Boolean)
    numeric_parse_note: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_notes: Mapped[str | None] = mapped_column(Text)

    card = relationship("Card", back_populates="reward_rules")
    exclusions_rows = relationship("RuleExclusion", back_populates="rule")

class RuleExclusion(Base):
    __tablename__ = "rule_exclusions"

    exclusion_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rule_id: Mapped[str] = mapped_column(Text, ForeignKey("reward_rules.rule_id"), nullable=False)
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.card_id"), nullable=False)
    card_name: Mapped[str | None] = mapped_column(Text)
    exclusion_text: Mapped[str] = mapped_column(Text, nullable=False)
    exclusion_category: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    rule = relationship("RewardRule", back_populates="exclusions_rows")

class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_merchant_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_merchant: Mapped[str] = mapped_column(Text, nullable=False)
    mcc: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    subcategory: Mapped[str | None] = mapped_column(Text)
    mapping_confidence: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[Date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_notes: Mapped[str | None] = mapped_column(Text)
    mvp_next_action: Mapped[str | None] = mapped_column(Text)

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True, index=True)
    email_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(Text, default="active")
    country: Mapped[str | None] = mapped_column(Text, default="IN")
    preferred_reward_type: Mapped[str | None] = mapped_column(Text)
    consent_status: Mapped[str | None] = mapped_column(Text)
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)

    cards = relationship("UserCard", back_populates="user")

class UserAccessToken(Base):
    __tablename__ = "user_access_tokens"

    token_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)
    token_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime)
    last_used_at: Mapped[DateTime | None] = mapped_column(DateTime)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.user_id"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_summary: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class UserCard(Base):
    __tablename__ = "user_cards"

    user_card_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.card_id"), nullable=False)
    masked_last4: Mapped[str | None] = mapped_column(Text)
    card_active_status: Mapped[str | None] = mapped_column(Text)
    billing_cycle_start_day: Mapped[int | None] = mapped_column()
    billing_cycle_end_day: Mapped[int | None] = mapped_column()
    annual_fee_month: Mapped[str | None] = mapped_column(Text)
    current_year_spend_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    reward_balance: Mapped[float | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="cards")
    card = relationship("Card")

class Statement(Base):
    __tablename__ = "statements"

    statement_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    user_card_id: Mapped[str] = mapped_column(Text, ForeignKey("user_cards.user_card_id"), nullable=False)
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.card_id"), nullable=False)
    statement_month: Mapped[str | None] = mapped_column(Text)
    statement_source: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(Text)
    parser_status: Mapped[str | None] = mapped_column(Text)
    parser_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(Text, primary_key=True)
    statement_id: Mapped[str] = mapped_column(Text, ForeignKey("statements.statement_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    user_card_id: Mapped[str] = mapped_column(Text, ForeignKey("user_cards.user_card_id"), nullable=False)
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.card_id"), nullable=False)
    transaction_date: Mapped[Date | None] = mapped_column(Date)
    merchant_raw: Mapped[str | None] = mapped_column(Text)
    merchant_id: Mapped[str | None] = mapped_column(Text, ForeignKey("merchants.merchant_id"))
    merchant_normalized: Mapped[str | None] = mapped_column(Text)
    amount_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(Text, default="INR")
    transaction_channel: Mapped[str | None] = mapped_column(Text)
    mcc: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    is_emi: Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_wallet_load: Mapped[bool | None] = mapped_column(Boolean, default=False)
    parser_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)

class ExpectedReward(Base):
    __tablename__ = "expected_rewards"

    expected_reward_id: Mapped[str] = mapped_column(Text, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(Text, ForeignKey("transactions.transaction_id"), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(Text, ForeignKey("reward_rules.rule_id"))
    calculation_status: Mapped[str | None] = mapped_column(Text)
    expected_reward_type: Mapped[str | None] = mapped_column(Text)
    expected_value_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    expected_points: Mapped[float | None] = mapped_column(Numeric(14, 2))
    cap_applied: Mapped[bool | None] = mapped_column(Boolean)
    exclusion_applied: Mapped[bool | None] = mapped_column(Boolean)
    calculation_explanation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class ActualReward(Base):
    __tablename__ = "actual_rewards"

    actual_reward_id: Mapped[str] = mapped_column(Text, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(Text, ForeignKey("transactions.transaction_id"), nullable=False)
    statement_id: Mapped[str] = mapped_column(Text, ForeignKey("statements.statement_id"), nullable=False)
    actual_reward_type: Mapped[str | None] = mapped_column(Text)
    actual_value_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    actual_points: Mapped[float | None] = mapped_column(Numeric(14, 2))
    posting_date: Mapped[Date | None] = mapped_column(Date)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)

class RewardDiscrepancy(Base):
    __tablename__ = "reward_discrepancies"

    discrepancy_id: Mapped[str] = mapped_column(Text, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(Text, ForeignKey("transactions.transaction_id"), nullable=False)
    expected_reward_id: Mapped[str | None] = mapped_column(Text, ForeignKey("expected_rewards.expected_reward_id"))
    actual_reward_id: Mapped[str | None] = mapped_column(Text, ForeignKey("actual_rewards.actual_reward_id"))
    expected_value_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    actual_value_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    difference_value_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    discrepancy_status: Mapped[str | None] = mapped_column(Text)
    suspected_reason: Mapped[str | None] = mapped_column(Text)
    complaint_needed: Mapped[bool | None] = mapped_column(Boolean)
    complaint_draft_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class ComplaintDraft(Base):
    __tablename__ = "complaint_drafts"

    complaint_draft_id: Mapped[str] = mapped_column(Text, primary_key=True)
    discrepancy_id: Mapped[str] = mapped_column(Text, ForeignKey("reward_discrepancies.discrepancy_id"), nullable=False)
    bank: Mapped[str | None] = mapped_column(Text)
    card_name: Mapped[str | None] = mapped_column(Text)
    support_channel: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    email_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    sent_at: Mapped[DateTime | None] = mapped_column(DateTime)

class Consent(Base):
    __tablename__ = "consents"

    consent_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    scopes_granted: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[DateTime | None] = mapped_column(DateTime)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime)
    data_retention_policy: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

Index("idx_reward_rules_card_category", RewardRule.card_id, RewardRule.merchant_category)
Index("idx_reward_rules_mcc", RewardRule.mcc)
Index("idx_merchants_normalized", Merchant.normalized_merchant)
Index("idx_transactions_user_date", Transaction.user_id, Transaction.transaction_date)
Index("idx_transactions_card_category", Transaction.card_id, Transaction.category)
Index("idx_expected_rewards_txn", ExpectedReward.transaction_id)
Index("idx_actual_rewards_txn", ActualReward.transaction_id)
Index("idx_discrepancies_status", RewardDiscrepancy.discrepancy_status)

Index("idx_users_email", User.email)
Index("idx_user_cards_user", UserCard.user_id)
Index("idx_user_tokens_hash", UserAccessToken.token_hash)
Index("idx_audit_events_user_type", AuditEvent.user_id, AuditEvent.event_type)
