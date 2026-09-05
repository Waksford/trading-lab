"""Exploratory Defensive research. It does not define Defensive V1 or paper state."""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_factor_analysis import CACHE_DIR, obtener_precios
from research.etf_final_validation import episodios_drawdown, rolling_summary
from research.etf_rotation_analysis import (
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    calcular_metricas,
    fechas_rebalanceo,
    simular_cartera,
)


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "research_defensive"
DEFENSIVE_ASSETS = ("SHY", "IEF", "TLT", "LQD", "GLD")
DOWNLOAD_ASSETS = ("SPY", *DEFENSIVE_ASSETS)
RISK_RULES = (
    "SPY_BELOW_SMA200",
    "SPY_BEAR_TREND",
    "SPY_DD60_BELOW_10",
    "SPY_MOM60_NEGATIVE",
    "SPY_MOM60_NEGATIVE_BELOW_SMA200",
)
ACTIONS = (
    "SHY_ONLY",
    "MOM60_TOP1",
    "MOM60_TOP2",
    "MIN_VOL20_POSITIVE",
    "SHY_UNLESS_STRONG",
)
PERIODS = {
    "2016-2019": ("2016-01-01", "2019-12-31"),
    "2020-2022": ("2020-01-01", "2022-12-31"),
    "2023-2026": ("2023-01-01", "2026-12-31"),
    "TRAIN_2016-2021": ("2016-01-01", "2021-12-31"),
    "TEST_2022-2026": ("2022-01-01", "2026-12-31"),
}
CRISES = {
    "Q4_2018": ("2018-09-20", "2018-12-31"),
    "COVID_2020": ("2020-02-19", "2020-03-23"),
    "BEAR_2022": ("2022-01-03", "2022-10-12"),
}


def construir_features(historicos):
    features = {}
    for symbol, frame in historicos.items():
        close = frame["close"]
        features[symbol] = pd.DataFrame({
            "momentum60": close.pct_change(60),
            "volatility20": close.pct_change().rolling(20).std(),
            "sma50": close.rolling(50).mean(),
            "sma200": close.rolling(200).mean(),
            "drawdown60": close / close.rolling(60).max() - 1,
        }, index=frame.index)
    return features


def detectar_risk_off(spy_features, regla):
    precio = spy_features["close"] if "close" in spy_features else None
    if precio is None:
        raise ValueError("spy_features debe incluir close")
    if regla == "SPY_BELOW_SMA200":
        señal = precio < spy_features["sma200"]
    elif regla == "SPY_BEAR_TREND":
        señal = (precio < spy_features["sma200"]) & (spy_features["sma50"] < spy_features["sma200"])
    elif regla == "SPY_DD60_BELOW_10":
        señal = spy_features["drawdown60"] < -0.10
    elif regla == "SPY_MOM60_NEGATIVE":
        señal = spy_features["momentum60"] < 0
    elif regla == "SPY_MOM60_NEGATIVE_BELOW_SMA200":
        señal = (spy_features["momentum60"] < 0) & (precio < spy_features["sma200"])
    else:
        raise ValueError(f"Regla risk-off desconocida: {regla}")
    return señal.fillna(False).astype(bool)


def seleccionar_defensivos(features, fecha, accion):
    filas = []
    for symbol in DEFENSIVE_ASSETS:
        frame = features.get(symbol)
        if frame is None or fecha not in frame.index:
            continue
        fila = frame.loc[fecha]
        filas.append((symbol, fila["momentum60"], fila["volatility20"]))
    validos = [(s, m, v) for s, m, v in filas if pd.notna(m)]
    if accion == "SHY_ONLY" or not validos:
        return {"SHY": 1.0}
    if accion == "MOM60_TOP1":
        return {max(validos, key=lambda x: (x[1], x[0]))[0]: 1.0}
    if accion == "MOM60_TOP2":
        top = sorted(validos, key=lambda x: (x[1], x[0]), reverse=True)[:2]
        return {s: 1 / len(top) for s, _, _ in top}
    if accion == "MIN_VOL20_POSITIVE":
        positivos = [(s, m, v) for s, m, v in validos if m > 0 and pd.notna(v)]
        return {min(positivos, key=lambda x: (x[2], x[0]))[0]: 1.0} if positivos else {"SHY": 1.0}
    if accion == "SHY_UNLESS_STRONG":
        shy = next((m for s, m, _ in validos if s == "SHY"), 0.0)
        mejor = max(validos, key=lambda x: (x[1], x[0]))
        # "Clearly positive" is fixed ex ante as +2 percentage points vs SHY.
        return {mejor[0]: 1.0} if mejor[0] != "SHY" and mejor[1] > 0 and mejor[1] > shy + 0.02 else {"SHY": 1.0}
    raise ValueError(f"Accion defensiva desconocida: {accion}")


def fechas_señal(calendario, risk_off, frecuencia):
    calendario = pd.DatetimeIndex(calendario)
    if frecuencia == "monthly":
        return [calendario[0], *fechas_rebalanceo(calendario, "monthly")]
    if frecuencia != "regime_change":
        raise ValueError("frecuencia debe ser monthly o regime_change")
    cambios = risk_off.ne(risk_off.shift(1)).fillna(True)
    return [f for f in calendario if bool(cambios.get(f, False))]


def simular_defensive(historicos, features, risk_off, accion, frecuencia):
    calendario = historicos["SPY"].index
    señales = fechas_señal(calendario, risk_off, frecuencia)
    posiciones = {f: i for i, f in enumerate(calendario)}
    ejecuciones = {calendario[posiciones[f] + 1]: f for f in señales if posiciones[f] + 1 < len(calendario)}
    cash, shares, total_costs = INITIAL_CAPITAL, {}, 0.0
    registros = []
    estado_risk_off = False
    for fecha in calendario:
        coste = turnover = 0.0
        rebalance = False
        if fecha in ejecuciones:
            señal = ejecuciones[fecha]
            estado_risk_off = bool(risk_off.at[señal])
            weights = seleccionar_defensivos(features, señal, accion) if estado_risk_off else {"SPY": 1.0}
            opens = {s: float(historicos[s].at[fecha, "open"]) for s in set(shares) | set(weights) if fecha in historicos[s].index}
            actual = {s: q * opens.get(s, 0.0) for s, q in shares.items()}
            equity_open = cash + sum(actual.values())
            weights = {s: w for s, w in weights.items() if s in opens}
            suma = sum(weights.values())
            weights = {s: w / suma for s, w in weights.items()} if suma else {}
            target_total = equity_open
            for _ in range(4):
                targets = {s: target_total * w for s, w in weights.items()}
                traded = sum(abs(targets.get(s, 0) - actual.get(s, 0)) for s in set(targets) | set(actual))
                target_total = max(equity_open - traded * TRANSACTION_COST, 0.0) if weights else 0.0
            targets = {s: target_total * w for s, w in weights.items()}
            traded = sum(abs(targets.get(s, 0) - actual.get(s, 0)) for s in set(targets) | set(actual))
            coste = traded * TRANSACTION_COST
            shares = {s: target / opens[s] for s, target in targets.items() if target > 0}
            cash = max(equity_open - sum(targets.values()) - coste, 0.0)
            turnover = traded / equity_open if equity_open else 0.0
            total_costs += coste
            rebalance = True
        invested = sum(q * float(historicos[s].at[fecha, "close"]) for s, q in shares.items())
        registros.append({
            "date": fecha, "equity": cash + invested, "cash": cash,
            "invested": invested, "is_invested": bool(shares),
            "holdings": "+".join(sorted(shares)) if shares else "CASH",
            "risk_off": estado_risk_off, "transaction_cost": coste,
            "turnover": turnover, "did_rebalance": rebalance,
        })
    curva = pd.DataFrame(registros).set_index("date")
    curva.attrs["total_costs"] = total_costs
    return curva


def _metricas_extra(curva):
    episodios = episodios_drawdown(curva)
    max_underwater = episodios["underwater_sessions"].max() if not episodios.empty else 0
    max_recovery = episodios["recovery_sessions"].max() if not episodios.empty else 0
    base = calcular_metricas(curva, INITIAL_CAPITAL)
    base.update({
        "max_underwater_sessions": max_underwater,
        "max_recovery_sessions": max_recovery,
        "defensive_time_pct": curva.get("risk_off", pd.Series(False, index=curva.index)).mean() * 100,
    })
    if "risk_off" in curva:
        retornos = curva["equity"].pct_change().fillna(0.0)
        solo_risk = retornos.where(curva["risk_off"].astype(bool), 0.0)
        path = (1 + solo_risk).cumprod()
        base["risk_off_return"] = (path.iloc[-1] - 1) * 100
        base["risk_off_max_drawdown"] = (path / path.cummax() - 1).min() * 100
    return base


def _tramo_normalizado(curva, start, end):
    tramo = curva.loc[start:end].copy()
    if len(tramo) < 2:
        return None
    return _metricas_extra(tramo.assign(equity=tramo["equity"] / tramo["equity"].iloc[0] * INITIAL_CAPITAL))


def _metricas_crisis(curva, start, end):
    metricas = _tramo_normalizado(curva, start, end)
    tramo = curva.loc[start:end]
    if metricas is None or tramo.empty:
        return None
    equity = tramo["equity"]
    drawdown = equity / equity.cummax() - 1
    trough = drawdown.idxmin()
    peak = equity.loc[:trough].idxmax()
    recuperadas = curva.loc[trough:]
    recuperadas = recuperadas[recuperadas["equity"] >= equity.at[peak]]
    recovery = recuperadas.index[0] if len(recuperadas) else pd.NaT
    metricas.update({
        "peak_date": peak, "trough_date": trough, "recovery_date": recovery,
        "recovery_sessions_full": (
            len(curva.loc[trough:recovery]) - 1 if pd.notna(recovery) else np.nan
        ),
    })
    return metricas


def analizar_activaciones(regla, risk_off, historicos):
    cambios = risk_off.ne(risk_off.shift(1)).fillna(False)
    inicios = list(risk_off.index[cambios & risk_off])
    filas = []
    for numero, inicio in enumerate(inicios, 1):
        posteriores = risk_off.loc[inicio:]
        finales = posteriores.index[(~posteriores) & posteriores.ne(posteriores.shift(1))]
        fin = finales[0] if len(finales) else risk_off.index[-1]
        spy = historicos["SPY"].loc[inicio:fin, "close"]
        retorno = (spy.iloc[-1] / spy.iloc[0] - 1) * 100
        filas.append({
            "rule": regla, "activation": numero, "start": inicio, "end": fin,
            "sessions": len(spy), "spy_return": retorno,
            "spy_fell": retorno < 0, "spy_rose": retorno > 0,
            "opportunity_cost_proxy": max(retorno, 0.0),
        })
    return filas


def analizar_activos(strategy_id, curva):
    pnl = curva["equity"].diff().fillna(0.0)
    filas = []
    for symbol in DEFENSIVE_ASSETS:
        mascara = curva["risk_off"] & curva["holdings"].str.split("+").apply(lambda x: symbol in x)
        numero_holdings = curva["holdings"].str.split("+").apply(len).clip(lower=1)
        pnl_asignado = (pnl / numero_holdings).where(mascara, 0.0)
        equity_sintetica = INITIAL_CAPITAL + pnl_asignado.cumsum()
        dd = (equity_sintetica / equity_sintetica.cummax() - 1).min() * 100
        segmentos = (mascara & ~mascara.shift(1, fill_value=False)).sum()
        filas.append({
            "strategy_id": strategy_id, "asset": symbol,
            "times_selected": int(segmentos), "sessions_held": int(mascara.sum()),
            "time_pct": mascara.mean() * 100, "pnl_contribution": pnl_asignado.sum(),
            "mean_daily_return_selected": curva["equity"].pct_change().where(mascara).mean() * 100,
            "max_drawdown_selected": dd,
        })
    return filas


def ejecutar_analisis(historicos, start="2016-01-01"):
    calendario = historicos["SPY"].loc[start:].index
    historicos = {s: df.reindex(calendario).dropna() for s, df in historicos.items()}
    features = construir_features(historicos)
    features["SPY"]["close"] = historicos["SPY"]["close"]
    resultados, periodos, crisis, activaciones, activos, curvas = [], [], [], [], [], []

    variantes = []
    for regla in RISK_RULES:
        risk = detectar_risk_off(features["SPY"], regla)
        activaciones.extend(analizar_activaciones(regla, risk, historicos))
        for accion in ACTIONS:
            for frecuencia in ("monthly", "regime_change"):
                variantes.append((regla, accion, frecuencia, risk))

    # Benchmarks use the same next-open engine with an always-on selector.
    always = pd.Series(True, index=calendario)
    benchmarks = {
        "CASH_0": None,
        "SHY_BUY_HOLD": "SHY_ONLY",
        "IEF_BUY_HOLD": "IEF",
        "GLD_BUY_HOLD": "GLD",
    }
    for nombre, accion in benchmarks.items():
        if nombre == "CASH_0":
            curva = pd.DataFrame({"equity": INITIAL_CAPITAL, "holdings": "CASH", "risk_off": True,
                                  "is_invested": False, "turnover": 0.0, "transaction_cost": 0.0,
                                  "did_rebalance": False}, index=calendario)
        else:
            symbol = "SHY" if accion == "SHY_ONLY" else accion
            curva = simular_cartera(
                historicos, [calendario[0]], lambda _, s=symbol: {s: 1.0}
            )
            curva["risk_off"] = True
        resultados.append({"strategy_id": nombre, "kind": "benchmark",
                           "outside_defensive": "N/A", **_metricas_extra(curva)})
        for periodo, (desde, hasta) in PERIODS.items():
            metricas = _tramo_normalizado(curva, desde, hasta)
            if metricas:
                periodos.append({"strategy_id": nombre, "period": periodo, **metricas})
        for episodio, (desde, hasta) in CRISES.items():
            metricas = _metricas_crisis(curva, desde, hasta)
            if metricas:
                tramo = curva.loc[desde:hasta]
                crisis.append({"strategy_id": nombre, "episode": episodio,
                               "holdings": ",".join(sorted(tramo["holdings"].unique())), **metricas})
        curvas.append((nombre, curva))

    # Existing comparison benchmarks are read from the validated phase-2 curves.
    fase2 = pd.read_csv(OUTPUT_DIR.parent / "research_etf" / "etf_rotation_equity.csv", parse_dates=["date"])
    for nombre, sid in (("SPY_BUY_HOLD", "SPY_BUY_HOLD"), ("BALANCED_60_40", "BENCHMARK_60_40")):
        curva = fase2[fase2["strategy_id"] == sid].set_index("date").loc[calendario[0]:calendario[-1]]
        resultados.append({"strategy_id": nombre, "kind": "benchmark",
                           "outside_defensive": "N/A", **_metricas_extra(curva)})
        for periodo, (desde, hasta) in PERIODS.items():
            metricas = _tramo_normalizado(curva, desde, hasta)
            if metricas:
                periodos.append({"strategy_id": nombre, "period": periodo, **metricas})
        for episodio, (desde, hasta) in CRISES.items():
            metricas = _metricas_crisis(curva, desde, hasta)
            if metricas:
                tramo = curva.loc[desde:hasta]
                crisis.append({"strategy_id": nombre, "episode": episodio,
                               "holdings": ",".join(sorted(tramo["holdings"].unique())), **metricas})
        curvas.append((nombre, curva))

    for regla, accion, frecuencia, risk in variantes:
        sid = f"{regla}|{accion}|{frecuencia}"
        curva = simular_defensive(historicos, features, risk, accion, frecuencia)
        resultados.append({"strategy_id": sid, "kind": "defensive", "rule": regla,
                           "action": accion, "frequency": frecuencia,
                           "is_defensive_simple": accion == "SHY_ONLY",
                           "outside_defensive": "SPY_PLACEHOLDER", **_metricas_extra(curva)})
        for periodo, (desde, hasta) in PERIODS.items():
            metricas = _tramo_normalizado(curva, desde, hasta)
            if metricas:
                periodos.append({"strategy_id": sid, "period": periodo, **metricas})
        for episodio, (desde, hasta) in CRISES.items():
            metricas = _metricas_crisis(curva, desde, hasta)
            if metricas:
                tramo = curva.loc[desde:hasta]
                crisis.append({"strategy_id": sid, "episode": episodio,
                               "holdings": ",".join(sorted(tramo["holdings"].unique())), **metricas})
        activos.extend(analizar_activos(sid, curva))
        curvas.append((sid, curva))

    resultados = pd.DataFrame(resultados)
    periodos = pd.DataFrame(periodos)
    crisis = pd.DataFrame(crisis)
    activaciones = pd.DataFrame(activaciones)
    activos = pd.DataFrame(activos)
    rolling = []
    spy = dict(curvas)["SPY_BUY_HOLD"]
    for sid, curva in curvas:
        for fila in rolling_summary(curva, spy).to_dict("records"):
            rolling.append({"strategy_id": sid, **fila})
    return resultados, periodos, crisis, activaciones, activos, pd.DataFrame(rolling)


def imprimir_resumen(resultados, periodos, crisis, activaciones, activos):
    print("\nDEFENSIVE RESEARCH - EXPLORATORY (NO DEFENSIVE V1)")
    print("=" * 88)
    for nombre in ("SHY_BUY_HOLD", "IEF_BUY_HOLD", "GLD_BUY_HOLD", "BALANCED_60_40", "SPY_BUY_HOLD", "CASH_0"):
        f = resultados[resultados["strategy_id"] == nombre].iloc[0]
        print(f"{nombre:<22} CAGR {f['cagr']:+6.2f}% | MaxDD {f['max_drawdown']:+6.2f}% | Sharpe {f['sharpe']:.2f}")
    defensivas = resultados[resultados["kind"] == "defensive"]
    for titulo, columna in (("MENOR MAXDD", "max_drawdown"), ("MEJOR SHARPE", "sharpe"), ("MEJOR CALMAR", "calmar")):
        print(f"\n{titulo}")
        for _, f in defensivas.sort_values(columna, ascending=False).head(5).iterrows():
            print(f"  {f['strategy_id']:<70} CAGR {f['cagr']:+.2f}% | DD {f['max_drawdown']:+.2f}% | Sharpe {f['sharpe']:.2f} | Calmar {f['calmar']:.2f}")
    print("\nFalsos positivos por regla")
    for regla, grupo in activaciones.groupby("rule"):
        print(f"  {regla:<42} n={len(grupo):2d} | SPY sube {grupo['spy_rose'].mean()*100:5.1f}% | coste oportunidad {grupo['opportunity_cost_proxy'].sum():+.2f}pp")
    print("\nTRAIN/TEST, crisis, rolling y dependencia por activo guardados en CSV.")


def parse_args():
    parser = argparse.ArgumentParser(description="Investigacion defensiva aislada")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    historicos = {}
    for symbol in DOWNLOAD_ASSETS:
        historicos[symbol] = obtener_precios(
            symbol, start - timedelta(days=400), end,
            refresh=args.refresh_cache, cache_dir=CACHE_DIR,
        )
    salidas = ejecutar_analisis(historicos, args.start)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nombres = ("defensive_results.csv", "defensive_periods.csv", "defensive_crises.csv",
               "defensive_activations.csv", "defensive_assets.csv", "defensive_rolling.csv")
    for nombre, frame in zip(nombres, salidas):
        frame.to_csv(OUTPUT_DIR / nombre, index=False)
    imprimir_resumen(*salidas[:5])


if __name__ == "__main__":
    main()
