from database.db import (
    obtener_ultimo_tecnico,
    obtener_ultima_clasificacion_fundamental,
    obtener_ultimo_news_context
)

from analysis.thesis_engine import (
    construir_tesis
)


SIMBOLOS = [
    "SENEA",
    "CBNA",
    "PCYO",
    "SNOW"
]


def imprimir_lista(
    titulo,
    elementos,
    prefijo
):

    print()
    print(titulo)

    if not elementos:
        print("  Ninguna.")
        return

    for elemento in elementos:
        print(
            f"  {prefijo} {elemento}"
        )


for symbol in SIMBOLOS:

    print()
    print("=" * 70)
    print(
        f"       {symbol}"
    )
    print("=" * 70)

    tecnico = obtener_ultimo_tecnico(
        symbol
    )

    if tecnico is None:
        print()
        print(
            "Sin datos tecnicos."
        )
        continue

    fundamental = (
        obtener_ultima_clasificacion_fundamental(
            symbol
        )
    )

    news = obtener_ultimo_news_context(
        symbol
    )

    resultado = construir_tesis(
        tecnico=tecnico,
        fundamental=fundamental,
        news=news
    )

    print()
    print(
        f"Tesis:               "
        f"{resultado['tesis']}"
    )

    print(
        f"Confianza:           "
        f"{resultado['confianza']}"
    )

    print()

    print(
        f"Prioridad tecnica:   "
        f"{resultado['prioridad_tecnica']}"
    )

    print(
        f"Score tecnico:       "
        f"{resultado['score_tecnico']}"
    )

    print(
        f"Score fundamental:   "
        f"{resultado['score_fundamental']}"
    )

    print(
        f"Contexto noticias:   "
        f"{resultado['contexto_noticias']}"
    )

    print()

    print(
        f"Puntos tecnico:      "
        f"{resultado['puntos_tecnicos']}"
    )

    print(
        f"Puntos fundamental:  "
        f"{resultado['puntos_fundamentales']}"
    )

    print(
        f"Puntos noticias:     "
        f"{resultado['puntos_noticias']}"
    )

    imprimir_lista(
        "EVIDENCIAS A FAVOR",
        resultado["evidencias"],
        "+"
    )

    imprimir_lista(
        "RIESGOS / CONTRA",
        resultado["riesgos"],
        "!"
    )

    print()
    print("LECTURA")
    print(
        resultado["lectura"]
    )