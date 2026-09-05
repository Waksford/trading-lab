"""Single daily orchestrator for all paper portfolios.

It owns data acquisition and failure isolation, while strategy engines retain
their existing selection, trading and valuation rules.
"""

from datetime import datetime, timedelta

from database.db import (
    ETF_FORWARD_START_DATE,
    PAPER_PORTFOLIO_START_DATE,
    inicializar_tablas_paper,
    inicializar_tablas_paper_portfolio,
    obtener_conexion,
    obtener_resumen_paper_portfolios,
)
from paper_etf_forward import procesar_carteras_etf_forward
from paper_portfolio_config import ALL_PAPER_PORTFOLIOS, STOCK_PORTFOLIOS
from paper_portfolio_live import procesar_paper_portfolios
from research.etf_rotation_analysis import REPRESENTATIVES


def ejecutar_motores(historicos, fecha_hasta=None):
    """Attempt every portfolio independently using one prepared dataset."""
    estados = {}
    for nombre in STOCK_PORTFOLIOS:
        try:
            procesar_paper_portfolios(
                historicos,
                fecha_hasta=fecha_hasta,
                nombres={nombre},
                incluir_forward=False,
            )
            estados[nombre] = {"ok": True, "error": None}
        except Exception as exc:
            estados[nombre] = {"ok": False, "error": str(exc)}

    try:
        estados.update(procesar_carteras_etf_forward(historicos, fecha_hasta))
    except Exception as exc:
        # Dataset/schema-wide failures happen before the engine can isolate rows.
        for nombre in ALL_PAPER_PORTFOLIOS:
            if nombre not in estados:
                estados[nombre] = {"ok": False, "error": str(exc)}
    return estados


def generar_resumen_estados(estados, carteras):
    por_nombre = {cartera["name"]: cartera for cartera in carteras}
    lineas = ["", "PAPER PORTFOLIOS", "-" * 64]
    for nombre in ALL_PAPER_PORTFOLIOS:
        estado = estados.get(nombre, {"ok": False, "error": "no ejecutada"})
        cartera = por_nombre.get(nombre, {})
        equity = (cartera.get("equity") or {}).get(
            "equity", cartera.get("current_cash", 0.0)
        )
        resultado = "OK" if estado["ok"] else f"ERROR: {estado['error']}"
        lineas.append(f"{nombre:<22} equity=${float(equity):>10,.2f}  {resultado}")
    return lineas


def descargar_dataset_compartido():
    """Download every required symbol once for the whole portfolio layer."""
    conexion = obtener_conexion()
    symbols = {
        fila["symbol"]
        for fila in conexion.execute(
            """SELECT DISTINCT symbol FROM paper_signals
               WHERE market_date >= ? AND variant = 'BASE'""",
            (PAPER_PORTFOLIO_START_DATE,),
        ).fetchall()
    }
    conexion.close()
    symbols.update(item.symbol for item in REPRESENTATIVES)

    from paper_simulator import descargar_historico, preparar_historicos

    descargado = descargar_historico(
        symbols,
        datetime.strptime(ETF_FORWARD_START_DATE, "%Y-%m-%d") - timedelta(days=400),
        datetime.now() + timedelta(days=1),
    )
    if descargado.empty:
        raise RuntimeError("No se ha obtenido historico para paper portfolios")
    return preparar_historicos(descargado)


def main():
    inicializar_tablas_paper()
    inicializar_tablas_paper_portfolio()
    historicos = descargar_dataset_compartido()
    estados = ejecutar_motores(historicos)
    carteras = obtener_resumen_paper_portfolios()
    print("\n".join(generar_resumen_estados(estados, carteras)))
    return 0 if all(e.get("ok") for e in estados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
