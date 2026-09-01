import argparse
from collections import defaultdict
from datetime import date
from statistics import mean, median

from research.historical_market_data import obtener_historicos
from research.portfolio_whatif import (
    calcular_benchmark_spy,
    calcular_max_drawdown,
    cargar_scans_historicos,
    evaluar_candidatos_research,
    filtrar_resultados,
    parsear_fecha,
    reconstruir_candidatos_research,
    seleccionar_candidatos_sesion,
    simular_cartera,
)


STOPS = (None, -8, -10, -12, -15)
TAKE_PROFITS = (None, 10, 15, 20, 25)
HOLDING = 5
TOP = 5
MAX_POSITIONS = 10
CAPITAL = 10000.0
COST_PCT = 0.10


def resolver_salida(barra, entry_price, stop_pct, take_profit_pct):
    apertura = float(barra["open"])
    minimo = float(barra["low"])
    maximo = float(barra["high"])
    stop_price = entry_price * (1 + stop_pct / 100) if stop_pct is not None else None
    take_price = (
        entry_price * (1 + take_profit_pct / 100)
        if take_profit_pct is not None else None
    )

    if stop_price is not None and apertura <= stop_price:
        return "STOP", apertura, True, False
    if take_price is not None and apertura >= take_price:
        return "TAKE_PROFIT", apertura, False, True

    toca_stop = stop_price is not None and minimo <= stop_price
    toca_take = take_price is not None and maximo >= take_price
    if toca_stop and toca_take:
        return "STOP", stop_price, False, False, True
    if toca_stop:
        return "STOP", stop_price, False, False
    if toca_take:
        return "TAKE_PROFIT", take_price, False, False
    return None


def simular_cartera_salidas(
    resultados,
    historicos,
    strategy,
    stop_pct=None,
    take_profit_pct=None,
    capital=CAPITAL,
    holding=HOLDING,
    top=TOP,
    max_positions=MAX_POSITIONS,
    cost_pct=COST_PCT,
    spy_bars=None,
):
    candidatos = filtrar_resultados(resultados, strategy, holding)
    entradas = defaultdict(list)
    for candidato in candidatos:
        entradas[candidato["entry_date_obj"]].append(candidato)
    if not candidatos:
        return _resultado_vacio(strategy, stop_pct, take_profit_pct, capital)

    inicio = min(candidato["entry_date_obj"] for candidato in candidatos)
    fin = max(candidato["exit_date_obj"] for candidato in candidatos)
    calendario = {
        parsear_fecha(fila["date"])
        for fila in (spy_bars or [])
        if inicio <= parsear_fecha(fila["date"]) <= fin
    }
    calendario.update(candidato["entry_date_obj"] for candidato in candidatos)
    calendario.update(candidato["exit_date_obj"] for candidato in candidatos)
    fechas = sorted(calendario)
    barras = {
        symbol: {parsear_fecha(fila["date"]): fila for fila in filas}
        for symbol, filas in historicos.items()
    }

    efectivo = float(capital)
    coste_lado = cost_pct / 100
    abiertas = []
    trades = []
    equity_curve = []
    max_simultaneas = 0
    contadores = defaultdict(int)

    def cerrar(posicion, fecha, precio, motivo):
        nonlocal efectivo
        bruto = posicion["shares"] * precio
        ingreso = bruto * (1 - coste_lado)
        efectivo += ingreso
        pnl = ingreso - posicion["capital_allocated"]
        retorno = pnl / posicion["capital_allocated"] * 100
        trade = dict(posicion)
        trade.update(
            {
                "planned_exit_date": posicion["planned_exit_date"],
                "actual_exit_date": fecha,
                "actual_exit_price": precio,
                "exit_reason": motivo,
                "holding_sessions_real": posicion["holding_sessions_real"],
                "return_pct": retorno,
                "pnl": pnl,
            }
        )
        trades.append(trade)
        contadores[motivo] += 1

    for fecha in fechas:
        siguen = []
        for posicion in abiertas:
            barra = barras.get(posicion["symbol"], {}).get(fecha)
            if barra is not None:
                posicion["holding_sessions_real"] += 1
                posicion["last_close"] = float(barra["close"])
                salida = resolver_salida(
                    barra, posicion["entry_price"], stop_pct, take_profit_pct
                )
            else:
                salida = None

            if salida:
                motivo, precio, stop_gap, take_gap, *ambigua = salida
                contadores["stop_gap_exits"] += int(stop_gap)
                contadores["take_profit_gap_exits"] += int(take_gap)
                contadores["ambiguous_stop_tp"] += int(bool(ambigua and ambigua[0]))
                cerrar(posicion, fecha, precio, motivo)
            elif fecha == posicion["planned_exit_date"]:
                cerrar(posicion, fecha, posicion["planned_exit_price"], "TIME")
            else:
                siguen.append(posicion)
        abiertas = siguen

        huecos = max_positions - len(abiertas)
        seleccionados = seleccionar_candidatos_sesion(
            entradas.get(fecha, []),
            strategy,
            top,
            huecos,
            {posicion["symbol"] for posicion in abiertas},
        )
        nuevas = []
        if seleccionados and efectivo > 0:
            asignacion = efectivo / huecos
            for candidato in seleccionados:
                coste_entrada = asignacion * coste_lado
                capital_invertido = asignacion - coste_entrada
                posicion = {
                    "symbol": candidato["symbol"],
                    "strategy": strategy.upper(),
                    "signal_date": candidato["signal_date_obj"],
                    "entry_date": fecha,
                    "entry_price": candidato["entry_price"],
                    "planned_exit_date": candidato["exit_date_obj"],
                    "planned_exit_price": candidato["exit_price"],
                    "capital_allocated": asignacion,
                    "shares": capital_invertido / candidato["entry_price"],
                    "last_close": candidato["entry_price"],
                    "holding_sessions_real": 1,
                }
                efectivo -= asignacion
                barra = barras.get(posicion["symbol"], {}).get(fecha)
                if barra is not None:
                    posicion["last_close"] = float(barra["close"])
                    salida = resolver_salida(
                        barra, posicion["entry_price"], stop_pct, take_profit_pct
                    )
                else:
                    salida = None
                if salida:
                    motivo, precio, stop_gap, take_gap, *ambigua = salida
                    contadores["stop_gap_exits"] += int(stop_gap)
                    contadores["take_profit_gap_exits"] += int(take_gap)
                    contadores["ambiguous_stop_tp"] += int(bool(ambigua and ambigua[0]))
                    cerrar(posicion, fecha, precio, motivo)
                else:
                    nuevas.append(posicion)
        abiertas.extend(nuevas)
        max_simultaneas = max(max_simultaneas, len(abiertas))

        valor = sum(posicion["shares"] * posicion["last_close"] for posicion in abiertas)
        equity = efectivo + valor
        equity_curve.append(
            {
                "date": fecha,
                "equity": equity,
                "cash": efectivo,
                "exposure_pct": valor / equity * 100 if equity else 0,
                "idle_cash_pct": efectivo / equity * 100 if equity else 0,
            }
        )

    capital_final = efectivo + sum(
        posicion["shares"] * posicion["last_close"] for posicion in abiertas
    )
    retorno = (capital_final / capital - 1) * 100
    retornos = [trade["return_pct"] for trade in trades]
    benchmark = calcular_benchmark_spy(
        spy_bars or [], inicio, fin, capital, cost_pct
    )
    spy_return = benchmark["return_pct"] if benchmark else None
    return {
        "strategy": strategy.upper(),
        "stop_pct": stop_pct,
        "take_profit_pct": take_profit_pct,
        "trades": len(trades),
        "capital_final": capital_final,
        "return_pct": retorno,
        "spy_return_pct": spy_return,
        "excess_spy_pp": retorno - spy_return if spy_return is not None else None,
        "max_drawdown_pct": calcular_max_drawdown(equity_curve),
        "win_rate_pct": sum(valor > 0 for valor in retornos) / len(retornos) * 100 if retornos else 0,
        "avg_trade_pct": mean(retornos) if retornos else None,
        "median_trade_pct": median(retornos) if retornos else None,
        "exposure_avg_pct": mean(p["exposure_pct"] for p in equity_curve),
        "idle_cash_avg_pct": mean(p["idle_cash_pct"] for p in equity_curve),
        "exit_stop_count": contadores["STOP"],
        "exit_tp_count": contadores["TAKE_PROFIT"],
        "exit_time_count": contadores["TIME"],
        "stop_gap_exits": contadores["stop_gap_exits"],
        "take_profit_gap_exits": contadores["take_profit_gap_exits"],
        "ambiguous_stop_tp": contadores["ambiguous_stop_tp"],
        "best_trade_pct": max(retornos) if retornos else None,
        "worst_trade_pct": min(retornos) if retornos else None,
        "max_positions_real": max_simultaneas,
        "period_start": inicio,
        "period_end": fin,
        "trade_details": trades,
        "equity_curve": equity_curve,
    }


def _resultado_vacio(strategy, stop_pct, take_profit_pct, capital):
    return {
        "strategy": strategy.upper(), "stop_pct": stop_pct,
        "take_profit_pct": take_profit_pct, "trades": 0,
        "capital_final": capital, "return_pct": 0.0,
        "spy_return_pct": None, "excess_spy_pp": None,
        "max_drawdown_pct": 0.0, "win_rate_pct": 0.0,
        "avg_trade_pct": None, "median_trade_pct": None,
        "exposure_avg_pct": 0.0, "idle_cash_avg_pct": 100.0,
        "exit_stop_count": 0, "exit_tp_count": 0, "exit_time_count": 0,
        "stop_gap_exits": 0, "take_profit_gap_exits": 0,
        "ambiguous_stop_tp": 0, "best_trade_pct": None,
        "worst_trade_pct": None, "max_positions_real": 0,
        "period_start": None, "period_end": None,
        "trade_details": [], "equity_curve": [],
    }


def ejecutar_matriz(resultados, historicos, strategy, **kwargs):
    filas = []
    for stop_pct in STOPS:
        for take_profit_pct in TAKE_PROFITS:
            filas.append(
                simular_cartera_salidas(
                    resultados,
                    historicos,
                    strategy,
                    stop_pct=stop_pct,
                    take_profit_pct=take_profit_pct,
                    spy_bars=historicos.get("SPY", []),
                    **kwargs,
                )
            )
    base = next(
        fila for fila in filas
        if fila["stop_pct"] is None and fila["take_profit_pct"] is None
    )
    for fila in filas:
        fila["delta_return_pp"] = fila["return_pct"] - base["return_pct"]
        fila["delta_max_drawdown_pp"] = fila["max_drawdown_pct"] - base["max_drawdown_pct"]
        fila["delta_excess_pp"] = (
            fila["excess_spy_pp"] - base["excess_spy_pp"]
            if fila["excess_spy_pp"] is not None and base["excess_spy_pp"] is not None
            else None
        )
    return filas


def escenarios_no_dominados(filas):
    no_dominados = []
    for candidato in filas:
        dominado = any(
            otro is not candidato
            and otro["return_pct"] >= candidato["return_pct"]
            and otro["max_drawdown_pct"] >= candidato["max_drawdown_pct"]
            and (
                otro["return_pct"] > candidato["return_pct"]
                or otro["max_drawdown_pct"] > candidato["max_drawdown_pct"]
            )
            for otro in filas
        )
        if not dominado:
            no_dominados.append(candidato)
    return no_dominados


def resumir_estabilidad(filas, campo):
    grupos = defaultdict(list)
    for fila in filas:
        grupos[fila[campo]].append(fila)
    return [
        {
            campo: clave,
            "return_median": median(f["return_pct"] for f in grupo),
            "maxdd_median": median(f["max_drawdown_pct"] for f in grupo),
            "beat_spy_pct": sum(f["excess_spy_pp"] > 0 for f in grupo) / len(grupo) * 100,
        }
        for clave, grupo in grupos.items()
    ]


def validar_base(resultados, historicos, strategy, base, **kwargs):
    control = simular_cartera(
        resultados,
        strategy=strategy,
        historicos=historicos,
        spy_bars=historicos.get("SPY", []),
        **kwargs,
    )
    diferencias = {
        "trades": base["trades"] - control["operaciones"],
        "capital_final": base["capital_final"] - control["capital_final"],
        "return_pct": base["return_pct"] - control["retorno_total_pct"],
        "max_drawdown_pct": base["max_drawdown_pct"] - control["max_drawdown_pct"],
    }
    coincide = (
        diferencias["trades"] == 0
        and abs(diferencias["capital_final"]) < 0.01
        and abs(diferencias["return_pct"]) < 0.001
        and abs(diferencias["max_drawdown_pct"]) < 0.001
    )
    return coincide, diferencias


def preparar_datos(strategies):
    scans = cargar_scans_historicos()
    candidatos = {
        strategy: reconstruir_candidatos_research(scans, strategy)
        for strategy in strategies
    }
    todos = [senal for grupo in candidatos.values() for senal in grupo]
    inicio = min(parsear_fecha(senal["market_date"]) for senal in todos)
    historicos, cache = obtener_historicos(
        {senal["symbol"] for senal in todos} | {"SPY"}, inicio, date.today()
    )
    resultados = {}
    for strategy in strategies:
        resultados[strategy], _ = evaluar_candidatos_research(
            candidatos[strategy], historicos, HOLDING
        )
    return resultados, historicos, cache


def etiqueta(valor):
    return "NONE" if valor is None else f"{valor:+g}%"


def formato(valor):
    return f"{valor:+.2f}%" if valor is not None else "N/A"


def imprimir_resultados(strategy, filas):
    print(f"\n{strategy.upper()} - MATRIZ STOP / TAKE PROFIT")
    print("=" * 120)
    print("STRATEGY | STOP | TP | TRADES | RET | SPY | EXC | MAXDD | WIN | STOP# | TP# | TIME# | GAPS S/T | AMB")
    for fila in filas:
        print(
            f"{fila['strategy']:<9} | {etiqueta(fila['stop_pct']):>5} | "
            f"{etiqueta(fila['take_profit_pct']):>5} | {fila['trades']:>6} | "
            f"{formato(fila['return_pct']):>8} | {formato(fila['spy_return_pct']):>8} | "
            f"{formato(fila['excess_spy_pp']):>8} | {formato(fila['max_drawdown_pct']):>8} | "
            f"{formato(fila['win_rate_pct']):>8} | {fila['exit_stop_count']:>5} | "
            f"{fila['exit_tp_count']:>3} | {fila['exit_time_count']:>5} | "
            f"{fila['stop_gap_exits']:>2}/{fila['take_profit_gap_exits']:<2} | {fila['ambiguous_stop_tp']:>3}"
        )

    print("\nDELTA CONTRA NONE/NONE")
    for fila in filas:
        print(
            f"STOP {etiqueta(fila['stop_pct']):>5} TP {etiqueta(fila['take_profit_pct']):>5} | "
            f"Delta ret {fila['delta_return_pp']:+.2f}pp | "
            f"Delta MaxDD {fila['delta_max_drawdown_pp']:+.2f}pp | "
            f"Delta exceso {fila['delta_excess_pp']:+.2f}pp"
        )

    for campo, titulo in (("stop_pct", "POR STOP"), ("take_profit_pct", "POR TAKE PROFIT")):
        print(f"\n{titulo}")
        for resumen in resumir_estabilidad(filas, campo):
            print(
                f"{etiqueta(resumen[campo]):>5} | ret med {formato(resumen['return_median'])} | "
                f"MaxDD med {formato(resumen['maxdd_median'])} | bate SPY {formato(resumen['beat_spy_pct'])}"
            )

    print("\nESCENARIOS NO DOMINADOS RETORNO/DD")
    for fila in escenarios_no_dominados(filas):
        print(
            f"STOP {etiqueta(fila['stop_pct']):>5} TP {etiqueta(fila['take_profit_pct']):>5} | "
            f"ret {formato(fila['return_pct'])} | MaxDD {formato(fila['max_drawdown_pct'])}"
        )


def obtener_argumentos():
    parser = argparse.ArgumentParser(description="Stops/TP exclusivamente research/in-sample.")
    parser.add_argument("--strategy", choices=("momentum", "reversal"), default="momentum")
    parser.add_argument("--compare", action="store_true")
    return parser.parse_args()


def main():
    args = obtener_argumentos()
    strategies = ("momentum", "reversal") if args.compare else (args.strategy,)
    resultados, historicos, cache = preparar_datos(strategies)
    matrices = {}
    for strategy in strategies:
        matrices[strategy] = ejecutar_matriz(
            resultados[strategy], historicos, strategy
        )
        base = matrices[strategy][0]
        coincide, diferencias = validar_base(
            resultados[strategy],
            historicos,
            strategy,
            base,
            capital=CAPITAL,
            holding=HOLDING,
            top=TOP,
            max_positions=MAX_POSITIONS,
            cost_pct=COST_PCT,
        )
        if not coincide:
            raise RuntimeError(
                f"NONE/NONE no coincide con portfolio_whatif para {strategy}: {diferencias}"
            )

    print("STOP / TAKE-PROFIT ANALYSIS - RESEARCH / IN-SAMPLE")
    print("NO ES VALIDACION OUT-OF-SAMPLE")
    print("NONE/NONE coincide con portfolio_whatif en trades, capital, retorno y MaxDD.")
    for strategy in strategies:
        imprimir_resultados(strategy, matrices[strategy])
    print(
        f"\nCache hits: {cache['cache_hits']} | descargados: "
        f"{cache['symbols'] - cache['cache_hits']} | filas descargadas: {cache['filas_descargadas']}"
    )
    print(
        "OHLC diario no revela el orden intradía. Cuando stop y TP se alcanzan en la misma vela "
        "sin resolución por apertura, se aplica STOP PRIMERO de forma conservadora."
    )


if __name__ == "__main__":
    main()
