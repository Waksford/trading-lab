import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median

from database.db import (
    obtener_conexion,
    obtener_resultados_paper,
)
from scoring.momentum_v4 import (
    calcular_score_v4,
    clasificar_prioridad_v4,
)
from scoring.reversal_v1 import detectar_reversal_v1
from research.historical_market_data import obtener_historicos


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "whatif_trades.csv"

PRIORIDAD_MOMENTUM = {
    "A+": 0,
    "A": 1,
}

TRADE_COLUMNS = [
    "symbol",
    "strategy",
    "signal_date",
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "return_pct",
    "capital_allocated",
    "pnl",
    "mfe_pct",
    "mae_pct",
    "gross_return_pct",
    "entry_cost",
    "exit_cost",
]


def parsear_fecha(valor):
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def clave_ranking(resultado, strategy):
    if strategy == "momentum":
        return (
            PRIORIDAD_MOMENTUM.get(
                resultado.get("prioridad"),
                99
            ),
            -float(resultado.get("score") or 0),
            str(resultado.get("symbol") or ""),
        )

    return (
        -float(resultado.get("score") or 0),
        str(resultado.get("symbol") or ""),
    )


def seleccionar_candidatos_sesion(
    candidatos,
    strategy,
    top,
    huecos,
    symbols_abiertos=None,
):
    symbols_abiertos = symbols_abiertos or set()
    disponibles = [
        candidato
        for candidato in candidatos
        if candidato["symbol"] not in symbols_abiertos
    ]
    disponibles = sorted(
        disponibles,
        key=lambda fila: clave_ranking(fila, strategy),
    )
    unicos = []
    symbols_sesion = set()
    for candidato in disponibles:
        if candidato["symbol"] in symbols_sesion:
            continue
        symbols_sesion.add(candidato["symbol"])
        unicos.append(candidato)
    return unicos[:min(top, huecos)]


def filtrar_resultados(
    resultados,
    strategy,
    holding
):
    strategy_db = strategy.upper()
    filtrados = []

    for resultado in resultados:
        if resultado.get("strategy") != strategy_db:
            continue
        if int(resultado.get("horizonte") or 0) != holding:
            continue

        if strategy == "momentum":
            if resultado.get("source_score_version") != "v4":
                continue
            if resultado.get("prioridad") not in ("A+", "A"):
                continue
        else:
            if resultado.get("score_version") != "reversal_v1":
                continue
            if resultado.get("source_score_version") != "v4":
                continue
            if resultado.get("prioridad") != "A":
                continue

        try:
            signal_date = parsear_fecha(
                resultado["market_date"]
            )
            entry_date = parsear_fecha(
                resultado["fecha_entrada"]
            )
            exit_date = parsear_fecha(
                resultado["fecha_salida"]
            )
            entry_price = float(
                resultado["precio_entrada"]
            )
            exit_price = float(
                resultado["precio_salida"]
            )
        except (KeyError, TypeError, ValueError):
            continue

        # La senal debe existir antes de la entrada. Cualquier fila
        # inconsistente se descarta para evitar look-ahead accidental.
        if not signal_date < entry_date <= exit_date:
            continue
        if entry_price <= 0 or exit_price <= 0:
            continue

        fila = dict(resultado)
        fila.update(
            {
                "signal_date_obj": signal_date,
                "entry_date_obj": entry_date,
                "exit_date_obj": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
            }
        )
        filtrados.append(fila)

    return filtrados


def cargar_scans_historicos():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT
            id,
            scan_time,
            market_date,
            symbol,
            tendencia,
            volatilidad,
            rsi,
            volumen_relativo,
            fuerza_20d,
            fuerza_60d,
            distancia_sma20,
            fuerza_sector_20d,
            fuerza_sector_60d
        FROM scans
        WHERE market_date IS NOT NULL
        ORDER BY
            market_date ASC,
            symbol ASC,
            scan_time DESC,
            id DESC
        """
    )
    filas = cursor.fetchall()
    conexion.close()

    unicos = {}

    for fila in filas:
        fila = dict(fila)
        clave = (
            fila["market_date"],
            fila["symbol"]
        )
        if clave not in unicos:
            unicos[clave] = fila

    return list(unicos.values())


def construir_indice_resultados_futuros(
    resultados,
    holding
):
    grupos = defaultdict(list)

    for resultado in resultados:
        if int(resultado.get("horizonte") or 0) != holding:
            continue
        clave = (
            str(resultado.get("symbol") or "").strip().upper(),
            str(resultado.get("market_date") or ""),
            holding,
        )
        if clave[0] and clave[1]:
            grupos[clave].append(resultado)

    indice = {}
    duplicados = 0
    duplicados_inconsistentes = 0

    for clave, filas in grupos.items():
        filas = sorted(
            filas,
            key=lambda fila: (
                int(fila.get("id") or 0),
                int(fila.get("signal_id") or 0),
            )
        )
        indice[clave] = filas[0]

        if len(filas) > 1:
            duplicados += len(filas) - 1
            valores = {
                (
                    fila.get("fecha_entrada"),
                    fila.get("precio_entrada"),
                    fila.get("fecha_salida"),
                    fila.get("precio_salida"),
                )
                for fila in filas
            }
            if len(valores) > 1:
                duplicados_inconsistentes += 1

    return indice, {
        "duplicados_resultado": duplicados,
        "duplicados_inconsistentes": duplicados_inconsistentes,
    }


def reconstruir_senales_research(
    scans,
    resultados_futuros,
    strategy,
    holding
):
    indice, diagnostico = construir_indice_resultados_futuros(
        resultados_futuros,
        holding
    )
    senales = []
    reconstruidas = 0

    for scan in scans:
        score = calcular_score_v4(
            tendencia=scan.get("tendencia"),
            rsi=scan.get("rsi"),
            fuerza_20d=scan.get("fuerza_20d"),
            fuerza_60d=scan.get("fuerza_60d"),
            fuerza_sector_20d=scan.get("fuerza_sector_20d"),
            fuerza_sector_60d=scan.get("fuerza_sector_60d"),
            distancia_sma20=scan.get("distancia_sma20"),
            volumen_relativo=scan.get("volumen_relativo"),
            volatilidad=scan.get("volatilidad"),
        )["total"]
        prioridad = clasificar_prioridad_v4(
            score
        )

        if strategy == "momentum":
            if prioridad not in ("A+", "A"):
                continue
            prioridad_senal = prioridad
            score_version = "v4"
            strategy_db = "MOMENTUM"
        else:
            reversal = detectar_reversal_v1(
                score_v4=score,
                rsi=scan.get("rsi"),
                distancia_sma20=scan.get("distancia_sma20"),
                volatilidad=scan.get("volatilidad"),
            )
            if not (
                reversal.get("candidate")
                and reversal.get("priority") == "A"
            ):
                continue
            prioridad_senal = "A"
            score_version = "reversal_v1"
            strategy_db = "REVERSAL"

        reconstruidas += 1
        clave = (
            str(scan.get("symbol") or "").strip().upper(),
            str(scan.get("market_date") or ""),
            holding,
        )
        futuro = indice.get(clave)

        if futuro is None:
            continue

        senal = dict(futuro)
        senal.update(
            {
                "symbol": clave[0],
                "market_date": clave[1],
                "strategy": strategy_db,
                "source_score_version": "v4",
                "score_version": score_version,
                "prioridad": prioridad_senal,
                "score": score,
            }
        )
        senales.append(senal)

    metadata = {
        "senales_reconstruidas": reconstruidas,
        "con_resultado_futuro": len(senales),
        **diagnostico,
    }
    return senales, metadata


def reconstruir_candidatos_research(scans, strategy):
    """Reconstruye señales usando exclusivamente métricas del día del scan."""
    senales = []

    for scan in scans:
        score = calcular_score_v4(
            tendencia=scan.get("tendencia"),
            rsi=scan.get("rsi"),
            fuerza_20d=scan.get("fuerza_20d"),
            fuerza_60d=scan.get("fuerza_60d"),
            fuerza_sector_20d=scan.get("fuerza_sector_20d"),
            fuerza_sector_60d=scan.get("fuerza_sector_60d"),
            distancia_sma20=scan.get("distancia_sma20"),
            volumen_relativo=scan.get("volumen_relativo"),
            volatilidad=scan.get("volatilidad"),
        )["total"]
        prioridad = clasificar_prioridad_v4(score)

        if strategy == "momentum":
            if prioridad not in ("A+", "A"):
                continue
            strategy_db = "MOMENTUM"
            score_version = "v4"
        else:
            reversal = detectar_reversal_v1(
                score_v4=score,
                rsi=scan.get("rsi"),
                distancia_sma20=scan.get("distancia_sma20"),
                volatilidad=scan.get("volatilidad"),
            )
            if not (reversal.get("candidate") and reversal.get("priority") == "A"):
                continue
            prioridad = "A"
            strategy_db = "REVERSAL"
            score_version = "reversal_v1"

        symbol = str(scan.get("symbol") or "").strip().upper()
        market_date = str(scan.get("market_date") or "")
        if not symbol or not market_date:
            continue
        senales.append(
            {
                "symbol": symbol,
                "market_date": market_date,
                "strategy": strategy_db,
                "source_score_version": "v4",
                "score_version": score_version,
                "prioridad": prioridad,
                "score": score,
            }
        )

    return senales


def evaluar_senal_historica(senal, historico, holding):
    """Entrada en apertura D+1 y salida al cierre de la sesión holding."""
    signal_date = parsear_fecha(senal["market_date"])
    posteriores = sorted(
        (fila for fila in historico if parsear_fecha(fila["date"]) > signal_date),
        key=lambda fila: parsear_fecha(fila["date"]),
    )
    if not posteriores:
        return None, "sin_entrada"
    if len(posteriores) < holding:
        return None, "sin_salida"

    entrada = posteriores[0]
    ventana = posteriores[:holding]
    salida = ventana[-1]
    precio_entrada = float(entrada["open"])
    precio_salida = float(salida["close"])
    if precio_entrada <= 0 or precio_salida <= 0:
        return None, "precio_invalido"

    resultado = dict(senal)
    resultado.update(
        {
            "horizonte": holding,
            "fecha_entrada": str(parsear_fecha(entrada["date"])),
            "precio_entrada": precio_entrada,
            "fecha_salida": str(parsear_fecha(salida["date"])),
            "precio_salida": precio_salida,
            "gross_return_pct": (precio_salida / precio_entrada - 1) * 100,
            "mfe_pct": (max(float(fila["high"]) for fila in ventana) / precio_entrada - 1) * 100,
            "mae_pct": (min(float(fila["low"]) for fila in ventana) / precio_entrada - 1) * 100,
        }
    )
    resultado["max_favorable_excursion_pct"] = resultado["mfe_pct"]
    resultado["max_adverse_excursion_pct"] = resultado["mae_pct"]
    return resultado, "completa"


def evaluar_candidatos_research(candidatos, historicos, holding):
    resultados = []
    cobertura = {
        "senales_reconstruidas": len(candidatos),
        "con_entrada": 0,
        "con_salida_5d": 0,
        "con_salida_20d": 0,
        "con_salida_60d": 0,
    }

    for senal in candidatos:
        historico = historicos.get(senal["symbol"], [])
        estados = {}
        for horizonte in (5, 20, 60):
            evaluada, estado = evaluar_senal_historica(senal, historico, horizonte)
            estados[horizonte] = (evaluada, estado)
            if estado != "sin_entrada":
                cobertura["con_entrada"] += int(horizonte == 5)
            if evaluada is not None:
                cobertura[f"con_salida_{horizonte}d"] += 1
        evaluada, _ = estados[holding]
        if evaluada is not None:
            resultados.append(evaluada)

    cobertura["con_resultado_futuro"] = len(resultados)
    cobertura["duplicados_resultado"] = 0
    cobertura["duplicados_inconsistentes"] = 0
    return resultados, cobertura


def calcular_benchmark_spy(spy_bars, inicio, fin, capital, cost_pct):
    barras = sorted(
        (
            fila for fila in spy_bars
            if inicio <= parsear_fecha(fila["date"]) <= fin
        ),
        key=lambda fila: parsear_fecha(fila["date"]),
    )
    if not barras:
        return None
    coste = cost_pct / 100.0
    shares = capital * (1 - coste) / float(barras[0]["open"])
    capital_final = shares * float(barras[-1]["close"]) * (1 - coste)
    return {
        "capital_final": capital_final,
        "return_pct": (capital_final / capital - 1) * 100,
        "inicio": parsear_fecha(barras[0]["date"]),
        "fin": parsear_fecha(barras[-1]["date"]),
    }


def calcular_max_drawdown(equity_curve):
    if not equity_curve:
        return 0.0

    pico = float(equity_curve[0]["equity"])
    peor = 0.0

    for punto in equity_curve:
        equity = float(punto["equity"])
        pico = max(pico, equity)
        if pico > 0:
            peor = min(
                peor,
                (equity / pico - 1) * 100
            )

    return peor


def simular_cartera(
    resultados,
    capital=10000.0,
    strategy="momentum",
    holding=20,
    top=5,
    max_positions=10,
    cost_pct=0.10,
    spy_return_pct=None,
    historicos=None,
    spy_bars=None,
):
    if capital <= 0:
        raise ValueError("capital debe ser positivo")
    if strategy not in ("momentum", "reversal"):
        raise ValueError("strategy debe ser momentum o reversal")
    if holding not in (5, 20, 60):
        raise ValueError("holding debe ser 5, 20 o 60")
    if top <= 0 or max_positions <= 0:
        raise ValueError("top y max_positions deben ser positivos")
    if cost_pct < 0:
        raise ValueError("cost_pct no puede ser negativo")

    candidatos = filtrar_resultados(
        resultados,
        strategy,
        holding
    )
    entradas = defaultdict(list)

    for candidato in candidatos:
        entradas[candidato["entry_date_obj"]].append(
            candidato
        )

    fechas_eventos = sorted(
        {
            candidato["entry_date_obj"]
            for candidato in candidatos
        }
        | {
            candidato["exit_date_obj"]
            for candidato in candidatos
        }
    )
    mtm_real = historicos is not None
    if mtm_real and fechas_eventos:
        inicio_eventos = fechas_eventos[0]
        fin_eventos = fechas_eventos[-1]
        calendario = {
            parsear_fecha(fila["date"])
            for fila in (spy_bars or [])
            if inicio_eventos <= parsear_fecha(fila["date"]) <= fin_eventos
        }
        calendario.update(fechas_eventos)
        fechas = sorted(calendario)
    else:
        fechas = fechas_eventos

    cierres = {
        symbol: {
            parsear_fecha(fila["date"]): float(fila["close"])
            for fila in filas
        }
        for symbol, filas in (historicos or {}).items()
    }

    capital_inicial = float(capital)
    efectivo = capital_inicial
    coste_lado = float(cost_pct) / 100.0
    abiertas = []
    trades = []
    equity_curve = []
    max_simultaneas = 0

    for fecha in fechas:
        siguen_abiertas = []

        # Los cierres se procesan antes que nuevas entradas para que
        # el capital liberado pueda reutilizarse en la misma sesion.
        for posicion in abiertas:
            if posicion["exit_date"] != fecha:
                siguen_abiertas.append(posicion)
                continue

            valor_bruto_salida = (
                posicion["shares"]
                * posicion["exit_price"]
            )
            ingreso_salida = (
                valor_bruto_salida
                * (1 - coste_lado)
            )
            efectivo += ingreso_salida
            pnl = (
                ingreso_salida
                - posicion["capital_allocated"]
            )
            retorno = (
                pnl
                / posicion["capital_allocated"]
                * 100
            )

            trade = dict(posicion)
            trade.update(
                {
                    "return_pct": retorno,
                    "pnl": pnl,
                    "gross_return_pct": (
                        posicion["exit_price"] / posicion["entry_price"] - 1
                    ) * 100,
                    "exit_cost": valor_bruto_salida * coste_lado,
                }
            )
            trades.append(trade)

        abiertas = siguen_abiertas

        symbols_abiertos = {
            posicion["symbol"]
            for posicion in abiertas
        }
        huecos = max_positions - len(abiertas)
        seleccionados = seleccionar_candidatos_sesion(
            entradas.get(fecha, []),
            strategy,
            top,
            huecos,
            symbols_abiertos,
        )

        if seleccionados and efectivo > 0:
            asignacion = efectivo / huecos

            for candidato in seleccionados:
                coste_entrada = asignacion * coste_lado
                capital_invertido = asignacion - coste_entrada
                shares = (
                    capital_invertido
                    / candidato["entry_price"]
                )
                efectivo -= asignacion

                abiertas.append(
                    {
                        "symbol": candidato["symbol"],
                        "strategy": strategy.upper(),
                        "signal_date": candidato["signal_date_obj"],
                        "entry_date": candidato["entry_date_obj"],
                        "exit_date": candidato["exit_date_obj"],
                        "entry_price": candidato["entry_price"],
                        "exit_price": candidato["exit_price"],
                        "capital_allocated": asignacion,
                        "entry_cost": coste_entrada,
                        "shares": shares,
                        "book_value": capital_invertido,
                        "last_close": candidato["entry_price"],
                        "score": candidato.get("score"),
                        "prioridad": candidato.get("prioridad"),
                        "mfe_pct": candidato.get("mfe_pct"),
                        "mae_pct": candidato.get("mae_pct"),
                        "max_favorable_excursion_pct": candidato.get(
                            "max_favorable_excursion_pct"
                        ),
                        "max_adverse_excursion_pct": candidato.get(
                            "max_adverse_excursion_pct"
                        ),
                    }
                )

        max_simultaneas = max(
            max_simultaneas,
            len(abiertas)
        )
        if mtm_real:
            for posicion in abiertas:
                cierre = cierres.get(posicion["symbol"], {}).get(fecha)
                if cierre is not None:
                    posicion["last_close"] = cierre
            valor_posiciones = sum(
                posicion["shares"] * posicion["last_close"]
                for posicion in abiertas
            )
        else:
            valor_posiciones = sum(
                posicion["book_value"]
                for posicion in abiertas
            )
        equity = efectivo + valor_posiciones
        exposicion = (
            valor_posiciones / equity * 100
            if equity > 0
            else 0.0
        )
        equity_curve.append(
            {
                "date": fecha,
                "equity": equity,
                "cash": efectivo,
                "open_positions": len(abiertas),
                "exposure_pct": exposicion,
                "idle_cash_pct": (
                    efectivo / equity * 100 if equity > 0 else 0.0
                ),
            }
        )

    retornos = [
        trade["return_pct"]
        for trade in trades
    ]
    capital_final = efectivo + sum(
        (
            posicion["shares"] * posicion["last_close"]
            if mtm_real
            else posicion["book_value"]
        )
        for posicion in abiertas
    )
    retorno_total = (
        capital_final / capital_inicial - 1
    ) * 100
    ganadoras = sum(
        retorno > 0
        for retorno in retornos
    )

    benchmark = None
    if mtm_real and spy_bars and fechas:
        benchmark = calcular_benchmark_spy(
            spy_bars,
            fechas[0],
            fechas[-1],
            capital_inicial,
            cost_pct,
        )
        if benchmark:
            spy_return_pct = benchmark["return_pct"]

    return {
        "strategy": strategy.upper(),
        "holding": holding,
        "capital_inicial": capital_inicial,
        "capital_final": capital_final,
        "retorno_total_pct": retorno_total,
        "operaciones": len(trades),
        "ganadoras": ganadoras,
        "win_rate_pct": (
            ganadoras / len(trades) * 100
            if trades
            else 0.0
        ),
        "retorno_medio_trade_pct": (
            mean(retornos) if retornos else None
        ),
        "retorno_mediana_trade_pct": (
            median(retornos) if retornos else None
        ),
        "mejor_trade_pct": max(retornos) if retornos else None,
        "peor_trade_pct": min(retornos) if retornos else None,
        "max_drawdown_pct": calcular_max_drawdown(
            equity_curve
        ),
        "max_posiciones_simultaneas": max_simultaneas,
        "exposicion_media_pct": (
            mean(
                punto["exposure_pct"]
                for punto in equity_curve
            )
            if equity_curve
            else 0.0
        ),
        "capital_ocioso_medio_pct": (
            mean(punto["idle_cash_pct"] for punto in equity_curve)
            if equity_curve else 100.0
        ),
        "mtm_real": mtm_real,
        "spy_capital_final": benchmark["capital_final"] if benchmark else None,
        "spy_return_pct": spy_return_pct,
        "exceso_spy_pct": (
            retorno_total - spy_return_pct
            if spy_return_pct is not None
            else None
        ),
        "periodo_inicio": fechas[0] if fechas else None,
        "periodo_fin": fechas[-1] if fechas else None,
        "trades": trades,
        "equity_curve": equity_curve,
        "posiciones_abiertas_final": len(abiertas),
    }


def formato_pct(valor):
    return (
        f"{valor:+.2f}%"
        if valor is not None
        else "N/A"
    )


def imprimir_trades(titulo, trades):
    print()
    print(titulo)
    print("-" * 120)

    if not trades:
        print("SIN OPERACIONES")
        return

    print(
        "SYMBOL  STRATEGY  SIGNAL      ENTRY       EXIT        "
        "ENTRY_PX  EXIT_PX   RETURN     CAPITAL       PNL"
    )

    for trade in trades:
        print(
            f"{trade['symbol']:<7} "
            f"{trade['strategy']:<9} "
            f"{str(trade['signal_date']):<11} "
            f"{str(trade['entry_date']):<11} "
            f"{str(trade['exit_date']):<11} "
            f"${trade['entry_price']:>7.2f} "
            f"${trade['exit_price']:>7.2f} "
            f"{trade['return_pct']:>+8.2f}% "
            f"${trade['capital_allocated']:>10.2f} "
            f"${trade['pnl']:>+9.2f}"
        )


def imprimir_resumen(
    resultado,
    mode="paper",
    metadata=None
):
    print()

    if mode == "research":
        print("=" * 60)
        print("      PORTFOLIO WHAT-IF - RESEARCH")
        print("=" * 60)
        print()
        print("ATENCION:")
        print("Simulacion retrospectiva/in-sample.")
        print(
            "V4/Reversal fueron desarrollados utilizando parte de este historico."
        )
        print("No representa validacion out-of-sample.")
    else:
        print("PORTFOLIO WHAT-IF")
        print("=" * 60)

    if metadata:
        print()
        print(
            "Senales reconstruidas:          "
            f"{metadata['senales_reconstruidas']}"
        )
        print(
            "Con resultado futuro:           "
            f"{metadata['con_resultado_futuro']}"
        )
        if "con_entrada" in metadata:
            print(f"Con entrada D+1:               {metadata['con_entrada']}")
            print(f"Con salida 5 sesiones:         {metadata['con_salida_5d']}")
            print(f"Con salida 20 sesiones:        {metadata['con_salida_20d']}")
            print(f"Con salida 60 sesiones:        {metadata['con_salida_60d']}")
        cache = metadata.get("cache")
        if cache:
            print(
                "Cache precios:                 "
                f"{cache['cache_hits']}/{cache['symbols']} hits | "
                f"{cache['filas_descargadas']} filas descargadas | "
                f"{cache['errores']} errores"
            )
        print(
            "Duplicados descartados:         "
            f"{metadata['duplicados_resultado']}"
        )
        print(
            "Duplicados inconsistentes:      "
            f"{metadata['duplicados_inconsistentes']}"
        )

    if resultado["periodo_inicio"] is None:
        print("No existen resultados compatibles y maduros.")
        return

    print(
        f"Periodo:                       "
        f"{resultado['periodo_inicio']} -> {resultado['periodo_fin']}"
    )
    print(f"Estrategia:                    {resultado['strategy']}")
    print(f"Holding:                       {resultado['holding']} sesiones")
    print(f"Capital inicial:               ${resultado['capital_inicial']:,.2f}")
    print(f"Capital final:                 ${resultado['capital_final']:,.2f}")
    print(f"Rentabilidad total:            {formato_pct(resultado['retorno_total_pct'])}")
    print(f"Operaciones:                   {resultado['operaciones']}")
    print(f"Sesiones/eventos:              {len(resultado['equity_curve'])}")
    print(f"Ganadoras:                     {resultado['ganadoras']}")
    print(f"Win rate:                      {formato_pct(resultado['win_rate_pct'])}")
    print(f"Retorno medio trade:           {formato_pct(resultado['retorno_medio_trade_pct'])}")
    print(f"Mediana trade:                 {formato_pct(resultado['retorno_mediana_trade_pct'])}")
    print(f"Mejor trade:                   {formato_pct(resultado['mejor_trade_pct'])}")
    print(f"Peor trade:                    {formato_pct(resultado['peor_trade_pct'])}")
    print(f"Max drawdown cartera:          {formato_pct(resultado['max_drawdown_pct'])}")
    print(f"Posiciones simultaneas max.:   {resultado['max_posiciones_simultaneas']}")
    print(f"Exposicion media:              {formato_pct(resultado['exposicion_media_pct'])}")
    print(f"Capital ocioso medio:          {formato_pct(resultado['capital_ocioso_medio_pct'])}")
    if resultado["spy_return_pct"] is None:
        print("SPY buy-and-hold:              NO DISPONIBLE")
        print("Exceso cartera vs SPY:         NO DISPONIBLE")
    else:
        print(f"Capital final SPY:             ${resultado['spy_capital_final']:,.2f}")
        print(f"SPY buy-and-hold:              {formato_pct(resultado['spy_return_pct'])}")
        print(f"Exceso cartera vs SPY:         {formato_pct(resultado['exceso_spy_pct'])}")

    print()
    if resultado["mtm_real"]:
        print(
            "Equity, drawdown y exposicion calculados mark-to-market con cierres "
            "historicos. Ante una cotizacion ausente se conserva el ultimo cierre."
        )
    else:
        print(
            "Limitacion del modo paper: la equity entre eventos conserva las "
            "posiciones a valor de entrada; drawdown y exposicion son aproximados."
        )

    ordenados = sorted(
        resultado["trades"],
        key=lambda trade: trade["return_pct"],
        reverse=True
    )
    imprimir_trades(
        "TOP 10 MEJORES TRADES",
        ordenados[:10]
    )
    imprimir_trades(
        "TOP 10 PEORES TRADES",
        list(reversed(ordenados[-10:]))
    )


def obtener_argumentos():
    parser = argparse.ArgumentParser(
        description="Simulador historico de cartera sobre paper_results."
    )
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument(
        "--mode",
        choices=("paper", "research"),
        default="paper"
    )
    parser.add_argument(
        "--strategy",
        choices=("momentum", "reversal"),
        default="momentum"
    )
    parser.add_argument("--holding", type=int, choices=(5, 20, 60), required=True)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument(
        "--cost-pct",
        type=float,
        default=0.10,
        help="Coste porcentual por lado, aplicado en entrada y salida."
    )
    parser.add_argument("--export-csv", action="store_true")
    parser.add_argument("--compare", action="store_true")
    return parser.parse_args()


def ejecutar_escenario(
    args,
    strategy
):
    metadata = None

    if args.mode == "paper":
        resultados = obtener_resultados_paper(
            strategy=strategy.upper()
        )
    else:
        scans = cargar_scans_historicos()
        candidatos = reconstruir_candidatos_research(
            scans, strategy
        )
        if candidatos:
            inicio = min(parsear_fecha(fila["market_date"]) for fila in candidatos)
            fin = date.today()
            symbols = {fila["symbol"] for fila in candidatos} | {"SPY"}
            historicos, cache = obtener_historicos(symbols, inicio, fin)
        else:
            historicos, cache = {"SPY": []}, {
                "symbols": 0, "cache_hits": 0, "filas_cache": 0,
                "filas_descargadas": 0, "errores": 0,
            }
        resultados, metadata = evaluar_candidatos_research(
            candidatos, historicos, args.holding
        )
        metadata["cache"] = cache

    simulacion = simular_cartera(
        resultados,
        capital=args.capital,
        strategy=strategy,
        holding=args.holding,
        top=args.top,
        max_positions=args.max_positions,
        cost_pct=args.cost_pct,
        historicos=(historicos if args.mode == "research" else None),
        spy_bars=(historicos.get("SPY", []) if args.mode == "research" else None),
    )
    return simulacion, metadata


def imprimir_comparacion(resultados):
    print()
    print("COMPARACION DE ESCENARIOS - RESEARCH / IN-SAMPLE")
    print("=" * 90)
    print(
        "ESTRATEGIA | TRADES | CAPITAL FINAL | RETORNO | MAX DD | WIN RATE"
    )

    for simulacion, _ in resultados:
        print(
            f"{simulacion['strategy']:<10} | "
            f"{simulacion['operaciones']:>6} | "
            f"${simulacion['capital_final']:>12,.2f} | "
            f"{simulacion['retorno_total_pct']:>+7.2f}% | "
            f"{simulacion['max_drawdown_pct']:>+6.2f}% | "
            f"{simulacion['win_rate_pct']:>7.2f}%"
        )


def main():
    args = obtener_argumentos()

    if args.compare:
        if args.mode != "research":
            raise ValueError("--compare requiere --mode research")
        escenarios = [
            ejecutar_escenario(args, strategy)
            for strategy in ("momentum", "reversal")
        ]

        for simulacion, metadata in escenarios:
            imprimir_resumen(
                simulacion,
                mode="research",
                metadata=metadata
            )
        imprimir_comparacion(escenarios)
        return

    simulacion, metadata = ejecutar_escenario(
        args,
        args.strategy
    )
    imprimir_resumen(
        simulacion,
        mode=args.mode,
        metadata=metadata
    )

    if args.export_csv:
        CSV_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        with CSV_PATH.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:
            escritor = csv.DictWriter(
                archivo,
                fieldnames=TRADE_COLUMNS,
                extrasaction="ignore"
            )
            escritor.writeheader()
            escritor.writerows(
                simulacion["trades"]
            )
        print(f"\nCSV guardado en: {CSV_PATH}")


if __name__ == "__main__":
    main()
