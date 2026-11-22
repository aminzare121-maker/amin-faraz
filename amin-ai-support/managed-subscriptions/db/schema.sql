-- Migrated only after installing real provider, verified payee and account secrets.
CREATE TABLE IF NOT EXISTS customers (
 id TEXT PRIMARY KEY,
 account_hash TEXT NOT NULL UNIQUE,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))
);
CREATE TABLE IF NOT EXISTS invoices (
 id TEXT PRIMARY KEY,
 customer_id TEXT NOT NULL REFERENCES customers(id),
 product TEXT NOT NULL,
 supplier_quote_id TEXT NOT NULL,
 supplier_cost_microunits INTEGER NOT NULL CHECK(supplier_cost_microunits>0),
 rent_microunits INTEGER NOT NULL CHECK(rent_microunits>=0),
 total_microunits INTEGER NOT NULL CHECK(total_microunits>0),
 created_at TEXT NOT NULL,
 quote_expires_at TEXT NOT NULL,
 destination TEXT,
 payment_tx TEXT UNIQUE,
 paid_at TEXT,
 activated_until TEXT,
 supplier_reference TEXT UNIQUE,
 state TEXT NOT NULL CHECK(state IN ('QUOTED','AWAITING_PAYMENT','PAYMENT_CONFIRMED','ACTIVE','CANCELED'))
);
CREATE INDEX IF NOT EXISTS invoice_customer ON invoices(customer_id,created_at);
CREATE INDEX IF NOT EXISTS invoice_owner_queue ON invoices(state,paid_at);
CREATE TABLE IF NOT EXISTS external_events(
 event_id TEXT PRIMARY KEY,
 event_kind TEXT NOT NULL,
 invoice_id TEXT NOT NULL REFERENCES invoices(id),
 tx_hash TEXT UNIQUE
);

-- Owner adjusts monthly rent without rebuilding client; audit is never shown to customers.
CREATE TABLE IF NOT EXISTS owner_settings(
  setting_key TEXT PRIMARY KEY,
  value_microunits INTEGER NOT NULL CHECK(value_microunits>0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS owner_settings_audit(
  id TEXT PRIMARY KEY,
  setting_key TEXT NOT NULL,
  value_microunits INTEGER NOT NULL CHECK(value_microunits>0),
  recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
