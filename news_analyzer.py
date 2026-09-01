import time

from database.db import (

    inicializar_db,

    asegurar_columna_market_date,

    asegurar_columnas_sectoriales,

    asegurar_columnas_score_v3,

    asegurar_columnas_clasificacion,

    inicializar_tablas_news,

    obtener_candidatos_news_pendientes,

    guardar_news_context
)

from analysis.news_context import (
    analizar_contexto_noticias
)


# ============================================================
# CONFIGURACION
# ============================================================

SCORE_VERSION = "v3"


PRIORIDADES = (
    "A+",
    "A"
)


# Pequena pausa entre peticiones.

PAUSA_API = 0.20


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "======================================"
    )

    print(
        "        NEWS ANALYZER V1"
    )

    print(
        "======================================"
    )

    print()


    # ========================================================
    # DB
    # ========================================================

    inicializar_db()

    asegurar_columna_market_date()

    asegurar_columnas_sectoriales()

    asegurar_columnas_score_v3()

    asegurar_columnas_clasificacion()

    inicializar_tablas_news()


    # ========================================================
    # PENDIENTES
    # ========================================================

    candidatos = (
        obtener_candidatos_news_pendientes(
            score_version=SCORE_VERSION,
            prioridades=PRIORIDADES
        )
    )


    print(
        f"Candidatos pendientes: "
        f"{len(candidatos)}"
    )


    if not candidatos:

        print(
            "No hay candidatos nuevos "
            "para analizar."
        )

        return


    print()


    guardados = 0

    errores = 0


    # ========================================================
    # ANALISIS
    # ========================================================

    total = len(
        candidatos
    )


    for posicion, candidato in enumerate(
        candidatos,
        start=1
    ):

        symbol = candidato[
            "symbol"
        ]

        prioridad = candidato[
            "prioridad_estudio"
        ]


        print(
            f"[{posicion}/{total}] "
            f"{symbol} "
            f"Prioridad {prioridad}"
        )


        try:

            resultado = (
                analizar_contexto_noticias(

                    symbol,

                    prioridad_tecnica=
                        prioridad
                )
            )


            guardar_news_context(

                candidato,

                resultado
            )


            guardados += 1


            print(
                f"    Contexto: "
                f"{resultado['contexto']}"
            )


            print(
                f"    Movimiento: "
                f"{resultado['movimiento_explicado']}"
            )


            print(
                f"    Catalizador: "
                f"{resultado['fuerza_catalizador']}"
            )


            print(
                f"    Riesgo narrativo: "
                f"{resultado['riesgo_narrativo']}"
            )


            print(
                f"    Noticias: "
                f"{resultado['num_noticias']}"
            )


        except Exception as e:

            errores += 1

            print(
                f"    ERROR: {e}"
            )


        time.sleep(
            PAUSA_API
        )


    # ========================================================
    # RESUMEN
    # ========================================================

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
        f"Analizados: "
        f"{total}"
    )


    print(
        f"Guardados:  "
        f"{guardados}"
    )


    print(
        f"Errores:    "
        f"{errores}"
    )


if __name__ == "__main__":

    main()