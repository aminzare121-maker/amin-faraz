-- No fictional money balance is stored. This is an entitlement ledger only.
-- Google Play's real financial and payout reports remain the source of truth.
CREATE TABLE IF NOT EXISTS play_receipts (
 receipt_hash TEXT PRIMARY KEY,
 account_hash TEXT NOT NULL,
 product_id TEXT NOT NULL,
 subscription_state TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 is_test INTEGER NOT NULL CHECK(is_test IN (0,1)),
 verified_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS play_receipts_account_idx ON play_receipts(account_hash,expires_at);
