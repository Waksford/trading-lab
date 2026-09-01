from analysis.news_context import (
    analizar_contexto_noticias
)


TICKERS = [

    (
        "SENEA",
        "A+"
    ),

    (
        "CBNA",
        "A+"
    ),

    (
        "AGYS",
        "B"
    ),

    (
        "PCYO",
        "A"
    )
]


for symbol, prioridad in TICKERS:

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


    try:

        resultado = (
            analizar_contexto_noticias(

                symbol,

                prioridad_tecnica=
                    prioridad
            )
        )


        print(
            f"Prioridad técnica: "
            f"{prioridad}"
        )


        print(
            f"Noticias encontradas: "
            f"{resultado['num_noticias']}"
        )


        print(
            f"Contexto: "
            f"{resultado['contexto']}"
        )


        print(
            f"Movimiento explicado: "
            f"{resultado['movimiento_explicado']}"
        )


        print(
            f"Fuerza catalizador: "
            f"{resultado['fuerza_catalizador']}"
        )


        print(
            f"Riesgo narrativo: "
            f"{resultado['riesgo_narrativo']}"
        )


        # ====================================================
        # CATALIZADORES
        # ====================================================

        print()

        print(
            "Catalizadores:"
        )


        if resultado[
            "catalizadores"
        ]:

            for catalizador in (
                resultado[
                    "catalizadores"
                ]
            ):

                print(
                    f"  * {catalizador}"
                )

        else:

            print(
                "  Ninguno identificado."
            )


        # ====================================================
        # EVIDENCIAS POSITIVAS
        # ====================================================

        print()

        print(
            "Evidencias positivas:"
        )


        if resultado[
            "evidencias_positivas"
        ]:

            for evidencia in (
                resultado[
                    "evidencias_positivas"
                ]
            ):

                print(
                    f"  + {evidencia}"
                )

        else:

            print(
                "  Ninguna identificada."
            )


        # ====================================================
        # EVIDENCIAS NEGATIVAS
        # ====================================================

        print()

        print(
            "Evidencias negativas:"
        )


        if resultado[
            "evidencias_negativas"
        ]:

            for evidencia in (
                resultado[
                    "evidencias_negativas"
                ]
            ):

                print(
                    f"  - {evidencia}"
                )

        else:

            print(
                "  Ninguna identificada."
            )


        # ====================================================
        # RIESGOS
        # ====================================================

        print()

        print(
            "Riesgos:"
        )


        if resultado[
            "riesgos"
        ]:

            for riesgo in (
                resultado[
                    "riesgos"
                ]
            ):

                print(
                    f"  ! {riesgo}"
                )

        else:

            print(
                "  Ninguno identificado."
            )


        # ====================================================
        # LECTURA
        # ====================================================

        print()

        print(
            "Lectura:"
        )


        print(
            resultado[
                "lectura"
            ]
        )


        # ====================================================
        # NOTICIAS
        # ====================================================

        print()

        print(
            "Noticias recientes:"
        )


        if not resultado[
            "noticias"
        ]:

            print(
                "  Sin noticias."
            )


        for noticia in (
            resultado[
                "noticias"
            ][:5]
        ):

            print()

            print(
                f"- {noticia['headline']}"
            )

            print(
                f"  Fecha: "
                f"{noticia['created_at']}"
            )

            print(
                f"  Contexto noticia: "
                f"{noticia['contexto']}"
            )


            if noticia[
                "evidencias_positivas"
            ]:

                print(
                    "  Positivas: "
                    + ", ".join(
                        noticia[
                            "evidencias_positivas"
                        ]
                    )
                )


            if noticia[
                "evidencias_negativas"
            ]:

                print(
                    "  Negativas: "
                    + ", ".join(
                        noticia[
                            "evidencias_negativas"
                        ]
                    )
                )


    except Exception as e:

        print(
            f"ERROR: {e}"
        )