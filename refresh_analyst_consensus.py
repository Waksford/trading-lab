import sys
from datetime import datetime

from database.db import (
    guardar_analyst_snapshot,
    inicializar_db,
    inicializar_tabla_analyst_consensus,
    obtener_ultimo_scan,
    obtener_ultimo_tecnico,
    obtener_ultimos_analyst_snapshots,
)
from providers.yahoo_analyst import (
    normalizar_symbol,
    obtener_consenso_analistas,
)


def obtener_candidatos_actuales():
    candidatos = set()

    for activo in obtener_ultimo_scan():
        if activo.get("score_version") != "v4":
            continue

        momentum = activo.get(
            "prioridad_estudio"
        ) in (
            "A+",
            "A",
            "B",
        )

        reversal = (
            activo.get("reversal_candidate") == 1
            and activo.get("reversal_version")
            == "reversal_v1"
            and activo.get("reversal_priority") == "A"
        )

        if momentum or reversal:
            candidatos.add(
                normalizar_symbol(
                    activo.get("symbol")
                )
            )

    candidatos.discard("")

    return sorted(
        candidatos
    )


def obtener_symbols_cli():
    symbols = {
        normalizar_symbol(symbol)
        for symbol in sys.argv[1:]
        if normalizar_symbol(symbol)
    }

    return sorted(
        symbols
    )


def actualizar_analyst_consensus(
    symbols=None,
    skip_existing_today=True,
    snapshot_date=None,
    provider_func=obtener_consenso_analistas,
):
    inicializar_tabla_analyst_consensus()

    symbols = sorted(
        {
            normalizar_symbol(symbol)
            for symbol in (
                symbols
                if symbols is not None
                else obtener_candidatos_actuales()
            )
            if normalizar_symbol(symbol)
        }
    )
    snapshot_date = (
        snapshot_date
        or datetime.now().date().isoformat()
    )

    actualizados_hoy = set()

    if skip_existing_today:
        actualizados_hoy = {
            fila["symbol"]
            for fila in obtener_ultimos_analyst_snapshots()
            if (
                fila.get("source") == "YAHOO"
                and fila.get("snapshot_date") == snapshot_date
            )
        }

    pendientes = [
        symbol
        for symbol in symbols
        if symbol not in actualizados_hoy
    ]

    resumen = {
        "candidatos": len(symbols),
        "actualizados_hoy": (
            len(symbols) - len(pendientes)
        ),
        "pendientes": len(pendientes),
        "consultados": 0,
        "guardados": 0,
        "sin_datos": 0,
        "errores": 0,
    }

    print()
    print("======================================")
    print("      YAHOO ANALYST CONSENSUS")
    print("======================================")

    if not pendientes:
        print(
            "Yahoo Analyst Consensus: "
            f"{resumen['actualizados_hoy']}/"
            f"{resumen['candidatos']} ya actualizados hoy."
        )
        print("No se realizaron consultas.")
        return resumen

    for symbol in pendientes:
        resumen["consultados"] += 1

        try:
            tecnico = obtener_ultimo_tecnico(
                symbol
            )
            price_internal = (
                tecnico.get("precio")
                if tecnico
                else None
            )

            snapshot = provider_func(
                symbol,
                price_internal=price_internal,
            )

            if snapshot is None:
                resumen["sin_datos"] += 1
                continue

            resumen["guardados"] += (
                guardar_analyst_snapshot(
                    snapshot
                )
            )

        except Exception as exc:
            resumen["errores"] += 1
            print(
                f"{symbol:<8} ERROR: {exc}"
            )

    print()
    print(
        f"Candidatos radar:      {resumen['candidatos']:>5}"
    )
    print(
        f"Ya actualizados hoy:   {resumen['actualizados_hoy']:>5}"
    )
    print(
        f"Pendientes Yahoo:      {resumen['pendientes']:>5}"
    )
    print(
        f"Consultados:           {resumen['consultados']:>5}"
    )
    print(
        f"Guardados:             {resumen['guardados']:>5}"
    )
    print(
        f"Sin datos:             {resumen['sin_datos']:>5}"
    )
    print(
        f"Errores:               {resumen['errores']:>5}"
    )

    return resumen


def main():
    inicializar_db()

    manuales = obtener_symbols_cli()

    actualizar_analyst_consensus(
        symbols=(
            manuales
            if manuales
            else None
        )
    )


if __name__ == "__main__":
    main()
