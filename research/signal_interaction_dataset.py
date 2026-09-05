"""Dataset point-in-time para SIGNAL INTERACTION RESEARCH.

Este modulo es deliberadamente independiente de produccion: solo hace lecturas
de SQLite y nunca modifica senales, carteras ni reglas de trading.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from database.db import DB_PATH


HORIZONS = (5, 20, 60)
PRIORITIES = ("A+", "A", "B")
TECHNICAL_FEATURES = (
    "score", "score_tendencia", "score_momentum", "score_fuerza",
    "score_sector", "score_continuacion", "score_volumen", "rsi",
    "fuerza_20d", "fuerza_60d", "fuerza_sector_20d",
    "fuerza_sector_60d", "distancia_sma20", "distancia_sma50",
)


def _read(conexion, query, params=()):
    return pd.read_sql_query(query, conexion, params=params)


def _timestamps(series):
    return pd.to_datetime(series, errors="coerce", utc=False)


def temporal_asof_join(base, snapshots, columns, timestamp_col="available_at"):
    """Une el ultimo snapshot del simbolo que ya existia al emitirse la senal."""
    result = base.copy()
    for column in columns:
        if column not in result:
            result[column] = np.nan
    if snapshots.empty or result.empty:
        return result

    left = result.reset_index().rename(columns={"index": "_original_index"})
    right = snapshots.copy()
    left["signal_time"] = _timestamps(left["signal_time"])
    right[timestamp_col] = _timestamps(right[timestamp_col])
    left["symbol"] = left["symbol"].astype(str).str.upper()
    right["symbol"] = right["symbol"].astype(str).str.upper()
    right = right.dropna(subset=[timestamp_col]).sort_values(timestamp_col)
    left = left.sort_values("signal_time")
    payload = list(dict.fromkeys(
        ["symbol", timestamp_col] + [c for c in columns if c in right]
    ))
    merged = pd.merge_asof(
        left, right[payload], left_on="signal_time", right_on=timestamp_col,
        by="symbol", direction="backward", allow_exact_matches=True,
        suffixes=("", "_snapshot"),
    )
    for column in columns:
        snapshot_column = f"{column}_snapshot"
        if snapshot_column in merged:
            merged[column] = merged[snapshot_column]
            merged = merged.drop(columns=snapshot_column)
    return merged.sort_values("_original_index").drop(
        columns=["_original_index"], errors="ignore"
    ).reset_index(drop=True)


def _load_signals(conexion):
    signals = _read(conexion, """
        SELECT id AS signal_id, market_date, scan_time, symbol, prioridad,
               score AS paper_score, sector AS paper_sector, created_at
        FROM paper_signals
        WHERE strategy = 'MOMENTUM'
          AND source_score_version = 'v4'
          AND variant = 'BASE'
          AND prioridad IN ('A+', 'A', 'B')
        ORDER BY market_date, symbol, id
    """)
    if signals.empty:
        return signals
    signals["signal_time"] = _timestamps(signals["scan_time"])
    fallback = _timestamps(signals["market_date"] + " 23:59:59")
    signals["signal_time"] = signals["signal_time"].fillna(fallback)
    signals["symbol"] = signals["symbol"].str.upper()
    return signals


def _load_original_scans(conexion):
    columns = ["market_date", "scan_time", "symbol", "score_version",
               "prioridad_estudio", "sector", "sector_benchmark",
               "fortaleza_sector", "riesgo_clasificacion"] + list(TECHNICAL_FEATURES)
    scans = _read(conexion, "SELECT id, " + ", ".join(columns) + " FROM scans WHERE score_version='v4'")
    if scans.empty:
        return scans
    scans = scans.sort_values(["market_date", "symbol", "scan_time", "id"])
    return scans.drop_duplicates(["market_date", "symbol"], keep="last")


def _load_results(conexion):
    results = _read(conexion, """
        SELECT signal_id, horizonte, fecha_entrada, fecha_salida, holding_sessions_real, retorno,
               retorno_spy, exceso_spy, max_subida, max_caida, max_drawdown
        FROM paper_results
        WHERE COALESCE(variant, 'BASE') = 'BASE'
          AND horizonte IN (5, 20, 60)
    """)
    if results.empty:
        return pd.DataFrame(columns=["signal_id"])
    value_columns = ["retorno", "retorno_spy", "exceso_spy", "max_subida",
                     "max_caida", "max_drawdown", "fecha_entrada", "fecha_salida",
                     "holding_sessions_real"]
    pieces = []
    for horizon in HORIZONS:
        part = results[results["horizonte"] == horizon][["signal_id"] + value_columns].copy()
        part = part.rename(columns={c: f"{c}_{horizon}d" for c in value_columns})
        pieces.append(part)
    output = pieces[0]
    for part in pieces[1:]:
        output = output.merge(part, on="signal_id", how="outer")
    return output


def _load_fundamentals(conexion):
    data = _read(conexion, """
        SELECT fc.symbol, fc.score_fundamental, fc.calidad_fundamental,
               fc.crecimiento AS crecimiento_fundamental,
               fc.rentabilidad AS rentabilidad_fundamental,
               fc.balance AS balance_fundamental,
               fc.valoracion AS valoracion_fundamental,
               fc.created_at AS classification_created_at,
               fa.created_at AS snapshot_created_at
        FROM fundamental_classification fc
        JOIN fundamental_analysis fa ON fa.id = fc.fundamental_id
    """)
    if data.empty:
        return data
    a = _timestamps(data["classification_created_at"])
    b = _timestamps(data["snapshot_created_at"])
    data["fundamental_available_at"] = pd.concat([a, b], axis=1).max(axis=1)
    return data.rename(columns={"fundamental_available_at": "available_at"})


def _load_analysts(conexion):
    data = _read(conexion, """
        SELECT id, symbol, snapshot_time, snapshot_date, upside_mean_pct,
               consensus_score, analyst_count, target_mean, eps_next_y
        FROM analyst_consensus_snapshots WHERE source='YAHOO'
    """)
    if data.empty:
        return data
    data["available_at"] = _timestamps(data["snapshot_time"])
    data = data.sort_values(["symbol", "available_at", "id"])
    rows = []
    for symbol, group in data.groupby("symbol"):
        records = group.to_dict("records")
        for current in records:
            cutoff = pd.Timestamp(current["available_at"]) - pd.Timedelta(days=7)
            previous = next((r for r in reversed(records)
                             if pd.Timestamp(r["available_at"]) <= cutoff), None)
            def pct(name):
                if not previous or previous.get(name) in (None, 0) or pd.isna(previous.get(name)):
                    return np.nan
                return (current.get(name) / previous.get(name) - 1) * 100
            current["target_revision_7d"] = pct("target_mean")
            current["eps_revision_7d"] = pct("eps_next_y")
            current["consensus_revision_7d"] = (
                current.get("consensus_score") - previous.get("consensus_score")
                if previous and pd.notna(current.get("consensus_score"))
                and pd.notna(previous.get("consensus_score")) else np.nan
            )
            rows.append(current)
    return pd.DataFrame(rows)


def _load_news(conexion):
    data = _read(conexion, """
        SELECT id, symbol, market_date AS news_market_date, contexto AS news_context,
               fuerza_catalizador, riesgo_narrativo, num_noticias,
               analyzed_at AS available_at
        FROM news_context
    """)
    if not data.empty:
        data["available_at"] = _timestamps(data["available_at"])
    return data


def build_signal_dataset(db_path=DB_PATH):
    """Construye una fila por senal real V4; los outcomes siguen en columnas."""
    conexion = sqlite3.connect(Path(db_path))
    try:
        signals = _load_signals(conexion)
        if signals.empty:
            return signals
        scans = _load_original_scans(conexion)
        results = _load_results(conexion)
        dataset = signals.merge(
            scans, on=["market_date", "symbol"], how="left", suffixes=("", "_scan")
        ).merge(results, on="signal_id", how="left")

        fund_cols = ["score_fundamental", "calidad_fundamental",
                     "crecimiento_fundamental", "rentabilidad_fundamental",
                     "balance_fundamental", "valoracion_fundamental",
                     "available_at"]
        dataset = temporal_asof_join(dataset, _load_fundamentals(conexion), fund_cols)
        dataset = dataset.rename(columns={"available_at": "fundamental_available_at"})

        analyst_cols = ["upside_mean_pct", "consensus_score", "analyst_count",
                        "target_revision_7d", "eps_revision_7d",
                        "consensus_revision_7d", "available_at"]
        dataset = temporal_asof_join(dataset, _load_analysts(conexion), analyst_cols)
        dataset = dataset.rename(columns={"available_at": "analyst_available_at"})

        news_cols = ["news_market_date", "news_context", "fuerza_catalizador",
                     "riesgo_narrativo", "num_noticias", "available_at"]
        dataset = temporal_asof_join(dataset, _load_news(conexion), news_cols)
        dataset = dataset.rename(columns={"available_at": "news_available_at"})
        stale_news = dataset["news_market_date"].astype("string") != dataset["market_date"].astype("string")
        dataset.loc[stale_news.fillna(True), [
            "news_market_date", "news_context", "fuerza_catalizador",
            "riesgo_narrativo", "num_noticias", "news_available_at",
        ]] = np.nan

        benchmark = _read(conexion, """
            SELECT market_date, return_60d AS spy_momentum60
            FROM benchmark_scans WHERE symbol='SPY'
        """)
        dataset = dataset.merge(benchmark, on="market_date", how="left")
        dataset["market_regime"] = np.where(
            dataset["spy_momentum60"].isna(), None,
            np.where(dataset["spy_momentum60"] >= 0, "RISK_ON", "RISK_OFF")
        )
        dataset["priority_group"] = np.where(
            dataset["prioridad"].isin(["A+", "A"]), "A+/A", dataset["prioridad"]
        )

        feature_groups = {
            "fundamental": ["score_fundamental", "calidad_fundamental"],
            "analyst": ["upside_mean_pct", "consensus_score"],
            "revision": ["target_revision_7d", "eps_revision_7d", "consensus_revision_7d"],
            "news": ["news_context", "fuerza_catalizador", "riesgo_narrativo"],
            "sector": ["score_sector", "fuerza_sector_20d", "fuerza_sector_60d"],
            "market": ["spy_momentum60", "market_regime"],
        }
        for group, columns in feature_groups.items():
            dataset[f"missing_{group}"] = dataset[columns].isna().all(axis=1).astype(int)
        for column in ["fundamental_available_at", "analyst_available_at", "news_available_at"]:
            invalid = _timestamps(dataset[column]) > _timestamps(dataset["signal_time"])
            if invalid.fillna(False).any():
                raise AssertionError(f"Lookahead detectado en {column}")
        return dataset.sort_values(["market_date", "symbol", "signal_id"]).reset_index(drop=True)
    finally:
        conexion.close()


def feature_dictionary():
    rows = []
    definitions = {
        "score_fundamental": ("fundamental", "numerica", "Snapshot clasificado disponible antes de la senal"),
        "calidad_fundamental": ("fundamental", "categorica", "Calidad fundamental historicamente disponible"),
        "upside_mean_pct": ("analistas", "numerica", "Potencial medio del ultimo snapshot previo"),
        "consensus_score": ("analistas", "numerica", "Consenso del ultimo snapshot previo"),
        "target_revision_7d": ("revisiones", "numerica", "Cambio de target frente a snapshot de al menos 7 dias antes"),
        "eps_revision_7d": ("revisiones", "numerica", "Cambio de EPS frente a snapshot de al menos 7 dias antes"),
        "consensus_revision_7d": ("revisiones", "numerica", "Cambio de consenso frente a snapshot de al menos 7 dias antes"),
        "news_context": ("noticias", "categorica", "Contexto analizado y ya disponible al emitir la senal"),
        "fuerza_catalizador": ("noticias", "categorica", "Fuerza del catalizador disponible al emitir la senal"),
        "riesgo_narrativo": ("noticias", "categorica", "Riesgo narrativo disponible al emitir la senal"),
        "score_sector": ("sector", "numerica", "Componente sectorial persistido en el scan original"),
        "fuerza_sector_20d": ("sector", "numerica", "Fuerza sectorial 20 sesiones del scan original"),
        "fuerza_sector_60d": ("sector", "numerica", "Fuerza sectorial 60 sesiones del scan original"),
        "spy_momentum60": ("mercado", "numerica", "Retorno SPY 60 sesiones conocido en la fecha de senal"),
        "market_regime": ("mercado", "categorica", "RISK_ON si SPY momentum60 >= 0; RISK_OFF en otro caso"),
    }
    for feature, (group, kind, definition) in definitions.items():
        rows.append({"feature": feature, "feature_group": group, "type": kind,
                     "definition": definition, "point_in_time_rule": "available_at <= signal_time",
                     "production_use": "NONE_RESEARCH_ONLY"})
    return pd.DataFrame(rows)


def data_availability_audit(dataset):
    rows = []
    groups = {
        "technical_signal": ("score", "PERSISTED_AT_SIGNAL"),
        "sector_context": ("score_sector", "PERSISTED_AT_SIGNAL"),
        "market_regime": ("spy_momentum60", "RECONSTRUCTED_PRIOR_ONLY"),
        "fundamentals": ("score_fundamental", "BACKWARD_SNAPSHOT_JOIN"),
        "analyst_consensus": ("consensus_score", "BACKWARD_SNAPSHOT_JOIN"),
        "analyst_revisions_7d": ("target_revision_7d", "TWO_PRIOR_SNAPSHOTS_REQUIRED"),
        "news": ("news_context", "BACKWARD_SNAPSHOT_JOIN"),
    }
    for source, (column, method) in groups.items():
        available = int(dataset[column].notna().sum()) if column in dataset else 0
        point_status = (
            "NOT_POINT_IN_TIME" if source == "news" and available == 0
            else "POINT_IN_TIME"
        )
        rows.append({
            "source": source, "join_method": method, "total_signals": len(dataset),
            "available_signals": available,
            "coverage_pct": available / len(dataset) * 100 if len(dataset) else 0,
            "first_signal_date": dataset.loc[dataset[column].notna(), "market_date"].min()
                if available else None,
            "last_signal_date": dataset.loc[dataset[column].notna(), "market_date"].max()
                if available else None,
            "point_in_time_status": point_status,
            "causal_use": ("NOT_ELIGIBLE" if point_status == "NOT_POINT_IN_TIME"
                           else "ELIGIBLE_IF_SAMPLE_SUFFICIENT" if available
                           else "INSUFFICIENT_DATA"),
        })
    return pd.DataFrame(rows)
