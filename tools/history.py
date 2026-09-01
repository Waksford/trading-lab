import sys

from database.db import (
    obtener_historial_symbol,
    obtener_ultimo_scan,
    obtener_eventos_recientes,
    obtener_scan_times,
    obtener_scan_por_fecha
)


def mostrar_symbol(
    symbol
):

    historial = obtener_historial_symbol(
        symbol,
        limite=30
    )

    if not historial:

        print(
            f"No hay histórico para {symbol}."
        )

        return


    primero = historial[0]

    print()
    print(
        f"{symbol.upper()} - "
        f"{primero.get('nombre', '')}"
    )

    print(
        "=" * 85
    )

    print(
        f"{'FECHA':19} "
        f"{'PRECIO':>10} "
        f"{'SCORE':>7} "
        f"{'RSI':>7} "
        f"{'RS20':>9} "
        f"{'RS60':>9}"
    )

    print(
        "-" * 85
    )


    for fila in historial:

        print(
            f"{fila['scan_time'][:19]:19} "
            f"${fila['precio']:>9.2f} "
            f"{fila['score']:>6}/100 "
            f"{fila['rsi']:>6.1f} "
            f"{fila['fuerza_20d']:>+8.1f} "
            f"{fila['fuerza_60d']:>+8.1f}"
        )


def mostrar_top():

    scan = obtener_ultimo_scan()

    print()
    print(
        "TOP 20 ÚLTIMO SCAN"
    )
    print(
        "=" * 80
    )


    for posicion, activo in enumerate(
        scan[:20],
        start=1
    ):

        print(
            f"{posicion:>2}. "
            f"{activo['symbol']:<7} "
            f"{activo['score']:>3}/100 "
            f"RS20 "
            f"{activo['fuerza_20d']:+6.1f} "
            f"RS60 "
            f"{activo['fuerza_60d']:+6.1f}"
        )


def mostrar_eventos():

    eventos = obtener_eventos_recientes(
        50
    )

    print()
    print(
        "EVENTOS RECIENTES"
    )
    print(
        "=" * 90
    )


    for evento in eventos:

        print(
            f"{evento['event_time'][:19]} | "
            f"{evento['tipo']:<18} | "
            f"{evento['mensaje']}"
        )


def mostrar_persistentes():

    scan_times = obtener_scan_times(
        limite=10
    )

    if not scan_times:

        print(
            "No hay scans guardados."
        )

        return


    apariciones = {}


    for scan_time in scan_times:

        scan = obtener_scan_por_fecha(
            scan_time
        )

        top20 = scan[:20]


        for activo in top20:

            symbol = activo["symbol"]

            apariciones[symbol] = (
                apariciones.get(
                    symbol,
                    0
                )
                + 1
            )


    ranking = sorted(
        apariciones.items(),
        key=lambda x: x[1],
        reverse=True
    )


    print()
    print(
        f"PERSISTENCIA TOP 20 "
        f"ÚLTIMOS {len(scan_times)} SCANS"
    )

    print(
        "=" * 60
    )


    for symbol, cantidad in ranking[:20]:

        print(
            f"{symbol:<8} "
            f"{cantidad}/{len(scan_times)} scans"
        )


def main():

    if len(sys.argv) < 2:

        print(
            "Uso:"
        )

        print(
            "  python history.py JLL"
        )

        print(
            "  python history.py top"
        )

        print(
            "  python history.py eventos"
        )

        print(
            "  python history.py persistentes"
        )

        return


    comando = (
        sys.argv[1]
        .upper()
    )


    if comando == "TOP":

        mostrar_top()

    elif comando == "EVENTOS":

        mostrar_eventos()

    elif comando == "PERSISTENTES":

        mostrar_persistentes()

    else:

        mostrar_symbol(
            comando
        )


if __name__ == "__main__":
    main()