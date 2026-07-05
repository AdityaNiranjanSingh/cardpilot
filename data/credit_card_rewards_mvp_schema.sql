-- CardPilot MVP schema
-- Generated from user seed workbooks on 2026-07-02.
-- Use this as a PostgreSQL starting point. Keep the Excel workbook as seed/reference data.

CREATE TABLE banks (
  bank_id TEXT PRIMARY KEY,
  bank_name TEXT NOT NULL,
  source_domain TEXT,
  support_email TEXT,
  support_page_url TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE cards (
  card_id TEXT PRIMARY KEY,
  bank_id TEXT REFERENCES banks(bank_id),
  card_name TEXT NOT NULL,
  network TEXT,
  card_family TEXT,
  status TEXT,
  annual_fee TEXT,
  renewal_fee TEXT,
  fee_waiver_spend TEXT,
  forex_markup TEXT,
  reward_currency TEXT,
  reward_expiry_months TEXT,
  last_verified DATE,
  source_url TEXT,
  source_notes TEXT,
  mvp_data_quality TEXT
);

CREATE TABLE reward_rules (
  rule_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL REFERENCES cards(card_id),
  rule_scope TEXT,
  merchant TEXT,
  merchant_category TEXT,
  mcc TEXT,
  reward_type TEXT,
  reward_rate TEXT,
  reward_cap TEXT,
  cap_period TEXT,
  minimum_spend TEXT,
  effective_reward_rate TEXT,
  estimated_rate_pct NUMERIC(8,4),
  estimated_reward_on_inr_1000 NUMERIC(12,2),
  exclusions TEXT,
  valid_from DATE,
  valid_to DATE,
  rule_version TEXT DEFAULT 'v1',
  rule_confidence TEXT,
  needs_manual_review BOOLEAN,
  source_url TEXT,
  source_notes TEXT
);

CREATE TABLE rule_exclusions (
  exclusion_id TEXT PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES reward_rules(rule_id),
  card_id TEXT NOT NULL REFERENCES cards(card_id),
  exclusion_text TEXT NOT NULL,
  exclusion_category TEXT,
  source_url TEXT,
  notes TEXT
);

CREATE TABLE merchants (
  merchant_id TEXT PRIMARY KEY,
  raw_merchant_pattern TEXT NOT NULL,
  normalized_merchant TEXT NOT NULL,
  mcc TEXT,
  category TEXT,
  subcategory TEXT,
  mapping_confidence TEXT,
  last_verified DATE,
  source_url TEXT,
  source_notes TEXT
);

CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  email_hash TEXT,
  country TEXT DEFAULT 'IN',
  preferred_reward_type TEXT,
  consent_status TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE user_cards (
  user_card_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  card_id TEXT NOT NULL REFERENCES cards(card_id),
  masked_last4 TEXT,
  card_active_status TEXT,
  billing_cycle_start_day INT,
  billing_cycle_end_day INT,
  annual_fee_month TEXT,
  current_year_spend_inr NUMERIC(14,2),
  reward_balance NUMERIC(14,2),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE statements (
  statement_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  user_card_id TEXT NOT NULL REFERENCES user_cards(user_card_id),
  card_id TEXT NOT NULL REFERENCES cards(card_id),
  statement_month TEXT,
  statement_source TEXT,
  file_hash TEXT,
  parser_status TEXT,
  parser_confidence NUMERIC(5,2),
  uploaded_at TIMESTAMP DEFAULT now(),
  notes TEXT
);

CREATE TABLE transactions (
  transaction_id TEXT PRIMARY KEY,
  statement_id TEXT NOT NULL REFERENCES statements(statement_id),
  user_id TEXT NOT NULL REFERENCES users(user_id),
  user_card_id TEXT NOT NULL REFERENCES user_cards(user_card_id),
  card_id TEXT NOT NULL REFERENCES cards(card_id),
  transaction_date DATE,
  merchant_raw TEXT,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  merchant_normalized TEXT,
  amount_inr NUMERIC(14,2),
  currency TEXT DEFAULT 'INR',
  transaction_channel TEXT,
  mcc TEXT,
  category TEXT,
  is_emi BOOLEAN DEFAULT FALSE,
  is_wallet_load BOOLEAN DEFAULT FALSE,
  parser_confidence NUMERIC(5,2),
  notes TEXT
);

CREATE TABLE expected_rewards (
  expected_reward_id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
  rule_id TEXT REFERENCES reward_rules(rule_id),
  calculation_status TEXT,
  expected_reward_type TEXT,
  expected_value_inr NUMERIC(14,2),
  expected_points NUMERIC(14,2),
  cap_applied BOOLEAN,
  exclusion_applied BOOLEAN,
  calculation_explanation TEXT,
  confidence TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE actual_rewards (
  actual_reward_id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
  statement_id TEXT NOT NULL REFERENCES statements(statement_id),
  actual_reward_type TEXT,
  actual_value_inr NUMERIC(14,2),
  actual_points NUMERIC(14,2),
  posting_date DATE,
  extraction_confidence NUMERIC(5,2),
  notes TEXT
);

CREATE TABLE reward_discrepancies (
  discrepancy_id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
  expected_reward_id TEXT REFERENCES expected_rewards(expected_reward_id),
  actual_reward_id TEXT REFERENCES actual_rewards(actual_reward_id),
  expected_value_inr NUMERIC(14,2),
  actual_value_inr NUMERIC(14,2),
  difference_value_inr NUMERIC(14,2),
  discrepancy_status TEXT,
  suspected_reason TEXT,
  complaint_needed BOOLEAN,
  complaint_draft_id TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE complaint_drafts (
  complaint_draft_id TEXT PRIMARY KEY,
  discrepancy_id TEXT NOT NULL REFERENCES reward_discrepancies(discrepancy_id),
  bank TEXT,
  card_name TEXT,
  support_channel TEXT,
  subject TEXT,
  email_body TEXT,
  status TEXT,
  created_at TIMESTAMP DEFAULT now(),
  sent_at TIMESTAMP
);

CREATE TABLE consents (
  consent_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  provider TEXT,
  scopes_granted TEXT,
  purpose TEXT,
  granted_at TIMESTAMP,
  revoked_at TIMESTAMP,
  data_retention_policy TEXT,
  notes TEXT
);

CREATE INDEX idx_reward_rules_card_category ON reward_rules(card_id, merchant_category);
CREATE INDEX idx_reward_rules_mcc ON reward_rules(mcc);
CREATE INDEX idx_merchants_normalized ON merchants(normalized_merchant);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX idx_transactions_card_category ON transactions(card_id, category);
CREATE INDEX idx_expected_rewards_txn ON expected_rewards(transaction_id);
CREATE INDEX idx_actual_rewards_txn ON actual_rewards(transaction_id);
CREATE INDEX idx_discrepancies_status ON reward_discrepancies(discrepancy_status);
