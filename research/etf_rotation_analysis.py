"""Fase 2 ETF: rotación entre clases de activos y métricas de riesgo.

Módulo puramente exploratorio. No define ETF V1 ni se conecta al radar, paper
tracking o carteras productivas. Todas las decisiones usan el cierre de la fecha
de señal y se ejecutan en la apertura de la sesión siguiente.
"""

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_factor_analysis import (
    CACHE_DIR,
    calcular_features_precios,
    obtener_precios,
)


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "research_etf"
INITIAL_CAPITAL = 10_000.0
TRANSACTION_COST = 0.0005


@dataclass(frozen=True)
class RepresentativeETF:
    symbol: str
    group: str
    reason: str


REPRESENTATIVES = (
    RepresentativeETF("SPY", "US Equity", "S&P 500 y benchmark principal"),
    RepresentativeETF("QQQ", "US Equity", "large-cap growth/tecnología"),
    RepresentativeETF("IWM", "US Equity", "small caps USA"),
    RepresentativeETF("QUAL", "Factors", "factor calidad"),
    RepresentativeETF("MTUM", "Factors", "factor momentum"),
    RepresentativeETF("USMV", "Factors", "mínima volatilidad"),
    RepresentativeETF("VTV", "Factors", "factor value"),
    RepresentativeETF("VEA", "International", "desarrollados ex-USA"),
    RepresentativeETF("VWO", "International", "emergentes"),
    RepresentativeETF("IEF", "Treasuries", "Treasury intermedio"),
    RepresentativeETF("TLT", "Treasuries", "Treasury largo"),
    RepresentativeETF("SHY", "Treasuries", "Treasury corto/cash proxy"),
    RepresentativeETF("LQD", "Credit", "crédito investment grade"),
    RepresentativeETF("HYG", "Credit", "high yield"),
    RepresentativeETF("GLD", "Gold / Commodities", "oro, sin duplicar IAU"),
    RepresentativeETF("DBC", "Gold / Commodities", "commodities diversificadas"),
    RepresentativeETF("VNQ", "Real Estate", "REIT USA"),
)

GROUP_BY_SYMBOL = {item.symbol: item.group for item in REPRESENTATIVES}
DEFENSIVE = {"GLD", "IEF", "TLT", "SHY", "LQD"}
STRATEGIES = (
    "A_momentum60_top1",
    "B_momentum120_top1",
    "C_momentum60_120_top1",
    "D_rs60_top1",
    "E_rs120_top1",
    "F_trend_rs_top1",
    "G_diversified_top2",
    "H_regime_top1",
)


def fechas_rebalanceo(index, frequency):
    """Última sesión de cada semana o mes; la orden se ejecuta al día siguiente."""
    fechas = pd.DatetimeIndex(index).sort_values().unique()
    if len(fechas) < 2:
        return []
    serie = pd.Series(fechas, index=fechas)
    if frequency == "weekly":
        claves = [f"{d.isocalendar().year}-{d.isocalendar().week}" for d in fechas]
    elif frequency == "monthly":
        claves = fechas.to_period("M")
    else:
        raise ValueError("frequency debe ser weekly o monthly")
    ultimas = serie.groupby(claves).last().tolist()
    return [fecha for fecha in ultimas if fecha != fechas[-1]]


def construir_panel_features(historicos):
    spy_close = historicos["SPY"]["close"]
    panel = {}
    for symbol, datos in historicos.items():
        if not datos.empty:
            panel[symbol] = calcular_features_precios(datos, spy_close)
    return panel


def ranking_fecha(panel, signal_date):
    filas = []
    for symbol, datos in panel.items():
        if signal_date not in datos.index:
            continue
        fila = datos.loc[signal_date]
        if pd.isna(fila.get("momentum120")):
            continue
        filas.append({
            "symbol": symbol,
            "group": GROUP_BY_SYMBOL[symbol],
            "momentum20": fila["momentum20"],
            "momentum60": fila["momentum60"],
            "momentum120": fila["momentum120"],
            "rs20": fila["rs20"],
            "rs60": fila["rs60"],
            "rs120": fila["rs120"],
            "price_gt_sma200": bool(fila["price_gt_sma200"]),
            "sma50_gt_sma200": bool(fila["sma50_gt_sma200"]),
        })
    ranking = pd.DataFrame(filas)
    if ranking.empty:
        return ranking
    ranking["momentum60_rank"] = ranking["momentum60"].rank(pct=True)
    ranking["momentum120_rank"] = ranking["momentum120"].rank(pct=True)
    ranking["rs60_rank"] = ranking["rs60"].rank(pct=True)
    ranking["rs120_rank"] = ranking["rs120"].rank(pct=True)
    ranking["momentum_combo"] = (
        ranking["momentum60_rank"] + ranking["momentum120_rank"]
    ) / 2
    ranking["trend_rs"] = (
        ranking["price_gt_sma200"].astype(int)
        + ranking["sma50_gt_sma200"].astype(int)
        + ranking["rs60_rank"]
    )
    return ranking


def seleccionar_etfs(ranking, strategy, cash_filter=False):
    if ranking.empty:
        return []
    candidatos = ranking.copy()
    if strategy == "H_regime_top1":
        spy = candidatos[candidatos["symbol"] == "SPY"]
        risk_on = (
            not spy.empty and bool(spy.iloc[0]["price_gt_sma200"])
            and bool(spy.iloc[0]["sma50_gt_sma200"])
        )
        if not risk_on:
            candidatos = candidatos[candidatos["symbol"].isin(DEFENSIVE)]

    columna = {
        "A_momentum60_top1": "momentum60",
        "B_momentum120_top1": "momentum120",
        "C_momentum60_120_top1": "momentum_combo",
        "D_rs60_top1": "rs60",
        "E_rs120_top1": "rs120",
        "F_trend_rs_top1": "trend_rs",
        "G_diversified_top2": "momentum_combo",
        "H_regime_top1": "momentum_combo",
    }[strategy]
    ordenados = candidatos.sort_values([columna, "symbol"], ascending=[False, True])
    seleccion = []
    grupos = set()
    limite = 2 if strategy == "G_diversified_top2" else 1
    for _, fila in ordenados.iterrows():
        if strategy == "G_diversified_top2" and fila["group"] in grupos:
            continue
        seleccion.append(fila)
        grupos.add(fila["group"])
        if len(seleccion) == limite:
            break

    if cash_filter:
        shy = ranking[ranking["symbol"] == "SHY"]
        shy_momentum = shy.iloc[0]["momentum60"] if not shy.empty else 0.0
        seleccion = [
            fila for fila in seleccion
            if fila["symbol"] != "SHY"
            and fila["momentum60"] > 0
            and bool(fila["price_gt_sma200"])
            and fila["momentum60"] > shy_momentum
        ]
    return [fila["symbol"] for fila in seleccion]


def pesos_seleccion(panel, signal_date, strategy, cash_filter):
    seleccion = seleccionar_etfs(
        ranking_fecha(panel, signal_date), strategy, cash_filter
    )
    if not seleccion:
        return {}
    peso = 1 / len(seleccion)
    return {symbol: peso for symbol in seleccion}


def simular_cartera(
    historicos,
    signal_dates,
    selector,
    initial_capital=INITIAL_CAPITAL,
    cost_rate=TRANSACTION_COST,
):
    """Simula posiciones long-only, sin leverage, con ejecución next-open."""
    calendario = historicos["SPY"].index.sort_values()
    ejecuciones = {}
    posiciones_fecha = {fecha: i for i, fecha in enumerate(calendario)}
    for signal_date in signal_dates:
        indice = posiciones_fecha.get(signal_date)
        if indice is not None and indice + 1 < len(calendario):
            ejecuciones[calendario[indice + 1]] = signal_date

    cash = float(initial_capital)
    shares = {}
    total_costs = 0.0
    total_turnover = 0.0
    rebalances = 0
    registros = []

    for fecha in calendario:
        day_cost = 0.0
        day_turnover = 0.0
        did_rebalance = False
        if fecha in ejecuciones:
            signal_date = ejecuciones[fecha]
            weights = selector(signal_date)
            precios_open = {
                symbol: float(datos.at[fecha, "open"])
                for symbol, datos in historicos.items()
                if fecha in datos.index and pd.notna(datos.at[fecha, "open"])
            }
            valor_actual = {
                symbol: cantidad * precios_open.get(symbol, 0.0)
                for symbol, cantidad in shares.items()
            }
            equity_open = cash + sum(valor_actual.values())
            weights = {
                symbol: weight for symbol, weight in weights.items()
                if symbol in precios_open and weight > 0
            }
            suma_weights = sum(weights.values())
            if suma_weights > 0:
                weights = {symbol: weight / suma_weights for symbol, weight in weights.items()}

            target_total = equity_open
            for _ in range(4):
                targets = {symbol: target_total * weight for symbol, weight in weights.items()}
                symbols = set(valor_actual) | set(targets)
                traded = sum(abs(targets.get(s, 0.0) - valor_actual.get(s, 0.0)) for s in symbols)
                coste = traded * cost_rate
                target_total = max(equity_open - coste, 0.0) if weights else 0.0
            targets = {symbol: target_total * weight for symbol, weight in weights.items()}
            symbols = set(valor_actual) | set(targets)
            traded = sum(abs(targets.get(s, 0.0) - valor_actual.get(s, 0.0)) for s in symbols)
            coste = traded * cost_rate
            shares = {
                symbol: target / precios_open[symbol]
                for symbol, target in targets.items() if target > 0
            }
            cash = max(equity_open - sum(targets.values()) - coste, 0.0)
            total_costs += coste
            day_cost = coste
            day_turnover = traded / equity_open if equity_open > 0 else 0.0
            did_rebalance = True
            total_turnover += day_turnover
            rebalances += 1

        valor_posiciones = sum(
            cantidad * float(historicos[symbol].at[fecha, "close"])
            for symbol, cantidad in shares.items() if fecha in historicos[symbol].index
        )
        equity = cash + valor_posiciones
        registros.append({
            "date": fecha, "equity": equity, "cash": cash,
            "invested": valor_posiciones, "is_invested": bool(shares),
            "holdings": "+".join(sorted(shares)) if shares else "CASH",
            "transaction_cost": day_cost, "turnover": day_turnover,
            "did_rebalance": did_rebalance,
        })

    curva = pd.DataFrame(registros).set_index("date")
    curva.attrs.update({
        "total_costs": total_costs,
        "turnover": total_turnover,
        "rebalances": rebalances,
    })
    return curva


def calcular_metricas(curva, initial_capital=None):
    if curva.empty:
        return {}
    equity = curva["equity"].dropna()
    if len(equity) < 2:
        return {}
    capital = float(initial_capital if initial_capital is not None else equity.iloc[0])
    retorno = equity.iloc[-1] / capital - 1
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 252)
    cagr = (equity.iloc[-1] / capital) ** (1 / years) - 1
    daily = equity.pct_change().dropna()
    volatility = daily.std(ddof=1) * np.sqrt(252)
    sharpe = daily.mean() / daily.std(ddof=1) * np.sqrt(252) if daily.std(ddof=1) > 0 else 0.0
    downside = daily[daily < 0].std(ddof=1)
    sortino = daily.mean() / downside * np.sqrt(252) if pd.notna(downside) and downside > 0 else 0.0
    drawdown = equity / equity.cummax() - 1
    max_drawdown = drawdown.min()
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else 0.0
    annual = equity.resample("YE").last().pct_change()
    if len(annual):
        first_year = equity.index[0].year
        first_base = capital
        first_end = equity[equity.index.year == first_year].iloc[-1]
        annual.iloc[0] = first_end / first_base - 1
    return {
        "cumulative_return": retorno * 100,
        "cagr": cagr * 100,
        "annualized_volatility": volatility * 100,
        "max_drawdown": max_drawdown * 100,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "invested_pct": curva["is_invested"].mean() * 100,
        "cash_pct": (~curva["is_invested"]).mean() * 100,
        "rebalances": int(curva["did_rebalance"].sum()) if "did_rebalance" in curva else curva.attrs.get("rebalances", 0),
        "turnover": (curva["turnover"].sum() * 100) if "turnover" in curva else curva.attrs.get("turnover", 0.0) * 100,
        "total_costs": curva["transaction_cost"].sum() if "transaction_cost" in curva else curva.attrs.get("total_costs", 0.0),
        "worst_year": annual.min() * 100 if len(annual) else np.nan,
        "best_year": annual.max() * 100 if len(annual) else np.nan,
        "balance_score": cagr * 100 - abs(max_drawdown * 100) / 2,
    }


PERIODS = {
    "2016-2019": ("2016-01-01", "2019-12-31"),
    "2020-2022": ("2020-01-01", "2022-12-31"),
    "2023-2026": ("2023-01-01", "2026-12-31"),
    "TRAIN_2016-2021": ("2016-01-01", "2021-12-31"),
    "TEST_2022-2026": ("2022-01-01", "2026-12-31"),
    "2016-2020": ("2016-01-01", "2020-12-31"),
    "2021-2026": ("2021-01-01", "2026-12-31"),
}


def metricas_periodos(curva):
    filas = []
    for nombre, (start, end) in PERIODS.items():
        tramo = curva.loc[start:end].copy()
        if len(tramo) < 2:
            continue
        tramo.attrs.update(curva.attrs)
        metricas = calcular_metricas(tramo, initial_capital=tramo["equity"].iloc[0])
        filas.append({"period": nombre, **metricas})
    return filas


def _curva_buy_hold(historicos, weights, start):
    calendario = historicos["SPY"].loc[start:].index
    signal = [calendario[0]] if len(calendario) > 1 else []
    return simular_cartera(historicos, signal, lambda _: weights)


def ejecutar_analisis(historicos, panel, start):
    calendario = historicos["SPY"].loc[start:].index
    historicos = {s: df.loc[df.index >= calendario[0]] for s, df in historicos.items()}
    resultados, periodos, curvas = [], [], []

    benchmarks = {
        "SPY_BUY_HOLD": _curva_buy_hold(historicos, {"SPY": 1.0}, calendario[0]),
        "SHY_BUY_HOLD": _curva_buy_hold(historicos, {"SHY": 1.0}, calendario[0]),
    }
    mensual = [calendario[0], *fechas_rebalanceo(calendario, "monthly")]
    benchmarks["BENCHMARK_60_40"] = simular_cartera(
        historicos, mensual, lambda _: {"SPY": 0.6, "IEF": 0.4}
    )

    for nombre, curva in benchmarks.items():
        resultados.append({"strategy": nombre, "frequency": "benchmark", "cash_filter": False, **calcular_metricas(curva, INITIAL_CAPITAL)})
        for fila in metricas_periodos(curva):
            periodos.append({"strategy": nombre, "frequency": "benchmark", "cash_filter": False, **fila})
        copia = curva.reset_index()
        copia.insert(0, "strategy_id", nombre)
        curvas.append(copia)

    for frequency in ("weekly", "monthly"):
        signals = [calendario[0], *fechas_rebalanceo(calendario, frequency)]
        for strategy in STRATEGIES:
            for cash_filter in (False, True):
                strategy_id = f"{strategy}|{frequency}|cash={int(cash_filter)}"
                curva = simular_cartera(
                    historicos, signals,
                    lambda fecha, s=strategy, c=cash_filter: pesos_seleccion(panel, fecha, s, c),
                )
                resultados.append({
                    "strategy": strategy, "strategy_id": strategy_id,
                    "frequency": frequency, "cash_filter": cash_filter,
                    **calcular_metricas(curva, INITIAL_CAPITAL),
                })
                for fila in metricas_periodos(curva):
                    periodos.append({
                        "strategy": strategy, "strategy_id": strategy_id,
                        "frequency": frequency, "cash_filter": cash_filter, **fila,
                    })
                copia = curva.reset_index()
                copia.insert(0, "strategy_id", strategy_id)
                curvas.append(copia)
    return pd.DataFrame(resultados), pd.DataFrame(periodos), pd.concat(curvas, ignore_index=True)


def imprimir_rankings(resultados, periodos):
    print("\nETF ROTATION RESEARCH - FASE 2")
    print("=" * 84)
    for benchmark in ("SPY_BUY_HOLD", "BENCHMARK_60_40", "SHY_BUY_HOLD"):
        fila = resultados[resultados["strategy"] == benchmark].iloc[0]
        print(f"{benchmark:<20} CAGR {fila['cagr']:+.2f}% | MaxDD {fila['max_drawdown']:+.2f}% | Sharpe {fila['sharpe']:.2f}")
    rotacion = resultados[resultados["frequency"] != "benchmark"]
    for titulo, columna, ascendente in (
        ("MAYOR CAGR", "cagr", False), ("MEJOR SHARPE", "sharpe", False),
        ("MENOR MAXDD", "max_drawdown", False), ("MEJOR CALMAR", "calmar", False),
        ("EQUILIBRIO RETORNO/DD", "balance_score", False),
    ):
        print(f"\n{titulo}")
        for _, fila in rotacion.sort_values(columna, ascending=ascendente).head(5).iterrows():
            print(
                f"  {fila['strategy_id']:<48} CAGR {fila['cagr']:+.2f}% | "
                f"DD {fila['max_drawdown']:+.2f}% | Sharpe {fila['sharpe']:.2f}"
            )
    print("\nTRAIN / TEST disponibles en etf_rotation_periods.csv")


def parse_args():
    parser = argparse.ArgumentParser(description="Fase 2 de investigación ETF")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    descarga_inicio = start - timedelta(days=400)
    historicos = {}
    for indice, item in enumerate(REPRESENTATIVES, 1):
        print(f"Precios rotación {indice}/{len(REPRESENTATIVES)}: {item.symbol}")
        historicos[item.symbol] = obtener_precios(
            item.symbol, descarga_inicio, end,
            refresh=args.refresh_cache, cache_dir=CACHE_DIR,
        )
    panel = construir_panel_features(historicos)
    resultados, periodos, curvas = ejecutar_analisis(historicos, panel, start)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    resultados.to_csv(OUTPUT_DIR / "etf_rotation_results.csv", index=False)
    periodos.to_csv(OUTPUT_DIR / "etf_rotation_periods.csv", index=False)
    curvas.to_csv(OUTPUT_DIR / "etf_rotation_equity.csv", index=False)
    imprimir_rankings(resultados, periodos)


if __name__ == "__main__":
    main()
