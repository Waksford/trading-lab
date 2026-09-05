"""Analisis descriptivo e incremental explicable para Signal Interaction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.signal_interaction_dataset import HORIZONS


MIN_GROUP = 10
EXTERNAL_FEATURES = (
    "score_fundamental", "calidad_fundamental", "upside_mean_pct",
    "consensus_score", "target_revision_7d", "eps_revision_7d",
    "consensus_revision_7d", "news_context", "fuerza_catalizador",
    "riesgo_narrativo", "score_sector", "fuerza_sector_20d",
    "fuerza_sector_60d", "spy_momentum60", "market_regime",
)


def _summary(group, outcome):
    values = pd.to_numeric(group[outcome], errors="coerce").dropna()
    return {
        "n": len(values), "mean": values.mean(), "median": values.median(),
        "positive_pct": (values > 0).mean() * 100 if len(values) else np.nan,
        "std": values.std(ddof=1),
    }


def baseline_results(dataset):
    rows = []
    groups = {"A+": ["A+"], "A": ["A"], "B": ["B"], "A+/A": ["A+", "A"]}
    for horizon in HORIZONS:
        for label, priorities in groups.items():
            subset = dataset[dataset["prioridad"].isin(priorities)]
            for metric in ("retorno", "retorno_spy", "exceso_spy", "max_drawdown"):
                outcome = f"{metric}_{horizon}d"
                stats = _summary(subset, outcome) if outcome in subset else _summary(pd.DataFrame({outcome: []}), outcome)
                rows.append({"horizon": horizon, "priority": label,
                             "metric": metric, **stats,
                             "status": "OK" if stats["n"] >= MIN_GROUP else "INSUFFICIENT_DATA"})
    return pd.DataFrame(rows)


def _bands(series, kind):
    if kind == "numeric":
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.nunique(dropna=True) < 3:
            return numeric.astype("string")
        try:
            return pd.qcut(numeric, q=3, duplicates="drop").astype("string")
        except ValueError:
            return numeric.astype("string")
    return series.astype("string")


def univariate_results(dataset, dictionary):
    rows = []
    for feature in dictionary["feature"]:
        if feature not in dataset:
            continue
        kind = "numeric" if dictionary.loc[dictionary["feature"] == feature, "type"].iloc[0] == "numerica" else "categorical"
        bands = _bands(dataset[feature], kind).fillna("MISSING")
        for horizon in HORIZONS:
            outcome = f"exceso_spy_{horizon}d"
            if outcome not in dataset:
                continue
            frame = dataset.assign(_band=bands)
            for (priority, band), group in frame[frame["prioridad"].isin(["A+", "A"])].groupby(["priority_group", "_band"], dropna=False):
                stats = _summary(group, outcome)
                rows.append({"feature": feature, "horizon": horizon,
                             "priority": priority, "band": str(band), **stats,
                             "status": "OK" if stats["n"] >= MIN_GROUP else "INSUFFICIENT_DATA"})
    return pd.DataFrame(rows)


def disagreement_results(dataset):
    subset = dataset[dataset["prioridad"].isin(["A+", "A"])].copy()
    rules = {
        "fundamental_debil": subset.get("calidad_fundamental", pd.Series(index=subset.index)).isin(["DEBIL", "MUY DEBIL"]),
        "analistas_negativos": pd.to_numeric(subset.get("consensus_score"), errors="coerce") < 0,
        "revision_negativa": pd.to_numeric(subset.get("target_revision_7d"), errors="coerce") < -3,
        "noticias_negativas": subset.get("news_context", pd.Series(index=subset.index)).eq("NEGATIVO"),
        "sector_debil": pd.to_numeric(subset.get("fuerza_sector_60d"), errors="coerce") < 0,
        "mercado_defensivo": subset.get("market_regime", pd.Series(index=subset.index)).eq("RISK_OFF"),
    }
    rows = []
    for name, mask in rules.items():
        mask = mask.fillna(False)
        for horizon in HORIZONS:
            outcome = f"exceso_spy_{horizon}d"
            for state, group in (("DISAGREEMENT", subset[mask]), ("NO_DISAGREEMENT", subset[~mask])):
                stats = _summary(group, outcome)
                rows.append({"rule": name, "state": state, "horizon": horizon, **stats,
                             "status": "OK" if stats["n"] >= MIN_GROUP else "INSUFFICIENT_DATA"})
    return pd.DataFrame(rows)


def feature_dependence(dataset, dictionary):
    rows = []
    technical = [c for c in ("score", "score_tendencia", "score_momentum",
                             "score_fuerza", "score_sector", "score_continuacion") if c in dataset]
    for feature in dictionary["feature"]:
        if feature not in dataset:
            continue
        numeric = pd.to_numeric(dataset[feature], errors="coerce")
        if numeric.notna().sum() >= MIN_GROUP:
            for tech in technical:
                pair = pd.concat([pd.to_numeric(dataset[tech], errors="coerce"), numeric], axis=1).dropna()
                variable = len(pair) >= 3 and pair.iloc[:, 0].nunique() > 1 and pair.iloc[:, 1].nunique() > 1
                rows.append({"feature": feature, "technical_feature": tech,
                             "kind": "numeric", "n": len(pair),
                             "pearson": pair.iloc[:, 0].corr(pair.iloc[:, 1], method="pearson") if variable else np.nan,
                             "spearman": pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank()) if variable else np.nan,
                             "categories": None})
        else:
            counts = dataset[feature].fillna("MISSING").astype(str).value_counts()
            rows.append({"feature": feature, "technical_feature": "priority",
                         "kind": "categorical_descriptive", "n": int(counts.sum()),
                         "pearson": np.nan, "spearman": np.nan,
                         "categories": "|".join(f"{k}:{v}" for k, v in counts.items())})
    return pd.DataFrame(rows)


def _design(frame, feature=None, categories=None):
    base = pd.DataFrame(index=frame.index)
    base["intercept"] = 1.0
    base["score"] = pd.to_numeric(frame["score"], errors="coerce")
    priority = pd.get_dummies(frame["prioridad"], prefix="priority", dtype=float)
    base = pd.concat([base, priority], axis=1)
    if feature:
        numeric = pd.to_numeric(frame[feature], errors="coerce")
        if numeric.notna().sum() >= max(5, len(frame) // 3):
            base[feature] = numeric
            base[f"{feature}_missing"] = numeric.isna().astype(float)
        else:
            values = frame[feature].fillna("MISSING").astype(str)
            cats = categories or sorted(values.unique())
            for category in cats:
                base[f"{feature}={category}"] = (values == category).astype(float)
    return base.astype(float)


def _fit_predict(train, test, outcome, feature=None):
    y_train = pd.to_numeric(train[outcome], errors="coerce")
    y_test = pd.to_numeric(test[outcome], errors="coerce")
    valid_train = y_train.notna() & pd.to_numeric(train["score"], errors="coerce").notna()
    valid_test = y_test.notna() & pd.to_numeric(test["score"], errors="coerce").notna()
    train, test = train[valid_train], test[valid_test]
    y_train, y_test = y_train[valid_train].to_numpy(), y_test[valid_test].to_numpy()
    if len(train) < 20 or len(test) < 10:
        return None
    categories = sorted(train[feature].fillna("MISSING").astype(str).unique()) if feature else None
    x_train = _design(train, feature, categories)
    x_test = _design(test, feature, categories).reindex(columns=x_train.columns, fill_value=0)
    medians = x_train.median(numeric_only=True)
    x_train = x_train.fillna(medians).fillna(0)
    x_test = x_test.fillna(medians).fillna(0)
    beta = np.linalg.pinv(x_train.to_numpy()) @ y_train
    prediction = x_test.to_numpy() @ beta
    error = y_test - prediction
    rmse = float(np.sqrt(np.mean(error ** 2)))
    mae = float(np.mean(np.abs(error)))
    denominator = float(np.sum((y_test - y_test.mean()) ** 2))
    r2 = 1 - float(np.sum(error ** 2)) / denominator if denominator else np.nan
    direction = float((np.sign(prediction) == np.sign(y_test)).mean())
    return {"train_n": len(train), "test_n": len(test), "rmse": rmse,
            "mae": mae, "r2": r2, "direction_accuracy": direction}


def incremental_value(dataset, dictionary, train_end="2021-12-31"):
    rows = []
    dates = pd.to_datetime(dataset["market_date"], errors="coerce")
    train = dataset[dates <= pd.Timestamp(train_end)]
    test = dataset[dates > pd.Timestamp(train_end)]
    for horizon in HORIZONS:
        outcome = f"exceso_spy_{horizon}d"
        baseline = _fit_predict(train, test, outcome)
        for feature in dictionary["feature"]:
            enriched = _fit_predict(train, test, outcome, feature) if feature in dataset else None
            row = {"feature": feature, "horizon": horizon,
                   "train_end": train_end, "test_start": "2022-01-01"}
            if baseline is None or enriched is None:
                row.update({"train_n": int(pd.to_numeric(train.get(outcome), errors="coerce").notna().sum()) if outcome in train else 0,
                            "test_n": int(pd.to_numeric(test.get(outcome), errors="coerce").notna().sum()) if outcome in test else 0,
                            "baseline_rmse": np.nan, "feature_rmse": np.nan,
                            "delta_rmse": np.nan, "baseline_r2": np.nan,
                            "feature_r2": np.nan, "delta_r2": np.nan,
                            "classification": "INSUFFICIENT_DATA"})
            else:
                row.update({"train_n": enriched["train_n"], "test_n": enriched["test_n"],
                            "baseline_rmse": baseline["rmse"], "feature_rmse": enriched["rmse"],
                            "delta_rmse": baseline["rmse"] - enriched["rmse"],
                            "baseline_r2": baseline["r2"], "feature_r2": enriched["r2"],
                            "delta_r2": enriched["r2"] - baseline["r2"],
                            "classification": "PROMISING" if enriched["rmse"] < baseline["rmse"] else "NEUTRAL"})
            rows.append(row)
    return pd.DataFrame(rows)
