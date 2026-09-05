"""Registro descriptivo y reproducible de experimentos de trading-lab.

La configuracion contiene decisiones humanas congeladas. Las muestras se leen
de los resumenes existentes; este modulo no crea tablas ni escribe en SQLite.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
import sys

from database.db import (
    obtener_conexion,
    obtener_resumen_paper,
    obtener_resumen_paper_portfolios,
)


CONFIG_PATH = Path(__file__).with_name("experiment_registry.json")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "research" / "experiment_status.json"
VALID_TYPES = {"strategy", "research", "forward_candidate"}
VALID_STATUSES = {"ACTIVE_OOS", "ACTIVE_FORWARD", "WAITING_FOR_DATA",
                  "COMPLETED", "REJECTED", "FROZEN"}
NA = "N/A"


def load_config(path=CONFIG_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = set()
    for experiment in data.get("experiments", []):
        if experiment["id"] in ids:
            raise ValueError(f"ID de experimento duplicado: {experiment['id']}")
        ids.add(experiment["id"])
        if experiment["type"] not in VALID_TYPES:
            raise ValueError(f"Tipo invalido: {experiment['type']}")
        if experiment["status"] not in VALID_STATUSES:
            raise ValueError(f"Estado invalido: {experiment['status']}")
    return data


def days_since_activation(activation_date, current_date):
    if not activation_date or activation_date == NA:
        return NA
    activated = date.fromisoformat(str(activation_date))
    today = current_date if isinstance(current_date, date) else date.fromisoformat(str(current_date))
    return max(0, (today - activated).days)


def summarize_paper(summary):
    signals_total = sum(int(row.get("cantidad") or 0) for row in summary.get("senales", []))
    mature = {5: 0, 20: 0, 60: 0}
    for row in summary.get("resultados", []):
        horizon = int(row.get("horizonte") or 0)
        if horizon in mature:
            mature[horizon] += int(row.get("cantidad") or 0)
    return {"signals_total": signals_total, "mature_5d": mature[5],
            "mature_20d": mature[20], "mature_60d": mature[60]}


def _database_dates(sources):
    """Lee solo fechas identificativas; no ejecuta ninguna migracion."""
    output = {}
    connection = obtener_conexion()
    try:
        cursor = connection.cursor()
        for source in sources:
            kind = source.get("kind")
            if kind in {"paper", "signal_interaction"}:
                key = (source.get("strategy"), source.get("score_version"), source.get("variant"))
                if key in output:
                    continue
                row = cursor.execute("""
                    SELECT MIN(market_date) AS first_signal_date
                    FROM paper_signals
                    WHERE strategy = ? AND source_score_version = ? AND variant = ?
                """, key).fetchone()
                output[key] = dict(row) if row else {"first_signal_date": None}
            if source.get("portfolio"):
                name = source.get("portfolio")
                row = cursor.execute("""
                    SELECT p.portfolio_type,
                           (SELECT MIN(pp.entry_date)
                            FROM paper_portfolio_positions pp
                            WHERE pp.portfolio_id = p.id) AS first_position_date,
                           (SELECT MIN(r.execution_date)
                            FROM paper_portfolio_rebalances r
                            WHERE r.portfolio_id = p.id) AS first_rebalance_date
                    FROM paper_portfolios p WHERE p.name = ?
                """, (name,)).fetchone()
                if row:
                    values = dict(row)
                    first_execution = (
                        values["first_rebalance_date"]
                        if values["portfolio_type"] == "FORWARD_ETF"
                        else values["first_position_date"]
                    )
                else:
                    first_execution = None
                output[("portfolio", name)] = {"first_execution_date": first_execution}
    finally:
        connection.close()
    return output


def _warnings(experiment, current_date):
    warnings = []
    start = experiment.get("review_window_start")
    if start and start != NA and current_date < date.fromisoformat(start):
        warnings.append("FROZEN — review window not reached")
    sample = experiment["sample"]
    if experiment["id"] == "SIGNAL_INTERACTION_PHASE1" and (
        sample["mature_20d"] in (0, NA) or sample["mature_60d"] in (0, NA)
    ):
        warnings.append("INSUFFICIENT MATURITY")
    elif experiment["type"] == "strategy" and (
        sample["mature_20d"] == 0 or sample["mature_60d"] == 0
    ):
        warnings.append("INSUFFICIENT MATURITY")
    return warnings


def build_registry(current_date=None, config=None, paper_provider=obtener_resumen_paper,
                   portfolios_provider=obtener_resumen_paper_portfolios,
                   dates_provider=_database_dates):
    today = current_date or date.today()
    if isinstance(today, str):
        today = date.fromisoformat(today)
    config = deepcopy(config or load_config())
    experiments = config["experiments"]
    sources = [item.get("data_source", {}) for item in experiments]
    dates = dates_provider(sources)
    portfolios = {item["name"]: item for item in portfolios_provider()}

    paper_cache = {}
    for experiment in experiments:
        source = experiment.pop("data_source", {})
        kind = source.get("kind")
        sample = {"signals_total": NA, "mature_5d": NA, "mature_20d": NA,
                  "mature_60d": NA, "open_positions": NA, "closed_trades": NA,
                  "days_since_activation": days_since_activation(experiment.get("activation_date"), today)}
        first_signal = first_execution = NA
        if kind in {"paper", "signal_interaction"}:
            key = (source["strategy"], source["score_version"], source["variant"])
            if key not in paper_cache:
                paper_cache[key] = summarize_paper(paper_provider(
                    strategy=key[0], source_score_version=key[1], variant=key[2]))
            sample.update(paper_cache[key])
            first_signal = dates.get(key, {}).get("first_signal_date") or NA
        if source.get("portfolio"):
            portfolio = portfolios.get(source["portfolio"])
            if portfolio:
                sample["open_positions"] = len(portfolio.get("abiertas", []))
                sample["closed_trades"] = int(portfolio.get("cerradas") or 0)
            first_execution = dates.get(("portfolio", source["portfolio"]), {}).get("first_execution_date") or NA
        experiment["first_signal_date"] = first_signal
        experiment["first_execution_date"] = first_execution
        experiment["sample"] = sample
        experiment["ready_for_phase2"] = (
            False if experiment["id"] == "SIGNAL_INTERACTION_PHASE1" else NA
        )
        experiment["warnings"] = _warnings(experiment, today)

    return {"schema_version": config.get("schema_version", 1),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": today.isoformat(), "experiments": experiments}


def write_status(registry, path=OUTPUT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_console(registry):
    lines = ["TRADING LAB — EXPERIMENT STATUS", "=" * 42]
    for item in registry["experiments"]:
        sample = item["sample"]
        lines.extend(["", item["display_name"],
                      f"  Status: {item['status']}", f"  Version: {item['version']}",
                      f"  Activated: {item['activation_date']}",
                      f"  First signal: {item['first_signal_date']}",
                      f"  First execution: {item['first_execution_date']}",
                      f"  Mature: 5D {sample['mature_5d']} | 20D {sample['mature_20d']} | 60D {sample['mature_60d']}",
                      f"  Positions: open {sample['open_positions']} | closed {sample['closed_trades']}",
                      f"  Decision: {item['decision']}",
                      f"  Next review: {item['review_window_start']} → {item['review_window_end']}"])
        lines.extend(f"  Warning: {warning}" for warning in item["warnings"])
    return "\n".join(lines)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    registry = build_registry()
    path = write_status(registry)
    print(render_console(registry))
    print(f"\nJSON: {path}")


if __name__ == "__main__":
    main()
