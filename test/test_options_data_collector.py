import hashlib
import sqlite3
from datetime import date, datetime, timezone

import pytest

from database.db import DB_PATH as TRADING_DB_PATH
from providers.alpaca_options import (
    AlpacaEntitlementError, AlpacaOptionsMarketDataProvider, ChainResult,
    normalize_snapshot, parse_contract_symbol,
)
from research.options_data_collector import (
    MAX_NO_SPOT_CONTRACTS, collect, initialize_database, quote_derivatives,
    select_contracts, select_contracts_no_spot, select_expirations,
)


NOW = datetime(2026, 9, 2, 20, 30, tzinfo=timezone.utc)


def _contract(root, expiry, kind, strike, bid=1.0, ask=1.2, quote_time="2026-09-02T19:59:00+00:00"):
    code = "C" if kind == "call" else "P"
    symbol = f"{root}{expiry.strftime('%y%m%d')}{code}{int(strike * 1000):08d}"
    return {"contract_symbol": symbol, "root_symbol": root,
            "expiration_date": expiry.isoformat(), "strike": float(strike),
            "option_type": kind, "is_call": kind == "call", "is_put": kind == "put",
            "bid": bid, "ask": ask, "bid_size": 2, "ask_size": 3,
            "quote_timestamp": quote_time, "last": 1.1,
            "trade_timestamp": quote_time, "implied_volatility": .2,
            "delta": None, "gamma": None, "theta": None, "vega": None,
            "rho": None, "open_interest": None, "volume": None,
            "feed": "indicative", "source": "ALPACA"}


class MockProvider:
    def __init__(self, fail=()):
        self.fail = set(fail); self.calls = []

    def discover_chain(self, underlying):
        self.calls.append(("chain", underlying))
        if underlying in self.fail:
            raise RuntimeError("entitlement denied")
        spot = {"SPX": 5000, "XSP": 500, "VIX": 20}[underlying]
        contracts = []
        for days in (7, 15, 31, 61, 92):
            expiry = date(2026, 9, 2).fromordinal(date(2026, 9, 2).toordinal() + days)
            for strike in (spot * .85, spot, spot * 1.15):
                contracts.extend([_contract(underlying, expiry, "call", strike),
                                  _contract(underlying, expiry, "put", strike)])
        return ChainResult(underlying, "indicative", contracts), ["OPRA: entitlement"]

    def get_underlying_price(self, underlying):
        self.calls.append(("spot", underlying))
        return {"spot_price": {"SPX": 5000, "XSP": 500, "VIX": 20}[underlying],
                "daily_change_pct": None}


class NoSpotProvider(MockProvider):
    def get_underlying_price(self, underlying):
        self.calls.append(("spot", underlying))
        return {"spot_price": None, "trade_timestamp": None,
                "daily_change_pct": None}


def test_contract_parser_and_normalization_missing_fields():
    parsed = parse_contract_symbol("SPX260909P05000000")
    assert parsed["expiration_date"] == "2026-09-09"
    assert parsed["strike"] == 5000 and parsed["is_put"]
    snapshot = {"latest_quote": {"bid_price": 2, "ask_price": 3,
                                  "timestamp": "2026-09-02T20:00:00Z"},
                "latest_trade": None, "implied_volatility": .25, "greeks": None}
    row = normalize_snapshot("SPX260909P05000000", snapshot, "indicative")
    assert row["feed"] == "indicative" and row["source"] == "ALPACA"
    assert row["delta"] is None and row["rho"] is None
    assert row["open_interest"] is None and row["volume"] is None


def test_expirations_are_nearest_and_not_duplicated():
    market = date(2026, 9, 2)
    contracts = [_contract("XSP", date(2026, 9, day), "put", 500)
                 for day in (8, 10, 16, 30)]
    selected = select_expirations(contracts, market, targets=(7, 8, 14))
    assert selected == ["2026-09-08", "2026-09-10", "2026-09-16"]
    assert len(selected) == len(set(selected))


def test_strike_selection_uses_band_and_deterministic_grid():
    market = date(2026, 9, 2); expiry = date(2026, 9, 9)
    contracts = [_contract("XSP", expiry, kind, strike)
                 for strike in range(400, 601, 5) for kind in ("call", "put")]
    selected = select_contracts(contracts, 500, market, max_strikes=11)
    strikes = sorted({row["strike"] for row in selected})
    assert len(strikes) == 11 and min(strikes) >= 425 and max(strikes) <= 575
    assert 500 in strikes
    assert selected == select_contracts(contracts, 500, market, max_strikes=11)


def test_no_spot_grid_is_deterministic_preserves_sides_extremes_and_cap():
    market = date(2026, 9, 2)
    contracts = []
    for days in (7, 14, 30, 60, 90):
        expiry = date.fromordinal(market.toordinal() + days)
        for strike in range(1, 401):
            contracts.extend([_contract("XSP", expiry, "call", strike),
                              _contract("XSP", expiry, "put", strike)])
    first = select_contracts_no_spot(contracts, market, maximum=2500)
    second = select_contracts_no_spot(list(reversed(contracts)), market, maximum=2500)
    assert first == second and len(first) == 2500
    assert {row["option_type"] for row in first} == {"call", "put"}
    for expiry in {row["expiration_date"] for row in first}:
        for kind in ("call", "put"):
            strikes = [row["strike"] for row in first
                       if row["expiration_date"] == expiry and row["option_type"] == kind]
            assert min(strikes) == 1 and max(strikes) == 400


@pytest.mark.parametrize("underlying,limit", [("SPX", 1000), ("XSP", 800), ("VIX", 500)])
def test_no_spot_limits_by_underlying(underlying, limit):
    market = date(2026, 9, 2)
    contracts = []
    for days in (7, 14, 30, 60, 90):
        expiry = date.fromordinal(market.toordinal() + days)
        for strike in range(150):
            contracts.extend([_contract(underlying, expiry, "call", strike + 1),
                              _contract(underlying, expiry, "put", strike + 1)])
    selected = select_contracts_no_spot(
        contracts, market, maximum=MAX_NO_SPOT_CONTRACTS[underlying]
    )
    assert len(selected) == limit


def test_no_spot_budget_is_balanced_and_spare_capacity_is_redistributed():
    market = date(2026, 9, 2)
    contracts = []
    sizes = (10, 80, 80, 80, 80)
    for days, size in zip((7, 14, 30, 60, 90), sizes):
        expiry = date.fromordinal(market.toordinal() + days)
        for strike in range(size // 2):
            contracts.extend([_contract("SPX", expiry, "call", strike + 1),
                              _contract("SPX", expiry, "put", strike + 1)])
    selected = select_contracts_no_spot(contracts, market, maximum=210)
    counts = {}
    for contract in selected:
        counts[contract["expiration_date"]] = counts.get(contract["expiration_date"], 0) + 1
    assert len(selected) == 210
    assert sorted(counts.values()) == [10, 50, 50, 50, 50]
    assert any(c["selection_reason"] == "GRID_REMAINDER" for c in selected)


def test_no_spot_prioritizes_pairs_and_only_keeps_true_unpaired_contracts():
    market = date(2026, 9, 2); expiry = date(2026, 9, 9)
    contracts = []
    for strike in range(1, 51):
        contracts.extend([_contract("XSP", expiry, "call", strike),
                          _contract("XSP", expiry, "put", strike)])
    contracts.append(_contract("XSP", expiry, "call", 51))
    selected = select_contracts_no_spot(contracts, market, maximum=40)
    keys = {(c["strike"], c["option_type"]) for c in selected}
    assert all(strike == 51 or (strike, "put") in keys
               for strike, kind in keys if kind == "call")
    assert all((strike, "call") in keys for strike, kind in keys if kind == "put")


def test_no_spot_small_chain_is_complete_with_metadata_and_raw_quote_unchanged():
    market = date(2026, 9, 2); expiry = date(2026, 9, 9)
    contracts = [_contract("XSP", expiry, kind, strike, bid=2.5, ask=2.9)
                 for strike in (400, 500, 600) for kind in ("call", "put")]
    selected = select_contracts_no_spot(contracts, market, maximum=800)
    assert len(selected) == len(contracts)
    assert [c["selection_rank"] for c in selected] == list(range(1, 7))
    assert {c["selection_reason"] for c in selected} <= {
        "GRID_ENDPOINT", "GRID_UNIFORM", "GRID_REMAINDER"
    }
    assert all(c["bid"] == 2.5 and c["ask"] == 2.9 for c in selected)
    assert not any("ATM" in c["selection_reason"] for c in selected)


@pytest.mark.parametrize("bid,ask,quality,mid", [
    (1, 3, "VALID", 2), (0, 2, "NO_BID", 1), (1, None, "NO_ASK", None),
    (3, 2, "CROSSED", None), (None, None, "MISSING", None),
])
def test_mid_spread_and_quote_quality(bid, ask, quality, mid):
    row = _contract("XSP", date(2026, 9, 9), "put", 500, bid, ask)
    derived = quote_derivatives(row, 500, date(2026, 9, 2))
    assert derived["quote_quality"] == quality and derived["mid"] == mid
    if mid:
        assert derived["spread_pct"] == pytest.approx((ask - bid) / mid)


def test_stale_dte_and_moneyness():
    row = _contract("XSP", date(2026, 9, 16), "put", 450,
                    quote_time="2026-09-01T20:00:00+00:00")
    derived = quote_derivatives(row, 500, date(2026, 9, 2))
    assert derived["quote_quality"] == "STALE"
    assert derived["dte"] == 14 and derived["moneyness_pct"] == pytest.approx(-10)


def test_collection_separate_db_timestamps_feed_and_idempotence(tmp_path):
    path = tmp_path / "options_market.db"; provider = MockProvider()
    first = collect(provider, path, NOW, underlyings=("XSP",), run_id="same-run")
    second = collect(provider, path, NOW, underlyings=("XSP",), run_id="same-run")
    assert first["contracts_saved"] == second["contracts_saved"] == 30
    con = sqlite3.connect(path)
    assert con.execute("SELECT COUNT(*) FROM option_collection_runs").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM option_snapshots").fetchone()[0] == 30
    row = con.execute("SELECT feed,snapshot_time_utc,snapshot_time_madrid,source FROM option_snapshots LIMIT 1").fetchone()
    con.close()
    assert row[0] == "indicative" and row[3] == "ALPACA"
    assert "+00:00" in row[1] and "+02:00" in row[2]


def test_no_spot_stores_raw_without_inventing_atm_fields(tmp_path):
    path = tmp_path / "options_market.db"
    result = collect(NoSpotProvider(), path, NOW, underlyings=("XSP",))
    item = result["underlyings"]["XSP"]
    assert result["status"] == "SUCCESS_WITH_LIMITATIONS"
    assert item["selection_mode"] == "NO_SPOT_GRID" and item["saved"] == 30
    assert item["expirations"] == ["2026-09-09", "2026-09-17", "2026-10-03",
                                    "2026-11-02", "2026-12-03"]
    assert "XSP: INDEX_SPOT_UNAVAILABLE" in result["warnings"]
    con = sqlite3.connect(path)
    rows = con.execute("""
        SELECT underlying_price,spot_available,spot_source,spot_timestamp,
               selection_mode,moneyness_pct,distance_from_atm_pct,bid,ask,
               selection_rank,selection_reason
        FROM option_snapshots
    """).fetchall()
    underlying = con.execute("""
        SELECT spot_price,spot_available,spot_source,spot_timestamp,selection_mode
        FROM option_underlying_snapshots
    """).fetchone()
    con.close()
    assert len(rows) == 30
    assert all(row[:4] == (None, 0, None, None) for row in rows)
    assert all(row[4] == "NO_SPOT_GRID" and row[5] is None and row[6] is None for row in rows)
    assert all(row[7:9] == (1.0, 1.2) for row in rows)
    assert sorted(row[9] for row in rows) == list(range(1, 31))
    assert all(row[10] in {"GRID_ENDPOINT", "GRID_UNIFORM", "GRID_REMAINDER"}
               for row in rows)
    assert underlying == (None, 0, None, None, "NO_SPOT_GRID")


def test_error_isolation_keeps_other_underlyings(tmp_path):
    result = collect(MockProvider(fail=("SPX",)), tmp_path / "options.db", NOW)
    assert result["underlyings"]["SPX"]["saved"] == 0
    assert result["underlyings"]["XSP"]["saved"] > 0
    assert result["underlyings"]["VIX"]["saved"] > 0
    assert result["status"] == "PARTIAL"


def test_market_closed_records_run_without_calling_provider(tmp_path):
    provider = MockProvider()
    saturday = datetime(2026, 9, 5, 20, 30, tzinfo=timezone.utc)
    result = collect(provider, tmp_path / "options.db", saturday)
    assert result["status"] == "NO_MARKET_DATA" and not provider.calls
    con = sqlite3.connect(tmp_path / "options.db")
    assert con.execute("SELECT status FROM option_collection_runs").fetchone()[0] == "NO_MARKET_DATA"
    con.close()


def test_holiday_like_stale_chain_is_no_market_data(tmp_path):
    provider = MockProvider()
    original = provider.discover_chain
    def stale(underlying):
        chain, warnings = original(underlying)
        for contract in chain.snapshots:
            contract["quote_timestamp"] = "2026-09-01T20:00:00+00:00"
            contract["trade_timestamp"] = "2026-09-01T20:00:00+00:00"
        return chain, warnings
    provider.discover_chain = stale
    result = collect(provider, tmp_path / "options.db", NOW,
                     market_window_checker=lambda _now: True)
    assert result["status"] == "NO_MARKET_DATA"
    assert result["contracts_saved"] == 0
    assert not any(call[0] == "spot" for call in provider.calls)


def test_database_is_separate_and_trading_db_unchanged(tmp_path):
    before = hashlib.sha256(TRADING_DB_PATH.read_bytes()).hexdigest()
    con = initialize_database(tmp_path / "options_market.db")
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    after = hashlib.sha256(TRADING_DB_PATH.read_bytes()).hexdigest()
    assert {"option_snapshots", "option_underlying_snapshots", "option_collection_runs"} <= tables
    assert before == after


def test_provider_and_collector_have_no_order_execution_dependencies():
    source = open("providers/alpaca_options.py", encoding="utf-8").read()
    collector = open("research/options_data_collector.py", encoding="utf-8").read()
    forbidden = ("from alpaca.trading", "import alpaca.trading", ".submit_order(",
                 "paper_portfolio_live", "paper_portfolios_runner", "weekly_report")
    assert all(word not in source + collector for word in forbidden)


def test_opra_unsigned_agreement_is_classified_as_entitlement(monkeypatch):
    class Client:
        def get_option_chain(self, _request):
            raise RuntimeError('{"message":"OPRA agreement is not signed"}')
    provider = AlpacaOptionsMarketDataProvider(
        api_key="test", secret_key="test", option_client=Client(), stock_client=object()
    )
    with pytest.raises(AlpacaEntitlementError):
        provider.get_chain("SPX", "opra")
