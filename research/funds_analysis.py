"""Métricas y validación walk-forward para fondos a frecuencia mensual."""

import numpy as np
import pandas as pd


MESES_AÑO = 12


def serie_mensual(datos, columna="nav"):
    serie = datos.set_index("date")[columna].astype(float).sort_index().dropna()
    serie.index = pd.to_datetime(serie.index)
    return serie[~serie.index.to_period("M").duplicated(keep="last")]


def retorno_anualizado(serie):
    if len(serie) < 2:
        return np.nan
    años = (serie.index[-1] - serie.index[0]).days / 365.25
    return (serie.iloc[-1] / serie.iloc[0]) ** (1 / años) - 1 if años > 0 else np.nan


def max_drawdown(serie):
    return (serie / serie.cummax() - 1).min() if len(serie) else np.nan


def recovery_months(serie):
    if len(serie) < 2:
        return np.nan
    maximo, inicio, peor = serie.iloc[0], None, 0
    for fecha, valor in serie.items():
        if valor >= maximo:
            if inicio is not None:
                peor = max(peor, (fecha.year - inicio.year) * 12 + fecha.month - inicio.month)
                inicio = None
            maximo = valor
        elif inicio is None:
            inicio = fecha
    return float(peor) if peor else np.nan


def calcular_metricas(serie, benchmark=None):
    serie = serie.dropna().sort_index()
    retornos = serie.pct_change().dropna()
    años = retornos.resample("YE").apply(lambda x: (1 + x).prod() - 1)
    cagr = retorno_anualizado(serie)
    vol = retornos.std(ddof=1) * np.sqrt(MESES_AÑO) if len(retornos) >= 2 else np.nan
    downside = retornos[retornos < 0].std(ddof=1) * np.sqrt(MESES_AÑO)
    dd = max_drawdown(serie)
    sharpe = retornos.mean() / retornos.std(ddof=1) * np.sqrt(MESES_AÑO) if retornos.std(ddof=1) > 0 else np.nan
    sortino = retornos.mean() * MESES_AÑO / downside if pd.notna(downside) and downside > 0 else np.nan
    rolling12 = serie.pct_change(12)
    rolling36 = (serie / serie.shift(36)) ** (1 / 3) - 1
    rolling60 = (serie / serie.shift(60)) ** (1 / 5) - 1
    salida = {
        "first_available_date": serie.index.min().date() if len(serie) else None,
        "last_available_date": serie.index.max().date() if len(serie) else None,
        "observations": len(serie), "total_return": (serie.iloc[-1] / serie.iloc[0] - 1) if len(serie) >= 2 else np.nan,
        "cagr": cagr, "annualized_volatility": vol, "max_drawdown": dd,
        "sharpe": sharpe, "sortino": sortino,
        "calmar": cagr / abs(dd) if pd.notna(cagr) and pd.notna(dd) and dd < 0 else np.nan,
        "worst_year": años.min() if len(años) else np.nan, "best_year": años.max() if len(años) else np.nan,
        "positive_years_pct": (años > 0).mean() if len(años) else np.nan,
        "rolling_1y_last": rolling12.dropna().iloc[-1] if rolling12.notna().any() else np.nan,
        "rolling_3y_annualized_mean": rolling36.mean(), "rolling_5y_annualized_mean": rolling60.mean(),
        "recovery_months_max": recovery_months(serie),
    }
    if benchmark is not None:
        comun = pd.concat([serie.rename("fund"), benchmark.rename("bench")], axis=1).dropna()
        if len(comun) >= 13:
            fr, br = comun.pct_change().dropna().T.values
            bcagr = retorno_anualizado(comun["bench"])
            beta = np.cov(fr, br, ddof=1)[0, 1] / np.var(br, ddof=1) if np.var(br, ddof=1) > 0 else np.nan
            fa = fr.reshape(-1)
            ba = br.reshape(-1)
            anual_f = comun["fund"].pct_change().dropna().resample("YE").apply(lambda x: (1 + x).prod() - 1)
            anual_b = comun["bench"].pct_change().dropna().resample("YE").apply(lambda x: (1 + x).prod() - 1)
            rolling_f = comun["fund"].pct_change(12)
            rolling_b = comun["bench"].pct_change(12)
            salida.update({
                "benchmark_common_start": comun.index[0].date(), "benchmark_common_observations": len(comun),
                "benchmark_cagr": bcagr, "cagr_difference": retorno_anualizado(comun["fund"]) - bcagr,
                "excess_annualized_return": (fa - ba).mean() * 12,
                "tracking_difference": (fa - ba).mean() * 12,
                "correlation": np.corrcoef(fa, ba)[0, 1], "beta": beta,
                "annual_hit_rate": (anual_f > anual_b).mean(),
                "rolling_outperformance_frequency": (rolling_f > rolling_b).dropna().mean(),
            })
    return salida


def _score_snapshot(serie, fecha, metodo):
    pasado = serie.loc[:fecha]
    ventana = {"RETURN_12M": 12, "RETURN_36M": 36, "RETURN_60M": 60}.get(metodo, 36)
    if len(pasado) < ventana + 1:
        return np.nan
    tramo = pasado.iloc[-ventana - 1:]
    ret = tramo.iloc[-1] / tramo.iloc[0] - 1
    if metodo in ("RETURN_12M", "RETURN_36M", "RETURN_60M"):
        return ret
    if metodo == "RETURN_36M_DRAWDOWN":
        return ret + max_drawdown(tramo)
    if metodo == "RETURN_36M_SHARPE":
        r = tramo.pct_change().dropna()
        return r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else np.nan
    rolling = tramo.pct_change(12).dropna()
    return (rolling > 0).mean() if len(rolling) else np.nan


def analizar_persistencia(series, benchmarks, universo, horizontes=(12, 24, 36)):
    metodos = ("RETURN_12M", "RETURN_36M", "RETURN_60M", "RETURN_36M_DRAWDOWN", "RETURN_36M_SHARPE", "CONSISTENCY")
    meta = universo.set_index("isin")
    finales = [s.index.max() for s in series.values() if len(s)]
    if not finales:
        return pd.DataFrame()
    fechas = pd.date_range("2017-12-31", min(finales), freq="YE")
    filas = []
    for fecha in fechas:
        for metodo in metodos:
            scores = {isin: _score_snapshot(s, fecha, metodo) for isin, s in series.items()}
            validos = sorted(((i, v) for i, v in scores.items() if pd.notna(v)), key=lambda x: x[1], reverse=True)
            for rango, (isin, score) in enumerate(validos, 1):
                tercil = "TOP" if rango <= max(1, len(validos) // 3) else ("BOTTOM" if rango > len(validos) - max(1, len(validos) // 3) else "MIDDLE")
                for horizonte in horizontes:
                    futuro = series[isin].loc[series[isin].index > fecha].iloc[:horizonte]
                    if len(futuro) < horizonte:
                        continue
                    retorno = futuro.iloc[-1] / series[isin].loc[:fecha].iloc[-1] - 1
                    bench = benchmarks.get(meta.at[isin, "benchmark"])
                    bpasado = bench.loc[:fecha] if bench is not None else pd.Series(dtype=float)
                    bfuturo = bench.loc[bench.index > fecha].iloc[:horizonte] if bench is not None else pd.Series(dtype=float)
                    bret = bfuturo.iloc[-1] / bpasado.iloc[-1] - 1 if len(bfuturo) >= horizonte and len(bpasado) else np.nan
                    filas.append({"ranking_date": fecha.date(), "method": metodo, "isin": isin,
                                  "rank": rango, "group": tercil, "universe_size": len(validos),
                                  "forward_months": horizonte, "forward_return": retorno,
                                  "benchmark_forward_return": bret, "forward_excess": retorno - bret})
    return pd.DataFrame(filas)


def estrategias_simples(series, benchmarks, universo, frecuencia="annual"):
    meta = universo.set_index("isin")
    finales = [s.index.max() for s in series.values() if len(s)]
    if not finales:
        return pd.DataFrame()
    freq = "YE" if frecuencia == "annual" else "6ME"
    fechas = pd.date_range("2018-12-31", min(finales), freq=freq)
    filas = []
    for fecha in fechas:
        features = []
        for isin, serie in series.items():
            tramo = serie.loc[:fecha].iloc[-37:]
            if len(tramo) < 37:
                continue
            ret = tramo.iloc[-1] / tramo.iloc[0] - 1
            r = tramo.pct_change().dropna()
            features.append({"isin": isin, "return36": ret, "sharpe36": r.mean() / r.std(ddof=1) if r.std(ddof=1) else np.nan,
                             "drawdown36": max_drawdown(tramo), "consistency": (tramo.pct_change(12).dropna() > 0).mean()})
        f = pd.DataFrame(features).dropna()
        if f.empty:
            continue
        f["balanced"] = f["return36"].rank(pct=True) + f["drawdown36"].rank(pct=True)
        selecciones = {
            "A_TOP1_RETURN36": f.nlargest(1, "return36"), "B_TOP3_RETURN36": f.nlargest(3, "return36"),
            "C_TOP3_SHARPE36": f.nlargest(3, "sharpe36"), "D_TOP3_RETURN_DD": f.nlargest(3, "balanced"),
            "E_TOP3_CONSISTENCY": f.nlargest(3, "consistency"),
        }
        for nombre, elegidos in selecciones.items():
            retornos, benchmark_returns = [], []
            for isin in elegidos["isin"]:
                pasado = series[isin].loc[:fecha]
                futuro = series[isin].loc[series[isin].index > fecha].iloc[:12]
                if len(pasado) and len(futuro) == 12:
                    retornos.append(futuro.iloc[-1] / pasado.iloc[-1] - 1)
                    bench = benchmarks.get(meta.at[isin, "benchmark"])
                    if bench is not None:
                        bp, bf = bench.loc[:fecha], bench.loc[bench.index > fecha].iloc[:12]
                        if len(bp) and len(bf) == 12:
                            benchmark_returns.append(bf.iloc[-1] / bp.iloc[-1] - 1)
            if retornos:
                filas.append({"rebalance_date": fecha.date(), "frequency": frecuencia, "strategy": nombre,
                              "selected_isins": "|".join(elegidos["isin"]), "fund_return_12m": np.mean(retornos),
                              "category_benchmark_return_12m": np.mean(benchmark_returns) if benchmark_returns else np.nan,
                              "category_excess_12m": np.mean(retornos) - np.mean(benchmark_returns) if benchmark_returns else np.nan})
    return pd.DataFrame(filas)
