import argparse
from datetime import date
from statistics import mean, median

from research.historical_market_data import obtener_historicos
from research.portfolio_whatif import (
    cargar_scans_historicos,
    evaluar_candidatos_research,
    parsear_fecha,
    reconstruir_candidatos_research,
    simular_cartera,
)


HOLDING_DEFAULT = 5
TOP_DEFAULT = 5
MAX_POSITIONS_DEFAULT = 10
CAPITAL_DEFAULT = 10000.0
COST_PCT_DEFAULT = 0.10
STOPS = (3, 5, 8, 10, 12, 15)
NIVELES_PERDEDORAS = (3, 5, 8, 10, 15, 20)
TAKE_PROFITS = (5, 8, 10, 15, 20, 25, 30)


def percentil(valores, porcentaje):
    """Percentil lineal inclusivo (equivalente al método R-7)."""
    ordenados = sorted(float(valor) for valor in valores)
    if not ordenados:
        return None
    if len(ordenados) == 1:
        return ordenados[0]
    posicion = (len(ordenados) - 1) * porcentaje / 100
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    peso = posicion - inferior
    return ordenados[inferior] * (1 - peso) + ordenados[superior] * peso


def preparar_trades(trades):
    preparados = []
    sin_excursion = 0
    for trade in trades:
        if trade.get("mfe_pct") is None or trade.get("mae_pct") is None:
            sin_excursion += 1
            continue
        fila = dict(trade)
        fila["giveback_pct"] = float(fila["mfe_pct"]) - float(fila["return_pct"])
        preparados.append(fila)
    return preparados, sin_excursion


def dividir_resultados(trades):
    return (
        [trade for trade in trades if trade["return_pct"] > 0],
        [trade for trade in trades if trade["return_pct"] <= 0],
    )


def resumir_grupo(trades):
    if not trades:
        return {
            campo: None
            for campo in (
                "return_medio", "return_mediano", "mfe_medio", "mfe_mediano",
                "mfe_p25", "mfe_p75", "mae_medio", "mae_mediano",
                "mae_p25", "mae_p75", "giveback_mediano",
            )
        } | {"n": 0}
    retornos = [trade["return_pct"] for trade in trades]
    mfe = [trade["mfe_pct"] for trade in trades]
    mae = [trade["mae_pct"] for trade in trades]
    giveback = [trade["giveback_pct"] for trade in trades]
    return {
        "n": len(trades),
        "return_medio": mean(retornos),
        "return_mediano": median(retornos),
        "mfe_medio": mean(mfe),
        "mfe_mediano": median(mfe),
        "mfe_p25": percentil(mfe, 25),
        "mfe_p75": percentil(mfe, 75),
        "mae_medio": mean(mae),
        "mae_mediano": median(mae),
        "mae_p25": percentil(mae, 25),
        "mae_p75": percentil(mae, 75),
        "giveback_mediano": median(giveback),
    }


def porcentaje_umbral(trades, campo, umbral, operador):
    if not trades:
        return None
    cumple = sum(operador(float(trade[campo]), umbral) for trade in trades)
    return cumple / len(trades) * 100


def supervivencia_stops(ganadoras):
    return {
        stop: porcentaje_umbral(ganadoras, "mae_pct", -stop, lambda valor, limite: valor <= limite)
        for stop in STOPS
    }


def mfe_perdedoras(perdedoras):
    return {
        nivel: porcentaje_umbral(perdedoras, "mfe_pct", nivel, lambda valor, limite: valor >= limite)
        for nivel in NIVELES_PERDEDORAS
    }


def alcance_take_profit(trades):
    ganadoras, perdedoras = dividir_resultados(trades)
    return {
        nivel: {
            "todas": porcentaje_umbral(trades, "mfe_pct", nivel, lambda valor, limite: valor >= limite),
            "ganadoras": porcentaje_umbral(ganadoras, "mfe_pct", nivel, lambda valor, limite: valor >= limite),
            "perdedoras": porcentaje_umbral(perdedoras, "mfe_pct", nivel, lambda valor, limite: valor >= limite),
        }
        for nivel in TAKE_PROFITS
    }


def distribuir_mae(trades):
    conteos = {
        "MAE >= -3%": 0,
        "-5% < MAE < -3%": 0,
        "-8% < MAE <= -5%": 0,
        "-10% < MAE <= -8%": 0,
        "-15% < MAE <= -10%": 0,
        "MAE <= -15%": 0,
    }
    for trade in trades:
        mae = float(trade["mae_pct"])
        if mae >= -3:
            clave = "MAE >= -3%"
        elif mae > -5:
            clave = "-5% < MAE < -3%"
        elif mae > -8:
            clave = "-8% < MAE <= -5%"
        elif mae > -10:
            clave = "-10% < MAE <= -8%"
        elif mae > -15:
            clave = "-15% < MAE <= -10%"
        else:
            clave = "MAE <= -15%"
        conteos[clave] += 1
    return conteos


def analizar_trades(trades, strategy):
    preparados, sin_excursion = preparar_trades(trades)
    ganadoras, perdedoras = dividir_resultados(preparados)
    return {
        "strategy": strategy.upper(),
        "trades": preparados,
        "sin_excursion": sin_excursion,
        "ganadoras": ganadoras,
        "perdedoras": perdedoras,
        "resumen_todas": resumir_grupo(preparados),
        "resumen_ganadoras": resumir_grupo(ganadoras),
        "resumen_perdedoras": resumir_grupo(perdedoras),
        "stops_ganadoras": supervivencia_stops(ganadoras),
        "mfe_perdedoras": mfe_perdedoras(perdedoras),
        "take_profit": alcance_take_profit(preparados),
        "distribucion_mae": distribuir_mae(preparados),
    }


def preparar_escenarios(strategies, holding, top, max_positions, capital, cost_pct):
    scans = cargar_scans_historicos()
    candidatos = {
        strategy: reconstruir_candidatos_research(scans, strategy)
        for strategy in strategies
    }
    todos = [senal for filas in candidatos.values() for senal in filas]
    inicio = min(parsear_fecha(senal["market_date"]) for senal in todos)
    symbols = {senal["symbol"] for senal in todos} | {"SPY"}
    historicos, cache = obtener_historicos(symbols, inicio, date.today())
    analisis = []
    metadata = {}
    for strategy in strategies:
        resultados, cobertura = evaluar_candidatos_research(
            candidatos[strategy], historicos, holding
        )
        simulacion = simular_cartera(
            resultados,
            capital=capital,
            strategy=strategy,
            holding=holding,
            top=top,
            max_positions=max_positions,
            cost_pct=cost_pct,
            historicos=historicos,
            spy_bars=historicos.get("SPY", []),
        )
        analisis.append(analizar_trades(simulacion["trades"], strategy))
        metadata[strategy] = cobertura
    return analisis, metadata, cache


def formato(valor):
    return f"{valor:+.2f}%" if valor is not None else "N/A"


def imprimir_resumen_grupo(nombre, resumen):
    print(f"\n{nombre} (N={resumen['n']})")
    print(
        f"Return medio/mediano: {formato(resumen['return_medio'])} / {formato(resumen['return_mediano'])} | "
        f"MFE medio/mediano/P25/P75: {formato(resumen['mfe_medio'])} / {formato(resumen['mfe_mediano'])} / "
        f"{formato(resumen['mfe_p25'])} / {formato(resumen['mfe_p75'])}"
    )
    print(
        f"MAE medio/mediano/P25/P75: {formato(resumen['mae_medio'])} / {formato(resumen['mae_mediano'])} / "
        f"{formato(resumen['mae_p25'])} / {formato(resumen['mae_p75'])} | "
        f"Giveback mediano: {formato(resumen['giveback_mediano'])}"
    )


def imprimir_casos(titulo, trades, incluir_giveback=True):
    print(f"\n{titulo}")
    print("SYMBOL  RETURN     MFE       MAE       GIVEBACK" if incluir_giveback else "SYMBOL  RETURN     MFE       MAE")
    for trade in trades[:10]:
        linea = (
            f"{trade['symbol']:<7} {formato(trade['return_pct']):>9} "
            f"{formato(trade['mfe_pct']):>9} {formato(trade['mae_pct']):>9}"
        )
        if incluir_giveback:
            linea += f" {formato(trade['giveback_pct']):>10}"
        print(linea)


def imprimir_analisis(analisis, cobertura):
    print(f"\n{analisis['strategy']} - EXCURSIONES INTRATRADE")
    print("=" * 90)
    print(
        f"Trades seleccionados con OHLC: {len(analisis['trades'])} | "
        f"seleccionados sin OHLC suficiente: {analisis['sin_excursion']} | "
        f"señales sin resultado maduro: "
        f"{cobertura['senales_reconstruidas'] - cobertura['con_resultado_futuro']}"
    )
    imprimir_resumen_grupo("TODAS", analisis["resumen_todas"])
    imprimir_resumen_grupo("GANADORAS", analisis["resumen_ganadoras"])
    imprimir_resumen_grupo("PERDEDORAS", analisis["resumen_perdedoras"])

    print("\nSTOP | GANADORAS QUE HABRIAN TOCADO EL STOP")
    for stop, porcentaje in analisis["stops_ganadoras"].items():
        print(f"-{stop:>2}% | {formato(porcentaje)}")
    print("\nNIVEL | PERDEDORAS QUE LLEGARON A ESE BENEFICIO")
    for nivel, porcentaje in analisis["mfe_perdedoras"].items():
        print(f"+{nivel:>2}% | {formato(porcentaje)}")
    print("\nTAKE-PROFIT ALCANZADO (NO SIMULADO)")
    print("NIVEL | TODAS | GANADORAS | PERDEDORAS")
    for nivel, grupos in analisis["take_profit"].items():
        print(
            f"+{nivel:>2}% | {formato(grupos['todas']):>8} | "
            f"{formato(grupos['ganadoras']):>9} | {formato(grupos['perdedoras']):>10}"
        )
    print("\nDISTRIBUCION MAE")
    for intervalo, cantidad in analisis["distribucion_mae"].items():
        print(f"{intervalo:<23} | {cantidad}")

    trades = analisis["trades"]
    imprimir_casos("10 MEJORES RETORNOS", sorted(trades, key=lambda x: x["return_pct"], reverse=True))
    imprimir_casos("10 PEORES RETORNOS", sorted(trades, key=lambda x: x["return_pct"]), False)
    imprimir_casos(
        "GANADORAS QUE MAS SUFRIERON",
        sorted(analisis["ganadoras"], key=lambda x: x["mae_pct"]),
    )
    imprimir_casos(
        "PERDEDORAS QUE MAS LLEGARON A GANAR",
        sorted(analisis["perdedoras"], key=lambda x: x["mfe_pct"], reverse=True),
    )


def construir_comparacion(analisis):
    filas = []
    for dato in analisis:
        todas = dato["resumen_todas"]
        filas.append(
            {
                "strategy": dato["strategy"],
                "trades": todas["n"],
                "win_pct": len(dato["ganadoras"]) / todas["n"] * 100 if todas["n"] else None,
                "return_med": todas["return_mediano"],
                "mfe_med": todas["mfe_mediano"],
                "mae_med": todas["mae_mediano"],
                "giveback_med": todas["giveback_mediano"],
                "ganadoras_stop_5": dato["stops_ganadoras"][5],
                "ganadoras_stop_8": dato["stops_ganadoras"][8],
                "perdedoras_mfe_5": dato["mfe_perdedoras"][5],
                "perdedoras_mfe_10": dato["mfe_perdedoras"][10],
            }
        )
    return filas


def imprimir_comparacion(analisis):
    print("\nCOMPARACION MOMENTUM VS REVERSAL")
    print("=" * 115)
    print("ESTRATEGIA | TRADES | WIN | RET MED | MFE MED | MAE MED | GIVEBACK | WIN STOP-5/-8 | LOSS MFE+5/+10")
    for fila in construir_comparacion(analisis):
        print(
            f"{fila['strategy']:<10} | {fila['trades']:>6} | {formato(fila['win_pct']):>8} | "
            f"{formato(fila['return_med']):>8} | {formato(fila['mfe_med']):>8} | "
            f"{formato(fila['mae_med']):>8} | {formato(fila['giveback_med']):>8} | "
            f"{formato(fila['ganadoras_stop_5'])}/{formato(fila['ganadoras_stop_8'])} | "
            f"{formato(fila['perdedoras_mfe_5'])}/{formato(fila['perdedoras_mfe_10'])}"
        )


def obtener_argumentos():
    parser = argparse.ArgumentParser(description="Análisis MFE/MAE research/in-sample.")
    parser.add_argument("--strategy", choices=("momentum", "reversal"), default="momentum")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--holding", type=int, choices=(5, 20, 60), default=HOLDING_DEFAULT)
    parser.add_argument("--top", type=int, default=TOP_DEFAULT)
    parser.add_argument("--max-positions", type=int, default=MAX_POSITIONS_DEFAULT)
    parser.add_argument("--capital", type=float, default=CAPITAL_DEFAULT)
    parser.add_argument("--cost-pct", type=float, default=COST_PCT_DEFAULT)
    return parser.parse_args()


def main():
    args = obtener_argumentos()
    strategies = ("momentum", "reversal") if args.compare else (args.strategy,)
    analisis, metadata, cache = preparar_escenarios(
        strategies, args.holding, args.top, args.max_positions, args.capital, args.cost_pct
    )
    print("TRADE EXCURSION ANALYSIS - RESEARCH / IN-SAMPLE")
    print("NO ES VALIDACION OUT-OF-SAMPLE")
    for dato in analisis:
        imprimir_analisis(dato, metadata[dato["strategy"].lower()])
    if args.compare:
        imprimir_comparacion(analisis)
    print(
        f"\nCache hits: {cache['cache_hits']} | "
        f"symbols descargados: {cache['symbols'] - cache['cache_hits']} | "
        f"filas descargadas: {cache['filas_descargadas']}"
    )
    print(
        "Limitacion OHLC diaria: conocemos high y low de cada sesión, pero no su orden intradía. "
        "Si una vela toca stop y take-profit, no puede determinarse cuál ocurrió primero; una futura "
        "simulación deberá aplicar una convención conservadora. Los niveles mostrados aquí no se simulan."
    )


if __name__ == "__main__":
    main()
