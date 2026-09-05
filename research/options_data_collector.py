"""OPTIONS DATA COLLECTION — PHASE 1 (solo captura point-in-time)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
from pathlib import Path
import sqlite3
import sys
import uuid
from zoneinfo import ZoneInfo

from providers.alpaca_options import AlpacaOptionsMarketDataProvider


UNDERLYINGS = ("SPX", "XSP", "VIX")
TARGET_DTES = (7, 14, 30, 60, 90)
STRIKE_BAND_PCT = 15.0
MAX_STRIKES_PER_EXPIRATION = 31
MAX_NO_SPOT_CONTRACTS = {"SPX": 1000, "XSP": 800, "VIX": 500}
BASE_DIR = Path(__file__).resolve().parent.parent
OPTIONS_DIR = BASE_DIR / "data" / "options"
DB_PATH = OPTIONS_DIR / "options_market.db"
SCHEMA_PATH = Path(__file__).with_name("options_schema.sql")
MADRID = ZoneInfo("Europe/Madrid")
NEW_YORK = ZoneInfo("America/New_York")


def initialize_database(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    migrations = {
        "option_collection_runs": {"warnings": "TEXT"},
        "option_underlying_snapshots": {
            "spot_available": "INTEGER NOT NULL DEFAULT 0", "spot_source": "TEXT",
            "spot_timestamp": "TEXT", "selection_mode": "TEXT",
        },
        "option_snapshots": {
            "spot_available": "INTEGER NOT NULL DEFAULT 0", "spot_source": "TEXT",
            "spot_timestamp": "TEXT", "selection_mode": "TEXT",
            "selection_rank": "INTEGER", "selection_reason": "TEXT",
        },
    }
    for table, columns in migrations.items():
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    connection.commit()
    return connection


def is_collection_window(now_utc):
    """Ventana conservadora: sesión regular o las dos horas posteriores."""
    local = now_utc.astimezone(NEW_YORK)
    return local.weekday() < 5 and time(9, 30) <= local.time().replace(tzinfo=None) <= time(18, 0)


def select_expirations(contracts, market_date, targets=TARGET_DTES):
    expirations = sorted({date.fromisoformat(c["expiration_date"]) for c in contracts
                          if date.fromisoformat(c["expiration_date"]) >= market_date})
    selected = []
    for target in targets:
        candidates = [expiry for expiry in expirations if expiry not in selected]
        if not candidates:
            break
        selected.append(min(candidates, key=lambda expiry: (abs((expiry - market_date).days - target), expiry)))
    return [expiry.isoformat() for expiry in selected]


def _grid_strikes(strikes, spot, maximum):
    strikes = sorted(set(float(value) for value in strikes))
    if len(strikes) <= maximum:
        return strikes
    low, high = spot * 0.85, spot * 1.15
    targets = [low + (high - low) * i / (maximum - 1) for i in range(maximum)]
    chosen = []
    for target in targets:
        available = [strike for strike in strikes if strike not in chosen]
        if not available:
            break
        chosen.append(min(available, key=lambda strike: (abs(strike - target), strike)))
    return sorted(chosen)


def select_contracts(contracts, spot, market_date, max_strikes=MAX_STRIKES_PER_EXPIRATION):
    if spot is None or float(spot) <= 0:
        return []
    expirations = select_expirations(contracts, market_date)
    selected = []
    low, high = float(spot) * 0.85, float(spot) * 1.15
    for expiry in expirations:
        group = [c for c in contracts if c["expiration_date"] == expiry
                 and low <= float(c["strike"]) <= high]
        strikes = _grid_strikes([c["strike"] for c in group], float(spot), max_strikes)
        selected.extend(c for c in group if float(c["strike"]) in strikes)
    return sorted(selected, key=lambda c: (c["expiration_date"], c["strike"], c["option_type"], c["contract_symbol"]))


def _uniform_sample(group, limit):
    group = sorted(group, key=lambda c: (float(c["strike"]), c["contract_symbol"]))
    if len(group) <= limit:
        return group
    if limit <= 1:
        return group[:limit]
    indexes = [round(i * (len(group) - 1) / (limit - 1)) for i in range(limit)]
    return [group[index] for index in indexes]


def _expiration_budgets(groups, maximum):
    """Reparte capacidad y redistribuye sobrantes de forma determinista."""
    keys = sorted(groups)
    if not keys:
        return {}, {}
    base, remainder = divmod(maximum, len(keys))
    initial = {key: base + int(index < remainder) for index, key in enumerate(keys)}
    budgets = {key: min(len(groups[key]), initial[key]) for key in keys}
    spare = maximum - sum(budgets.values())
    while spare:
        progressed = False
        for key in keys:
            if spare and budgets[key] < len(groups[key]):
                budgets[key] += 1
                spare -= 1
                progressed = True
        if not progressed:
            break
    return budgets, initial


def _select_expiration_grid(contracts, budget, used_redistribution=False):
    """Selecciona una rejilla por strike priorizando pares CALL/PUT y extremos."""
    ordered = sorted(contracts, key=lambda c: (
        float(c["strike"]), c["option_type"], c["contract_symbol"]
    ))
    if len(ordered) <= budget:
        chosen = ordered
    else:
        by_strike = {}
        for contract in ordered:
            by_strike.setdefault(float(contract["strike"]), []).append(contract)
        strikes = sorted(by_strike)
        endpoints = strikes if len(strikes) == 1 else [strikes[0], strikes[-1]]
        chosen, symbols = [], set()

        def add_strike(strike):
            unit = by_strike[strike]
            if len(chosen) + len(unit) > budget:
                return False
            chosen.extend(unit)
            symbols.update(c["contract_symbol"] for c in unit)
            return True

        for strike in endpoints:
            add_strike(strike)
        paired = [strike for strike in strikes if strike not in endpoints and
                  {c["option_type"] for c in by_strike[strike]} >= {"call", "put"}]
        pair_slots = min(len(paired), max(0, (budget - len(chosen)) // 2))
        samples = _uniform_sample(
            [{"strike": strike, "contract_symbol": str(strike)} for strike in paired],
            pair_slots,
        )
        for sample in samples:
            add_strike(float(sample["strike"]))
        remaining = [
            c for c in ordered
            if c["contract_symbol"] not in symbols
            and {item["option_type"] for item in by_strike[float(c["strike"])]}
            != {"call", "put"}
        ]
        chosen.extend(_uniform_sample(remaining, budget - len(chosen)))

    minimum = min(float(c["strike"]) for c in ordered)
    maximum = max(float(c["strike"]) for c in ordered)
    result = []
    for contract in sorted(chosen, key=lambda c: (
        float(c["strike"]), c["option_type"], c["contract_symbol"]
    )):
        row = dict(contract)
        if float(contract["strike"]) in {minimum, maximum}:
            row["selection_reason"] = "GRID_ENDPOINT"
        elif used_redistribution:
            row["selection_reason"] = "GRID_REMAINDER"
        else:
            row["selection_reason"] = "GRID_UNIFORM"
        result.append(row)
    return result


def select_contracts_no_spot(contracts, market_date, maximum=2500):
    """Limita almacenamiento sin inferir ATM, moneyness ni nivel del índice."""
    expirations = select_expirations(contracts, market_date)
    eligible = sorted(
        (c for c in contracts if c["expiration_date"] in expirations),
        key=lambda c: (c["expiration_date"], c["option_type"],
                       float(c["strike"]), c["contract_symbol"]),
    )
    groups = {}
    for contract in eligible:
        groups.setdefault(contract["expiration_date"], []).append(contract)
    budgets, initial = _expiration_budgets(groups, maximum)
    selected = []
    for expiry in sorted(groups):
        selected.extend(_select_expiration_grid(
            groups[expiry], budgets[expiry], budgets[expiry] > initial[expiry]
        ))
    selected.sort(key=lambda c: (
        c["expiration_date"], c["option_type"], float(c["strike"]), c["contract_symbol"]
    ))
    for rank, contract in enumerate(selected, start=1):
        contract["selection_rank"] = rank
    return selected


def selection_statistics(contracts):
    keys = {(c["expiration_date"], float(c["strike"]), c["option_type"])
            for c in contracts}
    return {
        "calls": sum(c["option_type"] == "call" for c in contracts),
        "puts": sum(c["option_type"] == "put" for c in contracts),
        "paired_contracts": sum(
            (expiry, strike, "put" if kind == "call" else "call") in keys
            for expiry, strike, kind in keys
        ),
        "unpaired_calls": sum(
            kind == "call" and (expiry, strike, "put") not in keys
            for expiry, strike, kind in keys
        ),
        "unpaired_puts": sum(
            kind == "put" and (expiry, strike, "call") not in keys
            for expiry, strike, kind in keys
        ),
    }


def quote_derivatives(contract, spot, market_date):
    def number(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    bid, ask = number(contract.get("bid")), number(contract.get("ask"))
    quote_time = contract.get("quote_timestamp")
    if bid is None and ask is None:
        quality = "MISSING"
    elif bid is None or bid <= 0:
        quality = "NO_BID"
    elif ask is None:
        quality = "NO_ASK"
    elif ask < bid:
        quality = "CROSSED"
    elif quote_time:
        parsed = datetime.fromisoformat(str(quote_time).replace("Z", "+00:00"))
        quality = "STALE" if parsed.astimezone(NEW_YORK).date() != market_date else "VALID"
    else:
        quality = "VALID"
    valid_mid = bid is not None and ask is not None and bid >= 0 and ask >= bid
    mid = (bid + ask) / 2 if valid_mid else None
    spread_abs = ask - bid if valid_mid else None
    spread_pct = spread_abs / mid if mid is not None and mid > 0 else None
    strike = float(contract["strike"])
    moneyness = (strike / float(spot) - 1) * 100 if spot else None
    return {"mid": mid, "spread_abs": spread_abs, "spread_pct": spread_pct,
            "quote_quality": quality, "moneyness_pct": moneyness,
            "distance_from_atm_pct": abs(moneyness) if moneyness is not None else None,
            "dte": (date.fromisoformat(contract["expiration_date"]) - market_date).days}


def chain_has_current_market_data(contracts, market_date):
    for contract in contracts:
        for field in ("quote_timestamp", "trade_timestamp"):
            value = contract.get(field)
            if not value:
                continue
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.astimezone(NEW_YORK).date() == market_date:
                return True
    return False


def _insert_run(connection, run_id, started, underlyings):
    connection.execute("""
        INSERT OR IGNORE INTO option_collection_runs
        (run_id, started_at, status, requested_underlyings)
        VALUES (?, ?, 'RUNNING', ?)
    """, (run_id, started.isoformat(), json.dumps(list(underlyings))))
    connection.commit()


def _save_underlying(connection, run_id, times, underlying, spot, feed):
    connection.execute("""
        INSERT OR IGNORE INTO option_underlying_snapshots
        (run_id, market_date, snapshot_time_utc, snapshot_time_madrid,
         underlying, spot_price, spot_available, spot_source, spot_timestamp,
         selection_mode, daily_change_pct, source, feed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ALPACA', ?)
    """, (run_id, times["market_date"], times["utc"], times["madrid"],
          underlying, spot.get("spot_price"), int(spot.get("spot_price") is not None),
          spot.get("spot_source"), spot.get("spot_timestamp"), spot.get("selection_mode"),
          spot.get("daily_change_pct"), feed))


SNAPSHOT_COLUMNS = (
    "run_id", "snapshot_time_utc", "snapshot_time_madrid", "market_date",
    "underlying", "underlying_price", "spot_available", "spot_source",
    "spot_timestamp", "selection_mode", "selection_rank", "selection_reason",
    "contract_symbol", "expiration_date",
    "dte", "strike", "option_type", "bid", "ask", "mid", "last",
    "bid_size", "ask_size", "implied_volatility", "delta", "gamma", "theta",
    "vega", "rho", "open_interest", "volume", "feed", "quote_timestamp",
    "trade_timestamp", "source", "is_call", "is_put", "moneyness_pct",
    "distance_from_atm_pct", "spread_abs", "spread_pct", "quote_quality",
)


def _save_contract(connection, run_id, times, underlying, spot_data, contract):
    spot = spot_data.get("spot_price")
    derived = quote_derivatives(contract, spot, date.fromisoformat(times["market_date"]))
    row = {**contract, **derived, "run_id": run_id,
           "snapshot_time_utc": times["utc"], "snapshot_time_madrid": times["madrid"],
           "market_date": times["market_date"], "underlying": underlying,
           "underlying_price": spot, "spot_available": int(spot is not None),
           "spot_source": spot_data.get("spot_source"),
           "spot_timestamp": spot_data.get("spot_timestamp"),
           "selection_mode": spot_data["selection_mode"],
           "is_call": int(bool(contract["is_call"])),
           "is_put": int(bool(contract["is_put"]))}
    placeholders = ",".join("?" for _ in SNAPSHOT_COLUMNS)
    cursor = connection.execute(
        f"INSERT OR IGNORE INTO option_snapshots ({','.join(SNAPSHOT_COLUMNS)}) VALUES ({placeholders})",
        tuple(row.get(column) for column in SNAPSHOT_COLUMNS),
    )
    return cursor.rowcount


def collect(provider=None, db_path=DB_PATH, now_utc=None, underlyings=UNDERLYINGS,
            run_id=None, market_window_checker=is_collection_window):
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    run_id = run_id or str(uuid.uuid4())
    market_date = now_utc.astimezone(NEW_YORK).date()
    times = {"utc": now_utc.astimezone(timezone.utc).isoformat(),
             "madrid": now_utc.astimezone(MADRID).isoformat(),
             "market_date": market_date.isoformat()}
    db_path = Path(db_path)
    db_size_before = db_path.stat().st_size if db_path.exists() else 0
    connection = initialize_database(db_path)
    _insert_run(connection, run_id, now_utc, underlyings)
    summary = {u: {"discovered": 0, "selected": 0, "saved": 0,
                   "expirations": [], "spot": None, "feed": None, "errors": [],
                   "warnings": [], "no_market_data": False,
                   "contracts_in_selected_expirations": 0, "selection_mode": None,
                   "calls": 0, "puts": 0, "paired_contracts": 0,
                   "unpaired_calls": 0, "unpaired_puts": 0,
                   "expiration_counts": {}}
               for u in underlyings}
    errors = []
    if not market_window_checker(now_utc):
        status = "NO_MARKET_DATA"
    else:
        provider = provider or AlpacaOptionsMarketDataProvider()
        for underlying in underlyings:
            item = summary[underlying]
            try:
                chain, feed_errors = provider.discover_chain(underlying)
                item["warnings"].extend(feed_errors)
                item["feed"] = chain.feed
                item["discovered"] = len(chain.snapshots)
                if chain.snapshots and not chain_has_current_market_data(chain.snapshots, market_date):
                    item["no_market_data"] = True
                    item["errors"].append("NO_MARKET_DATA: quotes/trades no pertenecen a la sesion actual")
                    errors.extend(f"{underlying}: {message}" for message in item["errors"])
                    continue
                try:
                    spot_data = provider.get_underlying_price(underlying)
                except Exception as error:
                    spot_data = {"spot_price": None, "daily_change_pct": None,
                                 "trade_timestamp": None}
                    item["warnings"].append(f"Spot no disponible: {error}")
                item["spot"] = spot_data.get("spot_price")
                spot_data["spot_source"] = "ALPACA" if item["spot"] is not None else None
                spot_data["spot_timestamp"] = spot_data.get("trade_timestamp") if item["spot"] is not None else None
                spot_data["selection_mode"] = "SPOT_BAND" if item["spot"] is not None else "NO_SPOT_GRID"
                item["selection_mode"] = spot_data["selection_mode"]
                _save_underlying(connection, run_id, times, underlying, spot_data, chain.feed)
                chosen_expirations = select_expirations(chain.snapshots, market_date)
                item["contracts_in_selected_expirations"] = sum(
                    c["expiration_date"] in chosen_expirations for c in chain.snapshots
                )
                selected = (
                    select_contracts(chain.snapshots, item["spot"], market_date)
                    if item["spot"] is not None
                    else select_contracts_no_spot(
                        chain.snapshots, market_date,
                        maximum=MAX_NO_SPOT_CONTRACTS.get(underlying, 500),
                    )
                )
                item["selected"] = len(selected)
                item["expirations"] = sorted({c["expiration_date"] for c in selected})
                item.update(selection_statistics(selected))
                item["expiration_counts"] = {
                    expiry: sum(c["expiration_date"] == expiry for c in selected)
                    for expiry in item["expirations"]
                }
                if item["spot"] is None:
                    item["warnings"].append("INDEX_SPOT_UNAVAILABLE")
                for contract in selected:
                    try:
                        item["saved"] += _save_contract(
                            connection, run_id, times, underlying, spot_data, contract
                        )
                    except Exception as error:
                        item["errors"].append(f"{contract.get('contract_symbol', 'N/A')}: {error}")
                connection.commit()
                item["saved"] = connection.execute(
                    "SELECT COUNT(*) FROM option_snapshots WHERE run_id=? AND underlying=?",
                    (run_id, underlying),
                ).fetchone()[0]
            except Exception as error:
                item["errors"].append(str(error))
            errors.extend(f"{underlying}: {message}" for message in item["errors"])
        saved = sum(item["saved"] for item in summary.values())
        succeeded = sum(not item["errors"] for item in summary.values())
        if summary and all(item["no_market_data"] for item in summary.values()):
            status = "NO_MARKET_DATA"
        else:
            status = "SUCCESS" if succeeded == len(summary) and saved else "PARTIAL" if saved else "FAILED"
    discovered = sum(item["discovered"] for item in summary.values())
    selected = sum(item["selected"] for item in summary.values())
    saved = sum(item["saved"] for item in summary.values())
    feeds = sorted({item["feed"] for item in summary.values() if item["feed"]})
    warnings = [f"{underlying}: {message}" for underlying, item in summary.items()
                for message in item["warnings"]]
    if status not in {"NO_MARKET_DATA"} and saved:
        limitations = any(item["selection_mode"] == "NO_SPOT_GRID" for item in summary.values())
        if limitations and not errors:
            status = "SUCCESS_WITH_LIMITATIONS"
    connection.execute("""
        UPDATE option_collection_runs SET finished_at=?, status=?, feed=?,
          contracts_discovered=?, contracts_selected=?, contracts_saved=?, warnings=?, errors=?
        WHERE run_id=?
    """, (datetime.now(timezone.utc).isoformat(), status, ",".join(feeds) or None,
          discovered, selected, saved, json.dumps(warnings, ensure_ascii=False),
          json.dumps(errors, ensure_ascii=False), run_id))
    total_db_rows = connection.execute("SELECT COUNT(*) FROM option_snapshots").fetchone()[0]
    connection.commit(); connection.close()
    db_size_after = db_path.stat().st_size
    estimated_rows_year = saved * 252
    bytes_per_row = db_size_after / total_db_rows if total_db_rows else 0
    return {"run_id": run_id, "status": status, "market_date": market_date.isoformat(),
            "feeds": feeds, "underlyings": summary, "warnings": warnings, "errors": errors,
            "contracts_discovered": discovered, "contracts_selected": selected,
            "contracts_saved": saved, "db_path": str(db_path.resolve()),
            "db_size_before": db_size_before, "db_size_after": db_size_after,
            "db_growth": db_size_after - db_size_before,
            "estimated_rows_year": estimated_rows_year,
            "estimated_mb_year": estimated_rows_year * bytes_per_row / 1_000_000}


def render_summary(result):
    lines = ["OPTIONS DATA COLLECTION", "=" * 40,
             f"Fecha: {result['market_date']}",
             f"Estado: {result['status']}",
             f"Feed: {', '.join(result['feeds']) if result['feeds'] else 'N/A'}"]
    for underlying, item in result["underlyings"].items():
        lines.extend(["", underlying,
                      f"  contratos descubiertos: {item['discovered']}",
                      f"  contratos en expiraciones elegidas: {item['contracts_in_selected_expirations']}",
                      f"  contratos seleccionados: {item['selected']}",
                      f"  calls / puts: {item['calls']} / {item['puts']}",
                      f"  contratos emparejados: {item['paired_contracts']}",
                      f"  calls / puts sin pareja: {item['unpaired_calls']} / {item['unpaired_puts']}",
                      f"  guardados: {item['saved']}",
                      f"  expiraciones: {', '.join(item['expirations']) or 'N/A'}",
                      "  distribución: " + (", ".join(
                          f"{expiry}={count}" for expiry, count in item['expiration_counts'].items()
                      ) or "N/A"),
                      f"  selection mode: {item['selection_mode'] or 'N/A'}",
                      f"  spot: {item['spot'] if item['spot'] is not None else 'N/A'}"])
    lines.extend(["", "Warnings:"] + ([f"- {e}" for e in result["warnings"]] or ["Ninguno"]))
    lines.extend(["", "Errores:"] + ([f"- {e}" for e in result["errors"]] or ["Ninguno"]))
    lines.extend([
        "", f"Total filas: {result['contracts_saved']}",
        f"Crecimiento DB: {result['db_growth']:,} bytes",
        f"Estimación anual: {result['estimated_rows_year']:,} filas / "
        f"{result['estimated_mb_year']:.1f} MB",
    ])
    return "\n".join(lines)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass
    result = collect()
    print(render_summary(result))


if __name__ == "__main__":
    main()
