import hashlib
import json
from datetime import date

from database.db import DB_PATH
from research.experiment_registry import (
    NA, build_registry, days_since_activation, load_config, render_console,
    summarize_paper, write_status,
)


def _paper_provider(**_kwargs):
    return {
        "senales": [{"cantidad": 12}, {"cantidad": 8}],
        "resultados": [
            {"horizonte": 5, "cantidad": 10},
            {"horizonte": 20, "cantidad": 4},
        ],
    }


def _portfolio_provider():
    return [
        {"name": "MOMENTUM_LIVE", "abiertas": [{}, {}], "cerradas": 3},
        {"name": "REVERSAL_LIVE", "abiertas": [{}], "cerradas": 2},
        {"name": "ETF_TOP2_CANDIDATE", "abiertas": [], "cerradas": 0},
        {"name": "DEFENSIVE_CANDIDATE", "abiertas": [], "cerradas": 0},
    ]


def _dates_provider(sources):
    result = {}
    for source in sources:
        if source.get("kind") in {"paper", "signal_interaction"}:
            result[(source["strategy"], source["score_version"], source["variant"])] = {
                "first_signal_date": "2026-08-21"
            }
        if source.get("portfolio"):
            result[("portfolio", source["portfolio"])] = {"first_execution_date": None}
    return result


def _build(config=None):
    return build_registry(
        current_date=date(2026, 9, 2), config=config,
        paper_provider=_paper_provider, portfolios_provider=_portfolio_provider,
        dates_provider=_dates_provider,
    )


def test_days_since_activation_and_na():
    assert days_since_activation("2026-08-25", date(2026, 9, 2)) == 8
    assert days_since_activation(NA, date(2026, 9, 2)) == NA


def test_mature_counts_are_derived_not_hardcoded():
    assert summarize_paper(_paper_provider()) == {
        "signals_total": 20, "mature_5d": 10, "mature_20d": 4, "mature_60d": 0
    }
    momentum = next(x for x in _build()["experiments"] if x["id"] == "MOMENTUM_V4")
    assert momentum["sample"]["signals_total"] == 20
    assert momentum["sample"]["mature_60d"] == 0


def test_rejected_and_completed_states_are_preserved():
    registry = _build()
    fund = next(x for x in registry["experiments"] if x["id"] == "FUND_RESEARCH_PHASE1")
    assert fund["status"] == "REJECTED" and fund["decision"] == "NO_CANDIDATE"
    config = load_config()
    config["experiments"][4]["status"] = "COMPLETED"
    completed = _build(config)["experiments"][4]
    assert completed["status"] == "COMPLETED"


def test_review_windows_warnings_and_waiting_maturity():
    registry = _build()
    momentum = next(x for x in registry["experiments"] if x["id"] == "MOMENTUM_V4")
    interaction = next(x for x in registry["experiments"] if x["id"] == "SIGNAL_INTERACTION_PHASE1")
    assert momentum["review_window_start"] == "2026-09-21"
    assert "FROZEN — review window not reached" in momentum["warnings"]
    assert interaction["ready_for_phase2"] is False
    assert "INSUFFICIENT MATURITY" in interaction["warnings"]


def test_json_output_and_na_handling(tmp_path):
    registry = _build()
    path = write_status(registry, tmp_path / "status.json")
    stored = json.loads(path.read_text(encoding="utf-8"))
    fund = next(x for x in stored["experiments"] if x["id"] == "FUND_RESEARCH_PHASE1")
    assert fund["sample"]["open_positions"] == NA
    assert "TRADING LAB — EXPERIMENT STATUS" in render_console(stored)


def test_real_registry_does_not_modify_database():
    before = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    build_registry(current_date=date(2026, 9, 2))
    after = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert before == after


def test_registry_does_not_import_or_modify_strategy_modules():
    source = open("research/experiment_registry.py", encoding="utf-8").read()
    assert "paper_portfolio_live" not in source
    assert "paper_portfolios_runner" not in source
    assert "weekly_report" not in source
