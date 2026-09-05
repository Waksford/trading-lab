"""FUND RESEARCH - PHASE 1. Investigación aislada, sin carteras productivas."""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from providers.cnmv_funds import CACHE_DIR, importar_csv_manual, obtener_nav_cnmv
from research.funds_analysis import (
    analizar_persistencia, calcular_metricas, estrategias_simples, serie_mensual,
)
from research.funds_universe import FUNDS_UNIVERSE


BENCHMARKS = ("SPY", "URTH", "VGK", "EWP", "IEF", "SHY")
TRAIN_END = pd.Timestamp("2021-12-31")
TEST_START = pd.Timestamp("2022-01-01")


def construir_benchmarks(inicio, fin, refresh=False, downloader=None):
    """Benchmarks total-return aproximados mediante precios ajustados por dividendos."""
    cache = CACHE_DIR / "benchmark_monthly.csv"
    if cache.exists() and not refresh:
        datos = pd.read_csv(cache, parse_dates=["date"])
        cubre = (not datos.empty and datos["date"].min().to_period("M") <= pd.Timestamp(inicio).to_period("M")
                 and datos["date"].max().to_period("M") >= pd.Timestamp(fin).to_period("M"))
    else:
        datos, cubre = pd.DataFrame(), False
    descargadas = 0
    if not cubre:
        if downloader is None:
            import yfinance as yf
            downloader = lambda ticker: yf.download(
                ticker, start=inicio,
                end=str((pd.Timestamp(fin) + pd.Timedelta(days=1)).date()),
                auto_adjust=True, progress=False, actions=False, threads=False,
            )
        piezas = []
        for symbol in BENCHMARKS:
            bruto = downloader(symbol)
            if bruto is None or bruto.empty:
                continue
            if getattr(bruto.columns, "nlevels", 1) > 1:
                bruto.columns = bruto.columns.get_level_values(0)
            mensual = bruto["Close"].astype(float).resample("ME").last().dropna()
            descargadas += len(mensual)
            piezas.append(pd.DataFrame({"date": mensual.index, "symbol": symbol, "value": mensual.values}))
        datos = pd.concat(piezas, ignore_index=True) if piezas else pd.DataFrame(columns=["date", "symbol", "value"])
        datos.to_csv(cache, index=False)
    series = {
        symbol: grupo.set_index("date")["value"].sort_index()
        for symbol, grupo in datos.groupby("symbol")
    }
    if "SPY" in series and "IEF" in series:
        retornos = pd.concat([series["SPY"].pct_change(), series["IEF"].pct_change()], axis=1).dropna()
        series["60_40"] = (1 + retornos.mul([0.6, 0.4]).sum(axis=1)).cumprod() * 100
    return series, {"filas_descargadas": descargadas, "cache_hit": cubre}


def normalizar_fecha_fin(valor):
    texto = str(valor)
    return str(pd.Period(texto, freq="M").end_time.date()) if len(texto) == 7 else texto


def metricas_periodo(serie, benchmark, inicio=None, fin=None):
    tramo = serie.loc[inicio:fin] if inicio or fin else serie
    bench = benchmark.loc[inicio:fin] if benchmark is not None and (inicio or fin) else benchmark
    return calcular_metricas(tramo, bench)


def ejecutar(nav, universo, benchmarks):
    series = {
        isin: serie_mensual(grupo)
        for isin, grupo in nav.groupby("isin")
        if len(grupo) >= 13
    }
    filas = []
    for _, fondo in universo.iterrows():
        isin = fondo["isin"]
        if isin not in series:
            continue
        benchmark = benchmarks.get(fondo["benchmark"])
        base = {**fondo.to_dict(), **calcular_metricas(series[isin], benchmark)}
        for periodo, inicio, fin in (
            ("TRAIN", None, TRAIN_END), ("TEST", TEST_START, None),
        ):
            m = metricas_periodo(series[isin], benchmark, inicio, fin)
            for clave in ("cagr", "max_drawdown", "sharpe", "cagr_difference"):
                base[f"{periodo.lower()}_{clave}"] = m.get(clave)
        filas.append(base)
    metricas = pd.DataFrame(filas)
    if not metricas.empty:
        metricas["train_cagr_rank"] = metricas["train_cagr"].rank(ascending=False, method="min")
        metricas["test_cagr_rank"] = metricas["test_cagr"].rank(ascending=False, method="min")
        metricas["train_test_rank_change"] = metricas["test_cagr_rank"] - metricas["train_cagr_rank"]
    persistencia = analizar_persistencia(series, benchmarks, universo)
    estrategias = pd.concat([
        estrategias_simples(series, benchmarks, universo, "annual"),
        estrategias_simples(series, benchmarks, universo, "semiannual"),
    ], ignore_index=True)
    if not estrategias.empty:
        fechas = pd.to_datetime(estrategias["rebalance_date"])
        estrategias["sample"] = np.where(fechas < TEST_START, "TRAIN", "TEST")
    return metricas, persistencia, estrategias, series


def resumir_categorias(metricas):
    columnas = ["cagr", "annualized_volatility", "max_drawdown", "sharpe", "sortino",
                "calmar", "cagr_difference", "annual_hit_rate", "rolling_outperformance_frequency"]
    disponibles = [c for c in columnas if c in metricas]
    resumen = metricas.groupby("category")[disponibles].agg(["count", "median", "mean"])
    resumen.columns = [f"{metrica}_{estadistico}" for metrica, estadistico in resumen.columns]
    return resumen.reset_index()


def resumen_persistencia(persistencia):
    if persistencia.empty:
        return pd.DataFrame()
    return persistencia.groupby(["method", "group", "forward_months"]).agg(
        observations=("forward_excess", "count"),
        mean_forward_excess=("forward_excess", "mean"),
        beat_benchmark_pct=("forward_excess", lambda x: (x > 0).mean()),
    ).reset_index()


def resumen_estrategias(estrategias):
    if estrategias.empty:
        return pd.DataFrame()
    return estrategias.groupby(["strategy", "frequency", "sample"]).agg(
        rebalances=("category_excess_12m", "count"),
        mean_return_12m=("fund_return_12m", "mean"),
        mean_excess_12m=("category_excess_12m", "mean"),
        beat_benchmark_pct=("category_excess_12m", lambda x: (x > 0).mean()),
    ).reset_index()


def auditar_calidad(nav, universo):
    filas = []
    for _, fondo in universo.iterrows():
        datos = nav[nav["isin"] == fondo["isin"]].sort_values("date")
        if datos.empty:
            filas.append({"isin": fondo["isin"], "fund_name": fondo["fund_name"],
                          "observations": 0, "quality_warning": "SIN DATOS CNMV"})
            continue
        periodos = pd.to_datetime(datos["date"]).dt.to_period("M")
        esperadas = len(pd.period_range(periodos.min(), periodos.max(), freq="M"))
        saltos = periodos.sort_values().astype(int).diff().dropna()
        filas.append({
            "isin": fondo["isin"], "fund_name": fondo["fund_name"],
            "first_available_date": datos["date"].min(), "last_available_date": datos["date"].max(),
            "observations": len(datos), "expected_months_between_endpoints": esperadas,
            "missing_months_between_endpoints": esperadas - len(periodos.unique()),
            "max_gap_months": int(saltos.max()) if len(saltos) else 0,
            "quality_warning": "" if esperadas == len(periodos.unique()) else "HUECOS MENSUALES",
        })
    return pd.DataFrame(filas)


def conclusion(metricas, persistencia_resumen, estrategias_resumen):
    test = estrategias_resumen[estrategias_resumen["sample"] == "TEST"] if not estrategias_resumen.empty else pd.DataFrame()
    top = persistencia_resumen[(persistencia_resumen["group"] == "TOP") &
                               (persistencia_resumen["forward_months"] == 12)] if not persistencia_resumen.empty else pd.DataFrame()
    robusta = (not test.empty and test["rebalances"].max() >= 4 and
               test["mean_excess_12m"].max() > 0.01 and test["beat_benchmark_pct"].max() > 0.55 and
               not top.empty and top["beat_benchmark_pct"].max() > 0.55)
    return (
        "Existe evidencia preliminar que justificaría una Fase 2, pero no una estrategia productiva."
        if robusta else
        "No existe evidencia suficientemente robusta para crear FUND_CANDIDATE con esta muestra."
    )


def generar_informe(universo, metricas, persistencia_r, estrategias_r, estadisticas):
    lineas = ["FUND RESEARCH - PHASE 1", "=" * 84,
              "Fuente principal: CNMV FONDREGISTRO + FONDMENS; benchmarks: Yahoo Finance (proxies ETF).",
              f"Fondos definidos: {len(universo)} | Fondos con >=13 observaciones: {len(metricas)}",
              f"Descargas benchmark: {estadisticas.get('filas_descargadas', 0)} filas nuevas.", "",
              "SESGOS Y LIMITACIONES", "-" * 84,
              "Este experimento presenta survivorship bias porque el universo se construye a partir de fondos actualmente existentes.",
              "No se han reconstruido fondos desaparecidos. No hay interpolación de NAV ni datos anteriores al inicio real.",
              "Los NAV ya incorporan gastos internos; no se descuentan de nuevo comisiones de gestión.",
              "La fiscalidad no se modela. Los traspasos elegibles pueden diferir la tributación en España, sujeto a normativa.", "",
              "MÉTRICAS INDIVIDUALES", "-" * 84]
    for _, f in metricas.sort_values("cagr", ascending=False).iterrows():
        lineas.append(f"{f['fund_name'][:34]:<34} | {f['category']:<15} | CAGR {f['cagr']:+.2%} | DD {f['max_drawdown']:+.2%} | Sharpe {f['sharpe']:.2f} | vs {f['benchmark']} {f.get('cagr_difference', np.nan):+.2%}")
    lineas.extend(["", "PERSISTENCIA TOP - FUTURO 12 MESES", "-" * 84])
    top = persistencia_r[(persistencia_r["group"] == "TOP") & (persistencia_r["forward_months"] == 12)] if not persistencia_r.empty else pd.DataFrame()
    for _, f in top.iterrows():
        lineas.append(f"{f['method']:<24} | n={int(f['observations']):>3} | exceso {f['mean_forward_excess']:+.2%} | bate benchmark {f['beat_benchmark_pct']:.1%}")
    lineas.extend(["", "ESTRATEGIAS SIMPLES - TRAIN/TEST", "-" * 84])
    for _, f in estrategias_r.iterrows():
        lineas.append(f"{f['strategy']:<24} | {f['frequency']:<10} | {f['sample']:<5} | n={int(f['rebalances']):>2} | exceso {f['mean_excess_12m']:+.2%} | bate {f['beat_benchmark_pct']:.1%}")
    lineas.extend(["", "ACTIVE FUNDS VS SIMPLE ETFs", "-" * 84,
                   "La comparación usa la ventana común de cada fondo y su proxy de categoría; SPY y 60/40 son referencias generales.",
                   "No se comparan fondos de renta fija indiscriminadamente contra SPY.", "", "CONCLUSIÓN", "-" * 84,
                   conclusion(metricas, persistencia_r, estrategias_r),
                   "No se ha creado ninguna estrategia ni cartera paper."])
    return "\n".join(lineas)


def ejecutar_research(inicio="2016-01", fin=None, refresh=False, manual_csv=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    universo = pd.DataFrame(FUNDS_UNIVERSE)
    universo["currency"] = "EUR"
    universo["inception_date"] = pd.NA
    universo["ongoing_charges"] = pd.NA
    universo["management_fee"] = pd.NA
    universo["depositary_fee"] = pd.NA
    universo.to_csv(CACHE_DIR / "fund_universe.csv", index=False)
    nav, metadata = obtener_nav_cnmv(universo["isin"].tolist(), inicio, fin, refresh)
    if manual_csv:
        nav = pd.concat([nav, importar_csv_manual(manual_csv)], ignore_index=True)
        nav = nav.sort_values(["isin", "date"]).drop_duplicates(["isin", "date"], keep="last")
    nav.to_csv(CACHE_DIR / "fund_nav_monthly.csv", index=False)
    calidad = auditar_calidad(nav, universo)
    calidad.to_csv(CACHE_DIR / "fund_data_quality.csv", index=False)
    if not metadata.empty:
        metadata.to_csv(CACHE_DIR / "cnmv_metadata_latest.csv", index=False)
    benchmarks, stats = construir_benchmarks(
        f"{inicio}-01",
        normalizar_fecha_fin(fin or str(date.today())),
        refresh=refresh
    )
    metricas, persistencia, estrategias, _ = ejecutar(nav, universo, benchmarks)
    categorias = resumir_categorias(metricas)
    persistencia_r = resumen_persistencia(persistencia)
    estrategias_r = resumen_estrategias(estrategias)
    metricas.to_csv(CACHE_DIR / "fund_metrics.csv", index=False)
    metricas[[c for c in metricas.columns if c.startswith(("fund_", "isin", "category", "benchmark", "train_", "test_"))]].to_csv(
        CACHE_DIR / "fund_train_test.csv", index=False
    )
    categorias.to_csv(CACHE_DIR / "fund_metrics_by_category.csv", index=False)
    persistencia.to_csv(CACHE_DIR / "fund_persistence.csv", index=False)
    estrategias.to_csv(CACHE_DIR / "fund_strategy_results.csv", index=False)
    persistencia_r.to_csv(CACHE_DIR / "fund_persistence_summary.csv", index=False)
    estrategias_r.to_csv(CACHE_DIR / "fund_strategy_summary.csv", index=False)
    informe = generar_informe(universo, metricas, persistencia_r, estrategias_r, stats)
    (CACHE_DIR / "fund_research_report.txt").write_text(informe, encoding="utf-8")
    return informe


def main():
    parser = argparse.ArgumentParser(description="FUND RESEARCH - PHASE 1")
    parser.add_argument("--start", default="2016-01")
    parser.add_argument("--end")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--manual-csv")
    args = parser.parse_args()
    print(ejecutar_research(args.start, args.end, args.refresh, args.manual_csv))


if __name__ == "__main__":
    main()
