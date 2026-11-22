
CREATE TABLE IF NOT EXISTS verified_notes(
 id TEXT PRIMARY KEY,project TEXT NOT NULL,title TEXT NOT NULL,
 content TEXT NOT NULL,source_url TEXT NOT NULL DEFAULT '',
 verified INTEGER NOT NULL CHECK(verified IN (0,1)),
 customer_visible INTEGER NOT NULL DEFAULT 0 CHECK(customer_visible IN (0,1)),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS verified_notes_scope ON verified_notes(project,verified,customer_visible);
CREATE TABLE IF NOT EXISTS ai_daily_usage(
 day TEXT NOT NULL,account_id TEXT NOT NULL,
 used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0),
 PRIMARY KEY(day,account_id)
);
