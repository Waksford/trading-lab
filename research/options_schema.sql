PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS option_collection_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    feed TEXT,
    requested_underlyings TEXT NOT NULL,
    contracts_discovered INTEGER NOT NULL DEFAULT 0,
    contracts_selected INTEGER NOT NULL DEFAULT 0,
    contracts_saved INTEGER NOT NULL DEFAULT 0,
    warnings TEXT,
    errors TEXT
);

CREATE TABLE IF NOT EXISTS option_underlying_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market_date TEXT NOT NULL,
    snapshot_time_utc TEXT NOT NULL,
    snapshot_time_madrid TEXT NOT NULL,
    underlying TEXT NOT NULL,
    spot_price REAL,
    spot_available INTEGER NOT NULL DEFAULT 0,
    spot_source TEXT,
    spot_timestamp TEXT,
    selection_mode TEXT,
    daily_change_pct REAL,
    source TEXT NOT NULL DEFAULT 'ALPACA',
    feed TEXT,
    UNIQUE(run_id, underlying),
    FOREIGN KEY(run_id) REFERENCES option_collection_runs(run_id)
);

CREATE TABLE IF NOT EXISTS option_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    snapshot_time_utc TEXT NOT NULL,
    snapshot_time_madrid TEXT NOT NULL,
    market_date TEXT NOT NULL,
    underlying TEXT NOT NULL,
    underlying_price REAL,
    spot_available INTEGER NOT NULL DEFAULT 0,
    spot_source TEXT,
    spot_timestamp TEXT,
    selection_mode TEXT NOT NULL,
    selection_rank INTEGER,
    selection_reason TEXT,
    contract_symbol TEXT NOT NULL,
    expiration_date TEXT NOT NULL,
    dte INTEGER NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,
    bid REAL, ask REAL, mid REAL, last REAL,
    bid_size REAL, ask_size REAL,
    implied_volatility REAL,
    delta REAL, gamma REAL, theta REAL, vega REAL, rho REAL,
    open_interest REAL, volume REAL,
    feed TEXT,
    quote_timestamp TEXT,
    trade_timestamp TEXT,
    source TEXT NOT NULL DEFAULT 'ALPACA',
    is_call INTEGER NOT NULL,
    is_put INTEGER NOT NULL,
    moneyness_pct REAL,
    distance_from_atm_pct REAL,
    spread_abs REAL,
    spread_pct REAL,
    quote_quality TEXT NOT NULL,
    UNIQUE(run_id, contract_symbol),
    FOREIGN KEY(run_id) REFERENCES option_collection_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_option_snapshots_market_underlying
ON option_snapshots(market_date, underlying);

CREATE INDEX IF NOT EXISTS idx_option_snapshots_contract_time
ON option_snapshots(contract_symbol, snapshot_time_utc);
