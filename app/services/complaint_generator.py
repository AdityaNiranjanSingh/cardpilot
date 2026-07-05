from __future__ import annotations

from decimal import Decimal

from ..models import Card

def draft_complaint_email(
    card: Card,
    merchant: str,
    amount_inr: Decimal | float,
    transaction_date: str | None,
    expected_value_inr: Decimal | float,
    actual_value_inr: Decimal | float,
    difference_value_inr: Decimal | float,
    rule_id: str | None,
    explanation: str | None,
) -> dict:
    subject = "Reward points/cashback discrepancy for transaction"
    body = f"""Dear Customer Care,

I would like to request a review of the reward points/cashback credited for the transaction below.

Card: {card.card_name}
Bank: {card.bank_name or card.bank_id or ''}
Transaction date: {transaction_date or 'Not available'}
Merchant: {merchant}
Transaction amount: INR {amount_inr}
Expected reward value: INR {expected_value_inr}
Reward/cashback credited: INR {actual_value_inr}
Possible difference: INR {difference_value_inr}
Rule reference used by my tracker: {rule_id or 'Not available'}

Based on the applicable reward terms available to me, this transaction appears eligible for a higher reward/cashback value. Kindly review the transaction and credit any missing reward/cashback if applicable.

Calculation note:
{explanation or 'Not available'}

Regards,
[Your Name]
"""
    return {"subject": subject, "email_body": body}
