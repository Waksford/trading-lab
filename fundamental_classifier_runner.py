from analysis.fundamental_classifier import (
    clasificar_fundamental
)

from database.db import (
    inicializar_db,
    inicializar_tabla_fundamental_classification,
    obtener_fundamentales_sin_clasificar,
    guardar_clasificacion_fundamental
)


def main():

    print()

    print(
        "======================================"
    )

    print(
        "  FUNDAMENTAL CLASSIFIER RUNNER V1"
    )

    print(
        "======================================"
    )

    print()

    inicializar_db()

    inicializar_tabla_fundamental_classification()

    pendientes = (
        obtener_fundamentales_sin_clasificar()
    )

    print(
        f"Fundamentales pendientes: "
        f"{len(pendientes)}"
    )

    if not pendientes:

        print(
            "No hay fundamentales pendientes "
            "de clasificar."
        )

        return

    print()

    clasificados = 0
    errores = 0

    for posicion, fundamental in enumerate(
        pendientes,
        start=1
    ):

        symbol = fundamental[
            "symbol"
        ]

        print(
            f"[{posicion}/{len(pendientes)}] "
            f"{symbol}"
        )

        try:

            resultado = (
                clasificar_fundamental(
                    fundamental
                )
            )

            guardar_clasificacion_fundamental(
                fundamental[
                    "id"
                ],
                fundamental,
                resultado
            )

            clasificados += 1

            print(
                f"    Calidad: "
                f"{resultado['calidad_fundamental']}"
            )

            print(
                f"    Score fundamental: "
                f"{resultado['score_fundamental']}/100"
            )

            print(
                f"    Valoracion: "
                f"{resultado['valoracion']}"
            )

        except Exception as e:

            errores += 1

            print(
                f"    ERROR: {e}"
            )

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

    print()

    print(
        f"Pendientes:    "
        f"{len(pendientes)}"
    )

    print(
        f"Clasificados:  "
        f"{clasificados}"
    )

    print(
        f"Errores:       "
        f"{errores}"
    )


if __name__ == "__main__":

    main()