"""Validaciones temporales y de concentracion para Signal Interaction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.signal_interaction_analysis import _fit_predict
from research.signal_interaction_dataset import HORIZONS


def temporal_validation(dataset, dictionary):
    rows = []
    dates = pd.to_datetime(dataset["market_date"], errors="coerce")
    years = sorted(dates.dropna().dt.year.unique())
    for test_year in years:
        train = dataset[dates.dt.year < test_year]
        test = dataset[dates.dt.year == test_year]
        for horizon in HORIZONS:
            outcome = f"exceso_spy_{horizon}d"
            baseline = _fit_predict(train, test, outcome)
            for feature in dictionary["feature"]:
                enriched = _fit_predict(train, test, outcome, feature)
                if baseline and enriched:
                    rows.append({"validation": "annual_walk_forward", "test_year": test_year,
                                 "feature": feature, "horizon": horizon,
                                 "train_n": enriched["train_n"], "test_n": enriched["test_n"],
                                 "delta_rmse": baseline["rmse"] - enriched["rmse"],
                                 "delta_r2": enriched["r2"] - baseline["r2"], "status": "OK"})
                else:
                    train_mature = int(pd.to_numeric(train.get(outcome), errors="coerce").notna().sum()) if outcome in train else 0
                    test_mature = int(pd.to_numeric(test.get(outcome), errors="coerce").notna().sum()) if outcome in test else 0
                    rows.append({"validation": "annual_walk_forward", "test_year": test_year,
                                 "feature": feature, "horizon": horizon,
                                 "train_n": train_mature, "test_n": test_mature,
                                 "delta_rmse": np.nan, "delta_r2": np.nan,
                                 "status": "INSUFFICIENT_DATA"})
    for sector in sorted(dataset.get("sector", pd.Series(dtype=str)).dropna().astype(str).unique()):
        for horizon in HORIZONS:
            outcome = f"exceso_spy_{horizon}d"
            mature = pd.to_numeric(dataset.get(outcome), errors="coerce").notna()
            rows.append({"validation": "leave_one_sector", "test_year": np.nan,
                         "feature": f"SECTOR={sector}", "horizon": horizon,
                         "train_n": int((mature & dataset["sector"].ne(sector)).sum()),
                         "test_n": int((mature & dataset["sector"].eq(sector)).sum()),
                         "delta_rmse": np.nan, "delta_r2": np.nan,
                         "status": "NOT_RUN_NO_TEMPORAL_DEPTH"})
    if not years:
        rows.append({"validation": "annual_walk_forward", "test_year": np.nan,
                     "feature": "ALL", "horizon": np.nan, "train_n": 0,
                     "test_n": 0, "delta_rmse": np.nan, "delta_r2": np.nan,
                     "status": "INSUFFICIENT_DATA"})
    return pd.DataFrame(rows)


def ticker_concentration(dataset):
    rows = []
    total = len(dataset)
    counts = dataset["symbol"].value_counts()
    for rank, (symbol, count) in enumerate(counts.items(), 1):
        rows.append({"rank": rank, "symbol": symbol, "signals": count,
                     "share_pct": count / total * 100 if total else 0,
                     "cumulative_share_pct": counts.iloc[:rank].sum() / total * 100 if total else 0})
    return pd.DataFrame(rows)


def validate_dataset(dataset):
    errors = []
    if dataset["signal_id"].duplicated().any():
        errors.append("signal_id duplicado")
    for column in ("fundamental_available_at", "analyst_available_at", "news_available_at"):
        left = pd.to_datetime(dataset[column], errors="coerce")
        right = pd.to_datetime(dataset["signal_time"], errors="coerce")
        if (left > right).fillna(False).any():
            errors.append(f"lookahead en {column}")
    for horizon in HORIZONS:
        entry = pd.to_datetime(dataset.get(f"fecha_entrada_{horizon}d"), errors="coerce")
        exit_date = pd.to_datetime(dataset.get(f"fecha_salida_{horizon}d"), errors="coerce")
        signal = pd.to_datetime(dataset["market_date"], errors="coerce")
        if (entry < signal).fillna(False).any() or (exit_date < entry).fillna(False).any():
            errors.append(f"alineacion temporal invalida a {horizon} sesiones")
        holding = pd.to_numeric(dataset.get(f"holding_sessions_real_{horizon}d"), errors="coerce")
        if (holding.dropna() != horizon).any():
            errors.append(f"holding no expresado en {horizon} sesiones reales")
    return errors
