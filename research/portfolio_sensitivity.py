import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

from research.historical_market_data import obtener_historicos
from research.portfolio_whatif import (
    cargar_scans_historicos,
    evaluar_candidatos_research,
    parsear_fecha,
    reconstruir_candidatos_research,
    simular_cartera,
)


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "portfolio_sensitivity.csv"
STRATEGIES = ("momentum", "reversal")
HOLDINGS = (5, 20)
TOPS = (3, 5, 10)
MAX_POSITIONS = (5, 10, 20)
CAPITAL = 10000.0
COST_PCT = 0.10

CSV_COLUMNS = (
    "strategy", "holding", "top", "max_positions", "capital_inicial",
    "capital_final", "retorno_pct", "spy_retorno_pct", "exceso_spy_pp",
    "max_drawdown_pct", "win_rate_pct", "trades",
    "retorno_medio_trade_pct", "mediana_trade_pct", "exposicion_media_pct",
    "max_posiciones_reales", "period_start", "period_end", "sample_quality",
)


def clasificar_muestra(trades):
    if trades < 20:
        return "MUY BAJA"
    if trades < 50:
        return "BAJA"
    if trades < 100:
        return "MEDIA"
    return "BUENA"


def crear_fila(simulacion, strategy, holding, top, max_positions):
    trades = simulacion["operaciones"]
    return {
        "strategy": strategy.upper(),
        "holding": holding,
        "top": top,
        "max_positions": max_positions,
        "capital_inicial": simulacion["capital_inicial"],
        "capital_final": simulacion["capital_final"],
        "retorno_pct": simulacion["retorno_total_pct"],
        "spy_retorno_pct": simulacion["spy_return_pct"],
        "exceso_spy_pp": simulacion["exceso_spy_pct"],
        "max_drawdown_pct": simulacion["max_drawdown_pct"],
        "win_rate_pct": simulacion["win_rate_pct"],
        "trades": trades,
        "retorno_medio_trade_pct": simulacion["retorno_medio_trade_pct"],
        "mediana_trade_pct": simulacion["retorno_mediana_trade_pct"],
        "exposicion_media_pct": simulacion["exposicion_media_pct"],
        "max_posiciones_reales": simulacion["max_posiciones_simultaneas"],
        "period_start": simulacion["periodo_inicio"],
        "period_end": simulacion["periodo_fin"],
        "sample_quality": clasificar_muestra(trades),
    }


def generar_escenarios(
    resultados_por_clave,
    historicos,
    simulador=simular_cartera,
    capital=CAPITAL,
    cost_pct=COST_PCT,
):
    filas = []
    for strategy in STRATEGIES:
        for holding in HOLDINGS:
            resultados = resultados_por_clave[(strategy, holding)]
            for top in TOPS:
                for max_positions in MAX_POSITIONS:
                    simulacion = simulador(
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
                    filas.append(
                        crear_fila(
                            simulacion, strategy, holding, top, max_positions
                        )
                    )
    return filas


def mediana_disponible(filas, campo):
    valores = [fila[campo] for fila in filas if fila.get(campo) is not None]
    return median(valores) if valores else None


def clasificar_robustez(filas):
    excesos = [fila["exceso_spy_pp"] for fila in filas if fila["exceso_spy_pp"] is not None]
    retorno_mediano = mediana_disponible(filas, "retorno_pct")
    dd_mediano = mediana_disponible(filas, "max_drawdown_pct")
    porcentaje_exceso = (
        sum(valor > 0 for valor in excesos) / len(excesos) * 100
        if excesos else None
    )
    # Los mismos trades reaparecen en configuraciones distintas; sumarlos
    # inflaría artificialmente la muestra. Exigimos que al menos un escenario
    # individual alcance calidad MEDIA.
    muestra_razonable = max((fila["trades"] for fila in filas), default=0) >= 50

    if (
        porcentaje_exceso is not None
        and porcentaje_exceso >= 70
        and retorno_mediano is not None and retorno_mediano > 0
        and dd_mediano is not None and dd_mediano > -20
        and muestra_razonable
    ):
        return "ROBUSTO"
    if (
        retorno_mediano is None or retorno_mediano <= 0
        or porcentaje_exceso is None or porcentaje_exceso < 50
    ):
        return "DEBIL"
    return "MIXTO"


def resumir_por_strategy_holding(filas):
    grupos = defaultdict(list)
    for fila in filas:
        grupos[(fila["strategy"], fila["holding"])].append(fila)

    resumenes = []
    for clave in sorted(grupos):
        grupo = grupos[clave]
        excesos = [fila["exceso_spy_pp"] for fila in grupo if fila["exceso_spy_pp"] is not None]
        retornos = [fila["retorno_pct"] for fila in grupo if fila["retorno_pct"] is not None]
        resumenes.append(
            {
                "strategy": clave[0],
                "holding": clave[1],
                "escenarios": len(grupo),
                "retorno_mediano": mediana_disponible(grupo, "retorno_pct"),
                "exceso_mediano": mediana_disponible(grupo, "exceso_spy_pp"),
                "maxdd_mediano": mediana_disponible(grupo, "max_drawdown_pct"),
                "pct_exceso_positivo": (
                    sum(valor > 0 for valor in excesos) / len(excesos) * 100
                    if excesos else None
                ),
                "pct_retorno_positivo": (
                    sum(valor > 0 for valor in retornos) / len(retornos) * 100
                    if retornos else None
                ),
                "robustez": clasificar_robustez(grupo),
            }
        )
    return resumenes


def resumir_estabilidad(filas, dimension):
    grupos = defaultdict(list)
    for fila in filas:
        grupos[(fila["strategy"], fila["holding"], fila[dimension])].append(fila)
    return [
        {
            "strategy": clave[0],
            "holding": clave[1],
            dimension: clave[2],
            "retorno_mediano": mediana_disponible(grupo, "retorno_pct"),
            "exceso_mediano": mediana_disponible(grupo, "exceso_spy_pp"),
            "maxdd_mediano": mediana_disponible(grupo, "max_drawdown_pct"),
        }
        for clave, grupo in sorted(grupos.items())
    ]


def detectar_sobreajuste(filas):
    avisos = []
    grupos = defaultdict(list)
    for fila in filas:
        grupos[(fila["strategy"], fila["holding"])].append(fila)

    for (strategy, holding), grupo in sorted(grupos.items()):
        retornos = sorted((fila["retorno_pct"] for fila in grupo), reverse=True)
        if len(retornos) > 1 and retornos[0] - retornos[1] > 20:
            avisos.append(
                f"{strategy} {holding}D: una combinacion supera a la siguiente por mas de 20pp."
            )
        por_top = {
            top: mediana_disponible([fila for fila in grupo if fila["top"] == top], "retorno_pct")
            for top in TOPS
        }
        if por_top[5] is not None and por_top[5] > 0 and por_top[3] <= 0 and por_top[10] <= 0:
            avisos.append(
                f"{strategy} {holding}D: resultado sensible a TOP; Top5 positivo y Top3/Top10 no positivos."
            )
        por_max = [
            mediana_disponible(
                [fila for fila in grupo if fila["max_positions"] == valor],
                "retorno_pct",
            )
            for valor in MAX_POSITIONS
        ]
        if max(por_max) - min(por_max) > 20:
            avisos.append(
                f"{strategy} {holding}D: cambios de max_positions alteran el retorno mediano en mas de 20pp."
            )

    for strategy in (valor.upper() for valor in STRATEGIES):
        cinco = [fila for fila in filas if fila["strategy"] == strategy and fila["holding"] == 5]
        veinte = [fila for fila in filas if fila["strategy"] == strategy and fila["holding"] == 20]
        mediana_5 = mediana_disponible(cinco, "retorno_pct")
        mediana_20 = mediana_disponible(veinte, "retorno_pct")
        if mediana_20 is not None and mediana_20 > 0 and mediana_5 is not None and mediana_5 <= 0:
            avisos.append(
                f"{strategy}: 20D positivo, pero 5D no positivo; posible sensibilidad al holding."
            )
    return avisos or ["No se detectan señales visuales claras con las reglas descriptivas actuales."]


def preparar_datos():
    scans = cargar_scans_historicos()
    candidatos = {
        strategy: reconstruir_candidatos_research(scans, strategy)
        for strategy in STRATEGIES
    }
    todos = [senal for filas in candidatos.values() for senal in filas]
    inicio = min(parsear_fecha(senal["market_date"]) for senal in todos)
    symbols = {senal["symbol"] for senal in todos} | {"SPY"}
    historicos, cache = obtener_historicos(symbols, inicio, date.today())
    resultados = {}
    cobertura = {}
    for strategy in STRATEGIES:
        for holding in HOLDINGS:
            evaluados, metadata = evaluar_candidatos_research(
                candidatos[strategy], historicos, holding
            )
            resultados[(strategy, holding)] = evaluados
            cobertura[(strategy, holding)] = metadata
    return resultados, historicos, cobertura, cache


def formato(valor, sufijo="%"):
    return f"{valor:+.2f}{sufijo}" if valor is not None else "N/A"


def imprimir_informe(filas, cobertura, cache):
    print("PORTFOLIO SENSITIVITY - RESEARCH / IN-SAMPLE")
    print("NO ES VALIDACION OUT-OF-SAMPLE")
    print("=" * 125)
    print("STRATEGY | HOLD | TOP | MAXPOS | TRADES | RET | SPY | EXC | MAXDD | WIN | EXP | SAMPLE")
    for fila in filas:
        print(
            f"{fila['strategy']:<9} | {fila['holding']:>2}D | {fila['top']:>3} | "
            f"{fila['max_positions']:>6} | {fila['trades']:>6} | "
            f"{formato(fila['retorno_pct']):>8} | {formato(fila['spy_retorno_pct']):>8} | "
            f"{formato(fila['exceso_spy_pp'], 'pp'):>9} | {formato(fila['max_drawdown_pct']):>8} | "
            f"{formato(fila['win_rate_pct']):>8} | {formato(fila['exposicion_media_pct']):>8} | "
            f"{fila['sample_quality']}"
        )

    print("\nRESUMEN DE ROBUSTEZ")
    print("-" * 125)
    for resumen in resumir_por_strategy_holding(filas):
        print(
            f"{resumen['strategy']} {resumen['holding']}D | escenarios {resumen['escenarios']} | "
            f"ret mediano {formato(resumen['retorno_mediano'])} | "
            f"exceso mediano {formato(resumen['exceso_mediano'], 'pp')} | "
            f"MaxDD mediano {formato(resumen['maxdd_mediano'])} | "
            f"exceso>0 {formato(resumen['pct_exceso_positivo'])} | "
            f"ret>0 {formato(resumen['pct_retorno_positivo'])} | {resumen['robustez']}"
        )

    for dimension, titulo in (("top", "ESTABILIDAD POR TOP"), ("max_positions", "ESTABILIDAD POR MAX POSITIONS")):
        print(f"\n{titulo}")
        print("-" * 125)
        for fila in resumir_estabilidad(filas, dimension):
            print(
                f"{fila['strategy']} {fila['holding']}D | {dimension}={fila[dimension]} | "
                f"ret {formato(fila['retorno_mediano'])} | "
                f"exceso {formato(fila['exceso_mediano'], 'pp')} | "
                f"MaxDD {formato(fila['maxdd_mediano'])}"
            )

    print("\nSEÑALES DE POSIBLE SOBREAJUSTE")
    print("-" * 125)
    for aviso in detectar_sobreajuste(filas):
        print(f"- {aviso}")

    print("\nCOBERTURA")
    for clave in sorted(cobertura):
        dato = cobertura[clave]
        print(
            f"{clave[0].upper()} {clave[1]}D: {dato['con_resultado_futuro']}/"
            f"{dato['senales_reconstruidas']} señales maduras"
        )
    print(
        f"Symbols cache hit: {cache['cache_hits']} | "
        f"Symbols descargados: {cache['symbols'] - cache['cache_hits']} | "
        f"Filas descargadas: {cache['filas_descargadas']}"
    )


def exportar_csv(filas, ruta=CSV_PATH):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CSV_COLUMNS)
        escritor.writeheader()
        escritor.writerows(filas)


def obtener_argumentos():
    parser = argparse.ArgumentParser(description="Sensibilidad de cartera research/in-sample.")
    parser.add_argument("--export-csv", action="store_true")
    return parser.parse_args()


def main():
    args = obtener_argumentos()
    resultados, historicos, cobertura, cache = preparar_datos()
    filas = generar_escenarios(resultados, historicos)
    imprimir_informe(filas, cobertura, cache)
    if args.export_csv:
        exportar_csv(filas)
        print(f"\nCSV guardado en: {CSV_PATH}")


if __name__ == "__main__":
    main()
