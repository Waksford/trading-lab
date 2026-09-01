import os
import subprocess
import sys

from datetime import (
    date,
    datetime,
    timedelta
)

from dotenv import load_dotenv

from alpaca.trading.client import (
    TradingClient
)

from alpaca.trading.requests import (
    GetCalendarRequest
)

from database.db import (
    obtener_conexion
)


# ============================================================
# CONFIGURACION
# ============================================================

MAX_DIAS_ATRAS = 30


# ============================================================
# CREDENCIALES / CALENDARIO
# ============================================================

load_dotenv()


API_KEY = os.getenv(
    "ALPACA_API_KEY"
)


SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY"
)


if not API_KEY or not SECRET_KEY:

    raise ValueError(
        "No se han cargado las claves "
        "de Alpaca desde .env"
    )


trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True
)


# ============================================================
# DB
# ============================================================

def obtener_market_dates_guardadas():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT DISTINCT market_date

        FROM scans

        WHERE market_date IS NOT NULL
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return {
        fila["market_date"]
        for fila in filas
        if fila["market_date"]
    }


# ============================================================
# CALENDARIO REAL DE MERCADO
# ============================================================

def obtener_sesiones_esperadas():
    """
    Consulta el calendario oficial de mercado de Alpaca
    para evitar tratar fines de semana o festivos como huecos.
    """

    hoy = date.today()

    inicio = (
        hoy
        - timedelta(
            days=MAX_DIAS_ATRAS
        )
    )

    # Solo buscamos sesiones COMPLETADAS anteriores a hoy.
    # La sesion de hoy la gestiona main.py normal.
    fin = (
        hoy
        - timedelta(
            days=1
        )
    )

    if fin < inicio:
        return []

    request = GetCalendarRequest(
        start=inicio,
        end=fin
    )

    calendario = (
        trading_client
        .get_calendar(
            request
        )
    )

    return sorted(
        sesion.date.isoformat()
        for sesion in calendario
    )


# ============================================================
# DETECTAR HUECOS
# ============================================================

def detectar_sesiones_faltantes():

    guardadas = (
        obtener_market_dates_guardadas()
    )

    esperadas = (
        obtener_sesiones_esperadas()
    )

    return [
        market_date
        for market_date in esperadas
        if market_date not in guardadas
    ]


# ============================================================
# EJECUTAR BACKFILL
# ============================================================

def ejecutar_backfill_fecha(
    market_date
):

    print()

    print(
        "======================================"
    )

    print(
        f"BACKFILL {market_date}"
    )

    print(
        "======================================"
    )

    resultado = subprocess.run(
        [
            sys.executable,
            "main.py",
            "--market-date",
            market_date
        ]
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            (
                f"main.py fallo reconstruyendo "
                f"{market_date}. "
                f"Exit code: "
                f"{resultado.returncode}"
            )
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "======================================"
    )

    print(
        "     CHECK MISSING MARKET DAYS"
    )

    print(
        "======================================"
    )

    faltantes = (
        detectar_sesiones_faltantes()
    )

    if not faltantes:

        print()
        print(
            "No hay sesiones faltantes."
        )

        return

    print()

    print(
        f"Sesiones faltantes: "
        f"{len(faltantes)}"
    )

    for market_date in faltantes:

        print(
            f"  - {market_date}"
        )

    reconstruidas = 0
    errores = 0

    for market_date in faltantes:

        try:

            ejecutar_backfill_fecha(
                market_date
            )

            reconstruidas += 1

        except Exception as exc:

            errores += 1

            print(
                f"ERROR {market_date}: "
                f"{exc}"
            )

            # Se detiene para preservar el orden
            # y no ocultar un hueco intermedio.
            break

    print()

    print(
        "======================================"
    )

    print(
        "              RESUMEN"
    )

    print(
        "======================================"
    )

    print(
        f"Detectadas:     "
        f"{len(faltantes)}"
    )

    print(
        f"Reconstruidas:  "
        f"{reconstruidas}"
    )

    print(
        f"Errores:        "
        f"{errores}"
    )


if __name__ == "__main__":
    main()