PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bars_1m (
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price REAL,
    change_pct REAL,
    volume REAL,
    volume_cum REAL,
    open_price REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    PRIMARY KEY (ts, symbol)
);

CREATE INDEX IF NOT EXISTS idx_bars_1m_symbol_ts ON bars_1m(symbol, ts);

CREATE TABLE IF NOT EXISTS bars_1d (
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (trade_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_bars_1d_symbol_date ON bars_1d(symbol, trade_date);

CREATE TABLE IF NOT EXISTS institutional_daily (
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    foreign_net REAL,
    trust_net REAL,
    dealer_net REAL,
    PRIMARY KEY (trade_date, symbol)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    severity INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ts, symbol, event_type, title)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    category TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    score REAL NOT NULL,
    payload_json TEXT NOT NULL,
    included_in_digest_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_pending
    ON signals(included_in_digest_at, ts);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_rule_day
    ON signals(symbol, rule_id, ts);

CREATE TABLE IF NOT EXISTS digest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_type TEXT NOT NULL,
    hour_bucket TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    signal_count INTEGER NOT NULL,
    message_id TEXT,
    UNIQUE(digest_type, hour_bucket)
);

-- US market (Taiwan-related indices / stocks)
CREATE TABLE IF NOT EXISTS us_bars (
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price REAL,
    change_pct REAL,
    volume REAL,
    open_price REAL,
    high REAL,
    low REAL,
    prev_close REAL,
    PRIMARY KEY (ts, symbol)
);

CREATE INDEX IF NOT EXISTS idx_us_bars_symbol_ts ON us_bars(symbol, ts);

CREATE TABLE IF NOT EXISTS us_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    category TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    score REAL NOT NULL,
    payload_json TEXT NOT NULL,
    included_in_digest_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_us_signals_pending
    ON us_signals(included_in_digest_at, ts);
CREATE INDEX IF NOT EXISTS idx_us_signals_symbol_rule_day
    ON us_signals(symbol, rule_id, ts);
