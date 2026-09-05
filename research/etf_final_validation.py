"""Fase 3 final de validación ETF, sin crear una estrategia productiva.

Las reglas se importan congeladas desde etf_rotation_analysis. El bootstrap es
descriptivo: remuestrea bloques de retornos mensuales históricos y no predice
precios ni rentabilidades futuras.
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_factor_analysis import CACHE_DIR, obtener_precios
from research.etf_rotation_analysis import (
    GROUP_BY_SYMBOL,
    INITIAL_CAPITAL,
    REPRESENTATIVES,
    TRANSACTION_COST,
    construir_panel_features,
    fechas_rebalanceo,
    pesos_seleccion,
    simular_cartera,
)


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "research_etf"
PHASE2_EQUITY = OUTPUT_DIR / "etf_rotation_equity.csv"
PHASE2_RESULTS = OUTPUT_DIR / "etf_rotation_results.csv"
PHASE2_PERIODS = OUTPUT_DIR / "etf_rotation_periods.csv"

FINALISTS = {
    "TOP2_DIVERSIFIED_CASH": "G_diversified_top2|monthly|cash=1",
    "MOMENTUM60_CASH": "A_momentum60_top1|monthly|cash=1",
    "TREND_RS": "F_trend_rs_top1|monthly|cash=0",
}
BENCHMARKS = {
    "SPY": "SPY_BUY_HOLD",
    "60_40": "BENCHMARK_60_40",
    "SHY": "SHY_BUY_HOLD",
}
ALL_SERIES = {**FINALISTS, **BENCHMARKS}

CRISIS_WINDOWS = {
    "Q4_2018": ("2018-09-20", "2019-04-30"),
    "COVID_2020": ("2020-02-19", "2020-08-31"),
    "BEAR_2022": ("2022-01-03", "2023-07-31"),
}


def cargar_curvas(path=PHASE2_EQUITY):
    if not Path(path).exists():
        raise FileNotFoundError(
            "Falta etf_rotation_equity.csv; ejecuta primero "
            "python -m research.etf_rotation_analysis"
        )
    datos = pd.read_csv(path, parse_dates=["date"])
    curvas = {}
    for nombre, strategy_id in ALL_SERIES.items():
        curva = datos[datos["strategy_id"] == strategy_id].copy()
        if curva.empty:
            raise ValueError(f"No existe la curva congelada {strategy_id}")
        curvas[nombre] = curva.set_index("date").sort_index()
    return curvas


def max_drawdown_serie(equity):
    return (equity / equity.cummax() - 1).min() * 100


def metricas_anuales(curva, initial_capital=INITIAL_CAPITAL):
    equity = curva["equity"].dropna()
    daily = equity.pct_change()
    filas = []
    for year, grupo in equity.groupby(equity.index.year):
        anterior = equity[equity.index < grupo.index[0]]
        base = anterior.iloc[-1] if len(anterior) else initial_capital
        retorno = (grupo.iloc[-1] / base - 1) * 100
        serie_dd = pd.concat([pd.Series([base], index=[grupo.index[0] - pd.Timedelta(days=1)]), grupo])
        retornos = daily.loc[grupo.index].dropna()
        vol = retornos.std(ddof=1) * np.sqrt(252) * 100 if len(retornos) > 1 else np.nan
        sharpe = (
            retornos.mean() / retornos.std(ddof=1) * np.sqrt(252)
            if len(retornos) > 1 and retornos.std(ddof=1) > 0 else np.nan
        )
        filas.append({
            "year": int(year), "return": retorno,
            "max_drawdown": max_drawdown_serie(serie_dd),
            "volatility": vol, "sharpe": sharpe,
        })
    return pd.DataFrame(filas)


def episodios_drawdown(curva):
    equity = curva["equity"].dropna()
    running_max = equity.cummax()
    dd = equity / running_max - 1
    episodios = []
    en_drawdown = False
    peak_date = equity.index[0]
    inicio = None
    for fecha in equity.index:
        if dd.at[fecha] < -1e-12 and not en_drawdown:
            en_drawdown = True
            inicio = fecha
            peak_date = equity.loc[:fecha].idxmax()
        if en_drawdown and dd.at[fecha] >= -1e-12:
            tramo = dd.loc[inicio:fecha]
            trough = tramo.idxmin()
            episodios.append({
                "peak_date": peak_date, "start_date": inicio, "trough_date": trough,
                "recovery_date": fecha, "drawdown_pct": dd.at[trough] * 100,
                "underwater_sessions": len(tramo),
                "recovery_sessions": len(equity.loc[trough:fecha]) - 1,
                "recovered": True,
            })
            en_drawdown = False
    if en_drawdown:
        tramo = dd.loc[inicio:]
        trough = tramo.idxmin()
        episodios.append({
            "peak_date": peak_date, "start_date": inicio, "trough_date": trough,
            "recovery_date": pd.NaT, "drawdown_pct": dd.at[trough] * 100,
            "underwater_sessions": len(tramo), "recovery_sessions": np.nan,
            "recovered": False,
        })
    return pd.DataFrame(episodios).sort_values("drawdown_pct") if episodios else pd.DataFrame()


def analizar_crisis(curvas, windows=CRISIS_WINDOWS):
    filas = []
    for episodio, (start, end) in windows.items():
        for nombre, curva in curvas.items():
            tramo = curva.loc[start:end]
            if tramo.empty:
                continue
            equity = tramo["equity"]
            trough = (equity / equity.cummax() - 1).idxmin()
            dd = max_drawdown_serie(equity)
            peak = equity.loc[:trough].idxmax()
            objetivo = equity.at[peak]
            posterior = curva.loc[trough:]
            recuperadas = posterior[posterior["equity"] >= objetivo]
            recovery = recuperadas.index[0] if len(recuperadas) else pd.NaT
            filas.append({
                "episode": episodio, "series": nombre, "start": start, "end": end,
                "max_drawdown": dd, "peak_date": peak, "trough_date": trough,
                "recovery_date": recovery,
                "recovery_sessions": (
                    len(curva.loc[trough:recovery]) - 1 if pd.notna(recovery) else np.nan
                ),
                "holding_at_trough": tramo.at[trough, "holdings"],
                "cash_pct_window": (~tramo["is_invested"].astype(bool)).mean() * 100,
            })
    return pd.DataFrame(filas)


def rolling_summary(curva, spy_curve, windows=(252, 756, 1260)):
    filas = []
    equity = curva["equity"]
    spy = spy_curve["equity"].reindex(equity.index)
    for sessions in windows:
        retornos = (equity / equity.shift(sessions) - 1) * 100
        spy_retornos = (spy / spy.shift(sessions) - 1) * 100
        validos = retornos.dropna()
        if validos.empty:
            continue
        comparables = spy_retornos.loc[validos.index]
        filas.append({
            "window_years": sessions // 252, "windows": len(validos),
            "median_return": validos.median(), "worst_return": validos.min(),
            "best_return": validos.max(), "positive_pct": (validos > 0).mean() * 100,
            "beat_spy_pct": (validos > comparables).mean() * 100,
        })
    return pd.DataFrame(filas)


def block_bootstrap(curva, spy_curve, simulations=2000, block_size=3, seed=42):
    mensual = curva["equity"].resample("ME").last().pct_change().dropna()
    spy = spy_curve["equity"].resample("ME").last().pct_change().reindex(mensual.index).dropna()
    mensual = mensual.reindex(spy.index)
    n = len(mensual)
    if n < block_size:
        return {}
    rng = np.random.default_rng(seed)
    cagr_values, dd_values, spy_cagr_values = [], [], []
    max_start = n - block_size
    for _ in range(simulations):
        indices = []
        while len(indices) < n:
            inicio = int(rng.integers(0, max_start + 1))
            indices.extend(range(inicio, inicio + block_size))
        indices = indices[:n]
        muestra = mensual.iloc[indices].to_numpy()
        muestra_spy = spy.iloc[indices].to_numpy()
        path = np.cumprod(1 + muestra)
        cagr = path[-1] ** (12 / n) - 1
        dd = np.min(path / np.maximum.accumulate(path) - 1)
        spy_cagr = np.prod(1 + muestra_spy) ** (12 / n) - 1
        cagr_values.append(cagr * 100)
        dd_values.append(dd * 100)
        spy_cagr_values.append(spy_cagr * 100)
    cagr_values = np.asarray(cagr_values)
    dd_values = np.asarray(dd_values)
    spy_cagr_values = np.asarray(spy_cagr_values)
    return {
        "simulations": simulations, "block_months": block_size,
        "cagr_p05": np.percentile(cagr_values, 5),
        "cagr_median": np.median(cagr_values),
        "cagr_p95": np.percentile(cagr_values, 95),
        "maxdd_p05": np.percentile(dd_values, 5),
        "maxdd_median": np.median(dd_values),
        "maxdd_p95": np.percentile(dd_values, 95),
        "positive_probability": (cagr_values > 0).mean() * 100,
        "beat_spy_probability": (cagr_values > spy_cagr_values).mean() * 100,
    }


def concentracion_beneficios(curva):
    mensual = curva["equity"].resample("ME").last().pct_change().dropna() * 100
    total_positivo = mensual[mensual > 0].sum()
    mejores = mensual.sort_values(ascending=False)
    pnl_diario = curva["equity"].diff().fillna(0.0)
    pnl_etf = {}
    pnl_categoria = {}
    for fecha, pnl in pnl_diario.items():
        holding = curva.at[fecha, "holdings"] if "holdings" in curva else "CASH"
        symbols = [] if pd.isna(holding) or holding == "CASH" else str(holding).split("+")
        for symbol in symbols:
            atribuido = pnl / len(symbols)
            pnl_etf[symbol] = pnl_etf.get(symbol, 0.0) + atribuido
            categoria = GROUP_BY_SYMBOL.get(symbol, symbol)
            pnl_categoria[categoria] = pnl_categoria.get(categoria, 0.0) + atribuido
    beneficio_neto = curva["equity"].iloc[-1] - curva["equity"].iloc[0]

    def serializar_contribucion(valores):
        return ";".join(
            f"{clave}:{valor / beneficio_neto * 100:+.2f}%"
            for clave, valor in sorted(valores.items(), key=lambda item: -item[1])
        ) if beneficio_neto else ""

    return {
        "months": len(mensual),
        "top5_positive_contribution_pct": mejores.head(5).sum() / total_positivo * 100 if total_positivo else np.nan,
        "top10_positive_contribution_pct": mejores.head(10).sum() / total_positivo * 100 if total_positivo else np.nan,
        "best5_months": ";".join(f"{d:%Y-%m}:{v:+.2f}%" for d, v in mejores.head(5).items()),
        "worst5_months": ";".join(f"{d:%Y-%m}:{v:+.2f}%" for d, v in mejores.tail(5).sort_values().items()),
        # Atribución aproximada: P&L close-to-close repartido entre las
        # posiciones que constan al cierre; no es contabilidad intradía exacta.
        "profit_contribution_by_etf": serializar_contribucion(pnl_etf),
        "profit_contribution_by_category": serializar_contribucion(pnl_categoria),
    }


def experiencia_operativa(curva, correlations=None):
    holdings = curva["holdings"].fillna("CASH")
    cambios = (holdings != holdings.shift()).sum() - 1
    bloques = (holdings != holdings.shift()).cumsum()
    duraciones = holdings.groupby(bloques).size()
    etf_dias = {}
    categoria_dias = {}
    concentraciones = []
    pares = []
    for holding in holdings:
        symbols = [] if holding == "CASH" else holding.split("+")
        if symbols:
            concentraciones.append(len(symbols) * (1 / len(symbols)) ** 2)
        for symbol in symbols:
            etf_dias[symbol] = etf_dias.get(symbol, 0) + 1 / len(symbols)
            categoria = GROUP_BY_SYMBOL[symbol]
            categoria_dias[categoria] = categoria_dias.get(categoria, 0) + 1 / len(symbols)
        if len(symbols) == 2:
            pares.append(tuple(sorted(symbols)))
    total = len(curva)
    corr_values = []
    if correlations is not None:
        for a, b in pares:
            if a in correlations.index and b in correlations.columns:
                corr_values.append(correlations.at[a, b])
    return {
        "asset_changes": int(max(cambios, 0)),
        "average_holding_sessions": duraciones.mean(),
        "cash_pct": (holdings == "CASH").mean() * 100,
        "average_concentration_hhi": np.mean(concentraciones) if concentraciones else np.nan,
        "average_pair_correlation": np.mean(corr_values) if corr_values else np.nan,
        "time_by_etf": ";".join(f"{k}:{v / total * 100:.2f}%" for k, v in sorted(etf_dias.items(), key=lambda x: -x[1])),
        "time_by_category": ";".join(f"{k}:{v / total * 100:.2f}%" for k, v in sorted(categoria_dias.items(), key=lambda x: -x[1])),
    }


def validar_capital(historicos, panel, start):
    calendario = historicos["SPY"].loc[start:].index
    recortados = {s: df.loc[df.index >= calendario[0]] for s, df in historicos.items()}
    signals = [calendario[0], *fechas_rebalanceo(calendario, "monthly")]
    configuraciones = {
        "TOP2_DIVERSIFIED_CASH": ("G_diversified_top2", True),
        "MOMENTUM60_CASH": ("A_momentum60_top1", True),
        "TREND_RS": ("F_trend_rs_top1", False),
    }
    filas = []
    for nombre, (strategy, cash_filter) in configuraciones.items():
        for capital in (1_000.0, 10_000.0, 50_000.0):
            curva = simular_cartera(
                recortados, signals,
                lambda fecha, s=strategy, c=cash_filter: pesos_seleccion(panel, fecha, s, c),
                initial_capital=capital, cost_rate=TRANSACTION_COST,
            )
            retorno = (curva["equity"].iloc[-1] / capital - 1) * 100
            filas.append({
                "series": nombre, "initial_capital": capital,
                "cumulative_return": retorno,
                "ending_equity": curva["equity"].iloc[-1],
                "total_costs": curva["transaction_cost"].sum(),
            })
    return pd.DataFrame(filas)


def crear_scorecard(curvas, yearly, rolling, phase2_results, phase2_periods):
    filas = []
    for nombre in ("TOP2_DIVERSIFIED_CASH", "MOMENTUM60_CASH", "TREND_RS", "SPY", "60_40"):
        strategy_id = ALL_SERIES[nombre]
        base = phase2_results[phase2_results["strategy_id"].fillna(phase2_results["strategy"]) == strategy_id]
        if base.empty:
            base = phase2_results[phase2_results["strategy"] == strategy_id]
        base = base.iloc[0]
        anual = yearly[yearly["series"] == nombre]
        roll = rolling[rolling["series"] == nombre]
        drawdowns = episodios_drawdown(curvas[nombre])
        train = phase2_periods[(phase2_periods["strategy_id"].fillna(phase2_periods["strategy"]) == strategy_id) & (phase2_periods["period"] == "TRAIN_2016-2021")]
        test = phase2_periods[(phase2_periods["strategy_id"].fillna(phase2_periods["strategy"]) == strategy_id) & (phase2_periods["period"] == "TEST_2022-2026")]
        filas.append({
            "series": nombre, "cagr": base["cagr"], "max_drawdown": base["max_drawdown"],
            "sharpe": base["sharpe"], "sortino": base["sortino"], "calmar": base["calmar"],
            "worst_year": anual["return"].min(),
            "positive_years": int((anual["return"] > 0).sum()), "total_years": len(anual),
            "years_beating_spy": int((anual["excess_vs_spy"] > 0).sum()),
            "worst_rolling_1y": roll.loc[roll["window_years"] == 1, "worst_return"].min(),
            "worst_rolling_3y": roll.loc[roll["window_years"] == 3, "worst_return"].min(),
            "max_underwater_sessions": drawdowns["underwater_sessions"].max(),
            "turnover": base["turnover"], "total_costs": base["total_costs"],
            "cash_pct": base["cash_pct"],
            "train_cagr": train["cagr"].iloc[0], "test_cagr": test["cagr"].iloc[0],
            "train_test_gap": abs(train["cagr"].iloc[0] - test["cagr"].iloc[0]),
        })
    return pd.DataFrame(filas)


def parse_args():
    parser = argparse.ArgumentParser(description="Validación ETF final, sin estrategia productiva")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--bootstrap-simulations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    curvas = cargar_curvas()
    yearly_parts = []
    for nombre, curva in curvas.items():
        tabla = metricas_anuales(curva)
        tabla.insert(0, "series", nombre)
        yearly_parts.append(tabla)
    yearly = pd.concat(yearly_parts, ignore_index=True)
    spy_years = yearly[yearly["series"] == "SPY"].set_index("year")["return"]
    yearly["spy_return"] = yearly["year"].map(spy_years)
    yearly["excess_vs_spy"] = yearly["return"] - yearly["spy_return"]

    drawdown_parts = []
    for nombre, curva in curvas.items():
        tabla = episodios_drawdown(curva).head(5).copy()
        tabla.insert(0, "series", nombre)
        drawdown_parts.append(tabla)
    drawdowns = pd.concat(drawdown_parts, ignore_index=True)
    crisis = analizar_crisis(curvas)

    rolling_parts = []
    for nombre, curva in curvas.items():
        tabla = rolling_summary(curva, curvas["SPY"])
        tabla.insert(0, "series", nombre)
        rolling_parts.append(tabla)
    rolling = pd.concat(rolling_parts, ignore_index=True)

    bootstrap = pd.DataFrame([
        {"series": nombre, **block_bootstrap(
            curva, curvas["SPY"], simulations=args.bootstrap_simulations, seed=args.seed
        )}
        for nombre, curva in curvas.items()
    ])
    concentration = pd.DataFrame([
        {"series": nombre, **concentracion_beneficios(curva)}
        for nombre, curva in curvas.items()
    ])

    historicos = {
        item.symbol: obtener_precios(
            item.symbol, pd.Timestamp(args.start) - timedelta(days=400),
            pd.Timestamp(args.end), cache_dir=CACHE_DIR,
        )
        for item in REPRESENTATIVES
    }
    returns = pd.concat({s: df["close"].pct_change() for s, df in historicos.items()}, axis=1)
    correlations = returns.corr()
    experience = pd.DataFrame([
        {"series": nombre, **experiencia_operativa(curva, correlations)}
        for nombre, curva in curvas.items()
    ])
    panel = construir_panel_features(historicos)
    capital = validar_capital(historicos, panel, pd.Timestamp(args.start))

    phase2_results = pd.read_csv(PHASE2_RESULTS)
    phase2_periods = pd.read_csv(PHASE2_PERIODS)
    scorecard = crear_scorecard(
        curvas, yearly, rolling, phase2_results, phase2_periods
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(OUTPUT_DIR / "etf_final_scorecard.csv", index=False)
    yearly.to_csv(OUTPUT_DIR / "etf_final_yearly.csv", index=False)
    drawdowns.to_csv(OUTPUT_DIR / "etf_final_drawdowns.csv", index=False)
    rolling.to_csv(OUTPUT_DIR / "etf_final_rolling.csv", index=False)
    crisis.to_csv(OUTPUT_DIR / "etf_final_crisis.csv", index=False)
    bootstrap.to_csv(OUTPUT_DIR / "etf_final_bootstrap.csv", index=False)
    concentration.to_csv(OUTPUT_DIR / "etf_final_concentration.csv", index=False)
    experience.to_csv(OUTPUT_DIR / "etf_final_experience.csv", index=False)
    capital.to_csv(OUTPUT_DIR / "etf_final_capital.csv", index=False)

    print("\nETF FINAL VALIDATION - FASE 3")
    print("=" * 84)
    print(scorecard.round(2).to_string(index=False))
    print("\nValidación descriptiva. No se ha creado ETF V1.")


if __name__ == "__main__":
    main()
