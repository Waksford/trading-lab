from database.db import (
    obtener_ultimo_fundamental
)

from analysis.fundamental_classifier import (
    clasificar_fundamental
)


TICKERS = [
    "SENEA",
    "CBNA",
    "PCYO",
    "SNOW"
]


for symbol in TICKERS:

    print()

    print(
        "=" * 70
    )

    print(
        f"       {symbol}"
    )

    print(
        "=" * 70
    )

    print()


    fundamental = obtener_ultimo_fundamental(
        symbol
    )


    if fundamental is None:

        print(
            "No existe fundamental guardado."
        )

        continue


    resultado = clasificar_fundamental(
        fundamental
    )


    print(
        f"Modelo:              "
        f"{resultado['model']}"
    )


    print(
        f"Score fundamental:   "
        f"{resultado['score_fundamental']}"
    )


    print(
        f"Calidad:             "
        f"{resultado['calidad_fundamental']}"
    )


    print(
        f"Crecimiento:         "
        f"{resultado['crecimiento']}"
    )


    print(
        f"Rentabilidad:        "
        f"{resultado['rentabilidad']}"
    )


    print(
        f"Balance:             "
        f"{resultado['balance']}"
    )


    print(
        f"Cash Flow:           "
        f"{resultado['cash_flow']}"
    )


    print(
        f"Valoracion:          "
        f"{resultado['valoracion']}"
    )


    print()

    print(
        "FORTALEZAS"
    )


    if resultado[
        "fortalezas"
    ]:

        for fortaleza in resultado[
            "fortalezas"
        ]:

            print(
                f"  + {fortaleza}"
            )

    else:

        print(
            "  Ninguna destacada."
        )


    print()

    print(
        "DEBILIDADES"
    )


    if resultado[
        "debilidades"
    ]:

        for debilidad in resultado[
            "debilidades"
        ]:

            print(
                f"  - {debilidad}"
            )

    else:

        print(
            "  Ninguna destacada."
        )


    print()

    print(
        "ALERTAS"
    )


    if resultado[
        "alertas"
    ]:

        for alerta in resultado[
            "alertas"
        ]:

            print(
                f"  ! {alerta}"
            )

    else:

        print(
            "  Ninguna."
        )


    print()

    print(
        "LECTURA"
    )

    print(
        resultado[
            "lectura"
        ]
    )