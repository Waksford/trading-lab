from collections import defaultdict
from datetime import timedelta
from statistics import mean, median

from research.stop_takeprofit_analysis import (
    CAPITAL,
    COST_PCT,
    HOLDING,
    MAX_POSITIONS,
    TOP,
    preparar_datos,
    simular_cartera_salidas,
)


VARIANTES = (
    ("MOMENTUM_BASE", "momentum", None, None),
    ("MOMENTUM_TP25", "momentum", None, 25),
    ("REVERSAL_BASE", "reversal", None, None),
    ("REVERSAL_TP10", "reversal", None, 10),
    ("REVERSAL_STOP12_TP10", "reversal", -12, 10),
)

COMPARACIONES = (
    ("MOMENTUM_BASE", "MOMENTUM_TP25"),
    ("REVERSAL_BASE", "REVERSAL_TP10"),
    ("REVERSAL_BASE", "REVERSAL_STOP12_TP10"),
)


def inicio_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())


def agrupar_trades_por_semana(trades):
    grupos = defaultdict(list)
    for trade in trades:
        grupos[inicio_semana(trade["signal_date"])].append(trade)
    return grupos


def resumir_trades(trades):
    retornos = [trade["return_pct"] for trade in trades]
    pnl = [trade["pnl"] for trade in trades]
    wins = sum(valor > 0 for valor in retornos)
    return {
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate_pct": wins / len(trades) * 100 if trades else None,
        "avg_trade_pct": mean(retornos) if retornos else None,
        "median_trade_pct": median(retornos) if retornos else None,
        "total_pnl": sum(pnl),
        "best_trade_pct": max(retornos) if retornos else None,
        "worst_trade_pct": min(retornos) if retornos else None,
        "exit_stop_count": sum(t["exit_reason"] == "STOP" for t in trades),
        "exit_tp_count": sum(t["exit_reason"] == "TAKE_PROFIT" for t in trades),
        "exit_time_count": sum(t["exit_reason"] == "TIME" for t in trades),
    }


def resumir_semanas(trades):
    grupos = agrupar_trades_por_semana(trades)
    total_pnl = sum(trade["pnl"] for trade in trades)
    filas = []
    for week_start, grupo in sorted(grupos.items()):
        fila = resumir_trades(grupo)
        fila.update(
            {
                "week_start": week_start,
                "week_end": week_start + timedelta(days=4),
                "contribution_to_total_pnl_pct": (
                    fila["total_pnl"] / total_pnl * 100
                    if total_pnl > 0 else None
                ),
            }
        )
        filas.append(fila)
    return filas


def punto_division_mitades(trades):
    fechas = sorted({trade["signal_date"] for trade in trades})
    if not fechas:
        return None
    return fechas[(len(fechas) + 1) // 2 - 1]


def resumir_mitades(trades):
    corte = punto_division_mitades(trades)
    if corte is None:
        return []
    primera = [trade for trade in trades if trade["signal_date"] <= corte]
    segunda = [trade for trade in trades if trade["signal_date"] > corte]
    filas = []
    for nombre, grupo in (("PRIMERA", primera), ("SEGUNDA", segunda)):
        fila = resumir_trades(grupo)
        fila["half"] = nombre
        filas.append(fila)
    return filas


def calcular_concentracion(trades, semanas=None):
    total_pnl = sum(trade["pnl"] for trade in trades)
    if total_pnl <= 0:
        return {
            "best_week_pct": None,
            "top_2_weeks_pct": None,
            "top_3_trades_pct": None,
            "top_5_trades_pct": None,
        }
    semanas = semanas if semanas is not None else resumir_semanas(trades)
    pnl_semanal = sorted((fila["total_pnl"] for fila in semanas), reverse=True)
    pnl_trades = sorted((trade["pnl"] for trade in trades), reverse=True)
    return {
        "best_week_pct": sum(pnl_semanal[:1]) / total_pnl * 100,
        "top_2_weeks_pct": sum(pnl_semanal[:2]) / total_pnl * 100,
        "top_3_trades_pct": sum(pnl_trades[:3]) / total_pnl * 100,
        "top_5_trades_pct": sum(pnl_trades[:5]) / total_pnl * 100,
    }


def calcular_consistencia(semanas):
    positivas = sum(fila["total_pnl"] > 0 for fila in semanas)
    negativas = sum(fila["total_pnl"] < 0 for fila in semanas)
    return {
        "numero_semanas_con_trades": len(semanas),
        "semanas_positivas": positivas,
        "semanas_negativas": negativas,
        "porcentaje_semanas_positivas": (
            positivas / len(semanas) * 100 if semanas else None
        ),
        "mediana_retorno_trade_por_semana": (
            median(fila["median_trade_pct"] for fila in semanas)
            if semanas else None
        ),
        "mediana_win_rate_semanal": (
            median(fila["win_rate_pct"] for fila in semanas)
            if semanas else None
        ),
    }


def analizar_variante(nombre, simulacion):
    trades = simulacion["trade_details"]
    semanas = resumir_semanas(trades)
    return {
        "name": nombre,
        "simulation": simulacion,
        "weeks": semanas,
        "halves": resumir_mitades(trades),
        "concentration": calcular_concentracion(trades, semanas),
        "consistency": calcular_consistencia(semanas),
    }


def comparar_variantes(base, variante):
    base_por_semana = {fila["week_start"]: fila for fila in base["weeks"]}
    variante_por_semana = {
        fila["week_start"]: fila for fila in variante["weeks"]
    }
    filas = []
    for semana in sorted(set(base_por_semana) | set(variante_por_semana)):
        fila_base = base_por_semana.get(semana, {"trades": 0, "total_pnl": 0})
        fila_variante = variante_por_semana.get(
            semana, {"trades": 0, "total_pnl": 0}
        )
        filas.append(
            {
                "week_start": semana,
                "week_end": semana + timedelta(days=4),
                "trades_base": fila_base["trades"],
                "pnl_base": fila_base["total_pnl"],
                "trades_variant": fila_variante["trades"],
                "pnl_variant": fila_variante["total_pnl"],
                "delta_pnl": fila_variante["total_pnl"] - fila_base["total_pnl"],
            }
        )
    return filas


def ejecutar_variantes(resultados, historicos):
    analisis = {}
    for nombre, strategy, stop, take_profit in VARIANTES:
        simulacion = simular_cartera_salidas(
            resultados[strategy],
            historicos,
            strategy,
            stop_pct=stop,
            take_profit_pct=take_profit,
            capital=CAPITAL,
            holding=HOLDING,
            top=TOP,
            max_positions=MAX_POSITIONS,
            cost_pct=COST_PCT,
            spy_bars=historicos.get("SPY", []),
        )
        analisis[nombre] = analizar_variante(nombre, simulacion)
    return analisis


def formato_pct(valor):
    return f"{valor:+.2f}%" if valor is not None else "N/A"


def imprimir_informe(analisis, cache):
    print("TEMPORAL STABILITY - RESEARCH / IN-SAMPLE")
    print("NO ES VALIDACION OUT-OF-SAMPLE")
    print("=" * 130)
    print("\n1. RESUMEN GENERAL")
    print("VARIANTE | TRADES | CAPITAL FINAL | RET | MAXDD | WEEKS | WEEKS+ | %WEEKS+")
    for nombre, dato in analisis.items():
        sim = dato["simulation"]
        consistencia = dato["consistency"]
        print(
            f"{nombre:<24} | {sim['trades']:>6} | ${sim['capital_final']:>12,.2f} | "
            f"{formato_pct(sim['return_pct']):>8} | {formato_pct(sim['max_drawdown_pct']):>8} | "
            f"{consistencia['numero_semanas_con_trades']:>5} | "
            f"{consistencia['semanas_positivas']:>6} | "
            f"{formato_pct(consistencia['porcentaje_semanas_positivas']):>8}"
        )

    print("\n2. RESULTADOS POR SEMANA")
    for nombre, dato in analisis.items():
        print(f"\n{nombre}")
        print("WEEK | TRADES | W/L | WIN | AVG | MEDIAN | PNL | BEST | WORST | S/TP/TIME | CONTRIB")
        for fila in dato["weeks"]:
            print(
                f"{fila['week_start']}..{fila['week_end']} | {fila['trades']:>6} | "
                f"{fila['wins']:>2}/{fila['losses']:<2} | {formato_pct(fila['win_rate_pct']):>8} | "
                f"{formato_pct(fila['avg_trade_pct']):>8} | {formato_pct(fila['median_trade_pct']):>8} | "
                f"${fila['total_pnl']:>+9.2f} | {formato_pct(fila['best_trade_pct']):>8} | "
                f"{formato_pct(fila['worst_trade_pct']):>8} | "
                f"{fila['exit_stop_count']}/{fila['exit_tp_count']}/{fila['exit_time_count']} | "
                f"{formato_pct(fila['contribution_to_total_pnl_pct'])}"
            )

    print("\n3. PRIMERA MITAD VS SEGUNDA MITAD")
    for nombre, dato in analisis.items():
        for fila in dato["halves"]:
            print(
                f"{nombre:<24} | {fila['half']:<7} | trades {fila['trades']:>3} | "
                f"win {formato_pct(fila['win_rate_pct'])} | avg {formato_pct(fila['avg_trade_pct'])} | "
                f"median {formato_pct(fila['median_trade_pct'])} | PNL ${fila['total_pnl']:+.2f}"
            )

    print("\n4. CONCENTRACION DEL PNL")
    print("VARIANTE | BEST WEEK | TOP2 WEEKS | TOP3 TRADES | TOP5 TRADES | MED WEEK RET | MED WEEK WIN")
    for nombre, dato in analisis.items():
        concentracion = dato["concentration"]
        consistencia = dato["consistency"]
        print(
            f"{nombre:<24} | {formato_pct(concentracion['best_week_pct']):>9} | "
            f"{formato_pct(concentracion['top_2_weeks_pct']):>10} | "
            f"{formato_pct(concentracion['top_3_trades_pct']):>11} | "
            f"{formato_pct(concentracion['top_5_trades_pct']):>11} | "
            f"{formato_pct(consistencia['mediana_retorno_trade_por_semana']):>12} | "
            f"{formato_pct(consistencia['mediana_win_rate_semanal']):>12}"
        )

    print("\n5. BASE VS VARIANTE")
    for base_nombre, variante_nombre in COMPARACIONES:
        print(f"\n{base_nombre} VS {variante_nombre}")
        print("WEEK | TRADES BASE | PNL BASE | TRADES VAR | PNL VAR | DELTA PNL")
        for fila in comparar_variantes(
            analisis[base_nombre], analisis[variante_nombre]
        ):
            print(
                f"{fila['week_start']}..{fila['week_end']} | {fila['trades_base']:>11} | "
                f"${fila['pnl_base']:>+9.2f} | {fila['trades_variant']:>10} | "
                f"${fila['pnl_variant']:>+9.2f} | ${fila['delta_pnl']:>+9.2f}"
            )

    print(
        f"\nCache hits: {cache['cache_hits']} | descargados: "
        f"{cache['symbols'] - cache['cache_hits']} | filas descargadas: "
        f"{cache['filas_descargadas']}"
    )
    print(
        "Las semanas atribuyen el P&L de cada trade a su signal_date; la cartera se ejecuta "
        "una sola vez de forma cronológica y no se reinicia cada lunes."
    )


def main():
    resultados, historicos, cache = preparar_datos(("momentum", "reversal"))
    analisis = ejecutar_variantes(resultados, historicos)
    imprimir_informe(analisis, cache)


if __name__ == "__main__":
    main()
