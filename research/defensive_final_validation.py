"""Final validation of two frozen Defensive finalists; no production strategy."""

import argparse
from datetime import date, timedelta

import numpy as np
import pandas as pd

from research.defensive_analysis import (
    BASE_DIR,
    DEFENSIVE_ASSETS,
    OUTPUT_DIR,
    PERIODS,
    construir_features,
    detectar_risk_off,
    seleccionar_defensivos,
    simular_defensive,
)
from research.etf_factor_analysis import CACHE_DIR, obtener_precios
from research.etf_final_validation import episodios_drawdown
from research.etf_rotation_analysis import INITIAL_CAPITAL, calcular_metricas, simular_cartera


FINALISTS = {
    "DEFENSIVE_SIMPLE": "SHY_ONLY",
    "DEFENSIVE_TOP2": "MOM60_TOP2",
}
BENCHMARK_IDS = {
    "SPY": "SPY_BUY_HOLD",
    "BALANCED_60_40": "BENCHMARK_60_40",
}
FIXED_CRISIS = {
    "Q4_2018": ("2018-09-20", "2018-12-31"),
    "COVID_2020": ("2020-02-19", "2020-03-23"),
    "BEAR_2022": ("2022-01-03", "2022-10-12"),
}


def construir_finalistas(historicos, start="2016-01-01"):
    calendario = historicos["SPY"].loc[start:].index
    historicos = {s: df.reindex(calendario).dropna() for s, df in historicos.items()}
    features = construir_features(historicos)
    features["SPY"]["close"] = historicos["SPY"]["close"]
    risk = detectar_risk_off(features["SPY"], "SPY_MOM60_NEGATIVE")
    curvas = {
        nombre: simular_defensive(historicos, features, risk, accion, "monthly")
        for nombre, accion in FINALISTS.items()
    }
    curvas["SHY"] = simular_cartera(historicos, [calendario[0]], lambda _: {"SHY": 1.0})
    fase2 = pd.read_csv(OUTPUT_DIR.parent / "research_etf" / "etf_rotation_equity.csv", parse_dates=["date"])
    for nombre, sid in BENCHMARK_IDS.items():
        curvas[nombre] = fase2[fase2["strategy_id"] == sid].set_index("date").loc[calendario[0]:calendario[-1]]
    return historicos, features, risk, curvas


def resultado_anual(nombre, curva, spy):
    filas = []
    for year, equity in curva["equity"].groupby(curva.index.year):
        base = curva.loc[curva.index < equity.index[0], "equity"]
        inicial = base.iloc[-1] if len(base) else INITIAL_CAPITAL
        retornos = equity.pct_change().dropna()
        retorno = (equity.iloc[-1] / inicial - 1) * 100
        dd = (pd.concat([pd.Series([inicial], index=[equity.index[0] - pd.Timedelta(days=1)]), equity]) /
              pd.concat([pd.Series([inicial], index=[equity.index[0] - pd.Timedelta(days=1)]), equity]).cummax() - 1).min() * 100
        spy_eq = spy.loc[equity.index, "equity"]
        spy_base = spy.loc[spy.index < spy_eq.index[0], "equity"]
        spy_inicial = spy_base.iloc[-1] if len(spy_base) else INITIAL_CAPITAL
        spy_return = (spy_eq.iloc[-1] / spy_inicial - 1) * 100
        filas.append({
            "series": nombre, "year": int(year), "return": retorno,
            "max_drawdown": dd,
            "volatility": retornos.std(ddof=1) * np.sqrt(252) * 100,
            "sharpe": retornos.mean() / retornos.std(ddof=1) * np.sqrt(252) if retornos.std(ddof=1) > 0 else 0.0,
            "defensive_time_pct": curva.loc[equity.index, "risk_off"].mean() * 100 if "risk_off" in curva else 0.0,
            "opportunity_cost_vs_spy": spy_return - retorno,
        })
    return filas


def activaciones_finales(historicos, features, risk, curvas):
    calendario = risk.index
    cambios = risk.ne(risk.shift(1)).fillna(False)
    filas = []
    for inicio in calendario[cambios & risk]:
        posteriores = risk.loc[inicio:]
        finales = posteriores.index[(~posteriores) & posteriores.ne(posteriores.shift(1))]
        fin = finales[0] if len(finales) else calendario[-1]
        señales_mes = pd.Series(calendario, index=calendario).groupby(calendario.to_period("M")).last()
        validas = [f for f in señales_mes if f >= inicio and f <= fin and bool(risk.at[f])]
        señal = validas[0] if validas else pd.NaT
        efectiva = calendario[calendario.get_loc(señal) + 1] if pd.notna(señal) and calendario.get_loc(señal) + 1 < len(calendario) else pd.NaT
        spy_close = historicos["SPY"]["close"]
        spy_tramo = spy_close.loc[inicio:fin]
        spy_ret = (spy_tramo.iloc[-1] / spy_tramo.iloc[0] - 1) * 100
        spy_dd = (spy_tramo / spy_tramo.cummax() - 1).min() * 100
        for nombre in FINALISTS:
            curva = curvas[nombre].loc[inicio:fin]
            defensive_ret = (curva["equity"].iloc[-1] / curva["equity"].iloc[0] - 1) * 100
            defensive_dd = (curva["equity"] / curva["equity"].cummax() - 1).min() * 100
            diferencia = defensive_ret - spy_ret
            etiqueta = "GOOD_DEFENSE" if diferencia > 2 else (
                "FALSE_POSITIVE" if spy_ret > 0 and diferencia < -2 else "NEUTRAL"
            )
            filas.append({
                "series": nombre, "signal_date": inicio, "effective_entry": efectiva,
                "monthly_signal_date": señal, "spy_level": spy_close.at[inicio],
                "momentum60": features["SPY"].at[inicio, "momentum60"],
                "risk_off_sessions": len(spy_tramo),
                "defensive_assets": "+".join(sorted(set(curva["holdings"]) - {"SPY"})) or "NONE",
                "defensive_return": defensive_ret, "spy_return": spy_ret,
                "difference": diferencia, "defensive_maxdd": defensive_dd,
                "spy_maxdd": spy_dd, "classification": etiqueta,
            })
    return pd.DataFrame(filas)


def _drawdown_window(equity, peak, recovery):
    return equity.loc[peak:recovery] if pd.notna(recovery) else equity.loc[peak:]


def detectar_crisis_spy(spy_curve):
    episodios = episodios_drawdown(spy_curve)
    ventanas = dict(FIXED_CRISIS)
    for i, fila in episodios[episodios["drawdown_pct"] <= -10].iterrows():
        ventanas[f"AUTO_SPY_DD_{len(ventanas)+1}"] = (
            str(pd.Timestamp(fila["peak_date"]).date()),
            str(pd.Timestamp(fila["trough_date"]).date()),
        )
    return ventanas


def analizar_crisis(curvas, risk, features):
    filas = []
    calendario = risk.index
    for episodio, (start, end) in detectar_crisis_spy(curvas["SPY"]).items():
        inicio, fin = pd.Timestamp(start), pd.Timestamp(end)
        spy = curvas["SPY"]["equity"].loc[inicio:fin]
        peak = spy.idxmax() if episodio.startswith("AUTO") else spy.index[0]
        negativos = features["SPY"].loc[peak:, "momentum60"] < 0
        momentum_date = negativos.index[negativos][0] if negativos.any() else pd.NaT
        mes_signals = pd.Series(calendario, index=calendario).groupby(calendario.to_period("M")).last()
        validas = [f for f in mes_signals if pd.notna(momentum_date) and f >= momentum_date and bool(risk.at[f])]
        señal = validas[0] if validas else pd.NaT
        entrada = calendario[calendario.get_loc(señal) + 1] if pd.notna(señal) and calendario.get_loc(señal) + 1 < len(calendario) else pd.NaT
        pre_damage = (
            (curvas["SPY"].at[entrada, "equity"] / curvas["SPY"].at[peak, "equity"] - 1) * 100
            if pd.notna(entrada) and entrada in curvas["SPY"].index else np.nan
        )
        for nombre, curva in curvas.items():
            tramo = curva["equity"].loc[inicio:fin]
            dd = (tramo / tramo.cummax() - 1).min() * 100
            retorno = (tramo.iloc[-1] / tramo.iloc[0] - 1) * 100
            trough = tramo.idxmin()
            objetivo = tramo.loc[:trough].max()
            recuperadas = curva.loc[trough:][curva.loc[trough:, "equity"] >= objetivo]
            recovery = recuperadas.index[0] if len(recuperadas) else pd.NaT
            holdings = "+".join(sorted(curva.loc[inicio:fin, "holdings"].astype(str).unique()))
            filas.append({
                "episode": episodio, "series": nombre, "start": inicio, "end": fin,
                "return": retorno, "max_drawdown": dd, "holdings": holdings,
                "spy_peak_date": peak, "momentum_negative_date": momentum_date,
                "monthly_signal_date": señal, "defensive_entry_date": entrada,
                "entry_delay_sessions": len(calendario[(calendario > peak) & (calendario <= entrada)]) if pd.notna(entrada) else np.nan,
                "spy_loss_before_defense": pre_damage, "recovery_date": recovery,
                "recovery_sessions": len(curva.loc[trough:recovery]) - 1 if pd.notna(recovery) else np.nan,
            })
    return pd.DataFrame(filas)


def analizar_drawdowns(curvas):
    filas = []
    for nombre, curva in curvas.items():
        episodios = episodios_drawdown(curva).head(5)
        for rank, (_, fila) in enumerate(episodios.iterrows(), 1):
            filas.append({"series": nombre, "rank": rank, **fila.to_dict()})
    return pd.DataFrame(filas)


def rolling_final(curvas, windows=(252, 756, 1260)):
    filas = []
    spy = curvas["SPY"]["equity"]
    for nombre, curva in curvas.items():
        equity = curva["equity"]
        for sessions in windows:
            retornos, spy_ret, dds, spy_dds = [], [], [], []
            for fin in range(sessions, len(equity)):
                tramo = equity.iloc[fin-sessions:fin+1]
                tramo_spy = spy.reindex(tramo.index)
                retornos.append((tramo.iloc[-1] / tramo.iloc[0] - 1) * 100)
                spy_ret.append((tramo_spy.iloc[-1] / tramo_spy.iloc[0] - 1) * 100)
                dds.append((tramo / tramo.cummax() - 1).min() * 100)
                spy_dds.append((tramo_spy / tramo_spy.cummax() - 1).min() * 100)
            if retornos:
                r, sr, dd, sdd = map(np.asarray, (retornos, spy_ret, dds, spy_dds))
                filas.append({
                    "series": nombre, "window_years": sessions // 252, "windows": len(r),
                    "median_return": np.median(r), "worst_return": r.min(), "best_return": r.max(),
                    "positive_pct": (r > 0).mean() * 100, "beat_spy_pct": (r > sr).mean() * 100,
                    "lower_drawdown_than_spy_pct": (dd > sdd).mean() * 100,
                })
    return pd.DataFrame(filas)


def oportunidad(curvas):
    filas = []
    spy_daily = curvas["SPY"]["equity"].pct_change().fillna(0)
    for nombre in FINALISTS:
        curva = curvas[nombre]
        mascara = curva["risk_off"].astype(bool)
        defensive = curva["equity"].pct_change().fillna(0)
        spy_risk = (1 + spy_daily.where(mascara, 0)).prod() - 1
        def_risk = (1 + defensive.where(mascara, 0)).prod() - 1
        mensual_def = defensive.where(mascara).resample("ME").sum()
        mensual_spy = spy_daily.where(mascara).resample("ME").sum()
        diferencia_diaria = (defensive - spy_daily).where(mascara, 0.0)
        protection_gained = diferencia_diaria.where(spy_daily < 0, 0.0).clip(lower=0).sum() * 100
        upside_sacrificed = (-diferencia_diaria.where(spy_daily > 0, 0.0)).clip(lower=0).sum() * 100
        filas.append({
            "series": nombre, "spy_return_during_risk_off": spy_risk * 100,
            "defensive_return_during_risk_off": def_risk * 100,
            "protection_vs_spy": (def_risk - spy_risk) * 100,
            "protection_gained": protection_gained,
            "upside_sacrificed": upside_sacrificed,
            "useful_months": int((mensual_def > mensual_spy).sum()),
            "harmful_months": int((mensual_def < mensual_spy).sum()),
        })
    return pd.DataFrame(filas)


def top2_sin_gld(historicos, features, risk):
    diagnostico = {s: f.copy() for s, f in features.items()}
    diagnostico["GLD"]["momentum60"] = np.nan
    return simular_defensive(historicos, diagnostico, risk, "MOM60_TOP2", "monthly")


def scorecard(curvas, periodos, oportunidad_df, assets):
    filas = []
    for nombre, curva in curvas.items():
        m = calcular_metricas(curva, INITIAL_CAPITAL)
        eps = episodios_drawdown(curva)
        train = periodos[(periodos.series == nombre) & (periodos.period == "TRAIN_2016-2021")].iloc[0]
        test = periodos[(periodos.series == nombre) & (periodos.period == "TEST_2022-2026")].iloc[0]
        op = oportunidad_df[oportunidad_df.series == nombre]
        gl = assets[(assets.series == nombre) & (assets.asset == "GLD")]
        operaciones = 0
        anterior = set()
        if "did_rebalance" in curva:
            for _, punto in curva[curva["did_rebalance"].astype(bool)].iterrows():
                actual = set() if punto["holdings"] == "CASH" else set(str(punto["holdings"]).split("+"))
                operaciones += len(anterior | actual)
                anterior = actual
        filas.append({
            "series": nombre, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "sortino": m["sortino"], "calmar": m["calmar"],
            "worst_year": m["worst_year"],
            "max_underwater": eps["underwater_sessions"].max() if not eps.empty else 0,
            "max_recovery": eps["recovery_sessions"].max() if not eps.empty else 0,
            "defensive_time_pct": curva["risk_off"].mean() * 100 if "risk_off" in curva else 0,
            "operations": operaciones, "turnover": m["turnover"],
            "costs": m["total_costs"], "costs_pct_initial": m["total_costs"] / INITIAL_CAPITAL * 100,
            "train_cagr": train.cagr, "test_cagr": test.cagr,
            "train_dd": train.max_drawdown, "test_dd": test.max_drawdown,
            "opportunity_cost": -float(op.iloc[0].protection_vs_spy) if len(op) else np.nan,
            "protection_vs_spy_risk_off": float(op.iloc[0].protection_vs_spy) if len(op) else np.nan,
            "gld_dependency_pct": float(gl.iloc[0].time_pct) if len(gl) else 0.0,
        })
    return pd.DataFrame(filas)


def ejecutar_validacion(historicos, start="2016-01-01"):
    historicos, features, risk, curvas = construir_finalistas(historicos, start)
    yearly = pd.DataFrame(sum((resultado_anual(n, c, curvas["SPY"]) for n, c in curvas.items()), []))
    periodos = []
    for nombre, curva in curvas.items():
        for periodo in ("TRAIN_2016-2021", "TEST_2022-2026"):
            desde, hasta = PERIODS[periodo]
            tramo = curva.loc[desde:hasta].copy()
            normal = tramo.copy()
            normal["equity"] = tramo["equity"] / tramo["equity"].iloc[0] * INITIAL_CAPITAL
            periodos.append({"series": nombre, "period": periodo, **calcular_metricas(normal, INITIAL_CAPITAL),
                             "defensive_time_pct": tramo["risk_off"].mean()*100 if "risk_off" in tramo else 0})
    periodos = pd.DataFrame(periodos)
    activaciones = activaciones_finales(historicos, features, risk, curvas)
    crises = analizar_crisis(curvas, risk, features)
    drawdowns = analizar_drawdowns(curvas)
    rolling = rolling_final(curvas)
    opp = oportunidad(curvas)
    asset_rows = []
    for nombre in FINALISTS:
        curva = curvas[nombre]
        pnl = curva["equity"].diff().fillna(0)
        for asset in DEFENSIVE_ASSETS:
            mask = curva["risk_off"] & curva["holdings"].str.split("+").apply(lambda x: asset in x)
            count = curva["holdings"].str.split("+").apply(len).clip(lower=1)
            asset_rows.append({"series": nombre, "asset": asset,
                               "selections": int((mask & ~mask.shift(1, fill_value=False)).sum()),
                               "sessions": int(mask.sum()), "time_pct": mask.mean()*100,
                               "pnl": (pnl/count).where(mask, 0).sum()})
    assets = pd.DataFrame(asset_rows)
    no_gld = top2_sin_gld(historicos, features, risk)
    no_gld_metrics = pd.DataFrame([{"series": "DEFENSIVE_TOP2_NO_GLD_DIAGNOSTIC",
                                    **calcular_metricas(no_gld, INITIAL_CAPITAL)}])
    card = scorecard(curvas, periodos, opp, assets)
    return card, yearly, activaciones, drawdowns, crises, rolling, periodos, opp, assets, no_gld_metrics


def main():
    parser = argparse.ArgumentParser(description="Validacion final Defensive congelada")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=str(date.today()))
    args = parser.parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    historicos = {s: obtener_precios(s, start-timedelta(days=400), end, cache_dir=CACHE_DIR)
                  for s in ("SPY", *DEFENSIVE_ASSETS)}
    salidas = ejecutar_validacion(historicos, args.start)
    nombres = (
        "defensive_final_scorecard.csv", "defensive_final_yearly.csv",
        "defensive_final_activations.csv", "defensive_final_drawdowns.csv",
        "defensive_final_crises.csv", "defensive_final_rolling.csv",
        "defensive_final_periods.csv", "defensive_final_opportunity.csv",
        "defensive_final_assets.csv", "defensive_final_no_gld.csv",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for nombre, frame in zip(nombres, salidas):
        frame.to_csv(OUTPUT_DIR / nombre, index=False)
    print("\nDEFENSIVE FINAL VALIDATION - NO DEFENSIVE V1")
    print(salidas[0].to_string(index=False))
    print("\nTop-2 sin GLD (solo diagnostico)")
    print(salidas[-1].to_string(index=False))


if __name__ == "__main__":
    main()
