import numpy as np
import pandas as pd

from research.paper_analysis import (
    cargar_dataset,
    crear_buckets,
    crear_configuraciones,
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTE = 5

MIN_CASOS_BLOQUE = 5


# ============================================================
# PATRONES A VALIDAR
# ============================================================

PATRONES = {

    # --------------------------------------------------------
    # BASELINES
    # --------------------------------------------------------

    "A+ GLOBAL": lambda df: (
        df["prioridad"] == "A+"
    ),

    "A GLOBAL": lambda df: (
        df["prioridad"] == "A"
    ),

    "B GLOBAL": lambda df: (
        df["prioridad"] == "B"
    ),


    # --------------------------------------------------------
    # PATRONES ROBUSTOS ENCONTRADOS
    # --------------------------------------------------------

    "B + RSI 65-70 + SMA20 10-15%":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df["bucket_rsi"]
                .astype(str)
                == "65-70"
            )

            &

            (
                df["bucket_sma20"]
                .astype(str)
                == "10-15%"
            )
        ),


    "B + RIESGO MUY ALTO":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df[
                    "riesgo_clasificacion"
                ]
                == "MUY ALTO"
            )
        ),


    "B + SMA20 10-15%":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df[
                    "bucket_sma20"
                ]
                .astype(str)
                == "10-15%"
            )
        ),


    "B + VOLUMEN MUY ALTO":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df[
                    "volumen_clasificacion"
                ]
                == "MUY ALTO"
            )
        ),


    "B + RSI 60-65":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df[
                    "bucket_rsi"
                ]
                .astype(str)
                == "60-65"
            )
        ),


    # --------------------------------------------------------
    # CONFIGURACION MUY ESPECIFICA
    # --------------------------------------------------------

    "B + RSI60-65 + SMA6-10 + RIESGO MUY ALTO + VOL ALTO":
        lambda df: (

            (df["prioridad"] == "B")

            &

            (
                df["bucket_rsi"]
                .astype(str)
                == "60-65"
            )

            &

            (
                df["bucket_sma20"]
                .astype(str)
                == "6-10%"
            )

            &

            (
                df["riesgo_clasificacion"]
                == "MUY ALTO"
            )

            &

            (
                df["volumen_clasificacion"]
                == "ALTO"
            )
        ),
}


# ============================================================
# HELPERS
# ============================================================

def porcentaje_positivo(
    serie
):

    serie = serie.dropna()

    if serie.empty:
        return 0.0

    return (
        (serie > 0).mean()
        * 100
    )


def trimmed_mean(
    serie,
    pct=0.05
):

    serie = (
        serie
        .dropna()
        .sort_values()
    )

    n = len(
        serie
    )

    if n == 0:
        return None

    corte = int(
        n * pct
    )

    if (
        corte == 0
        or
        corte * 2 >= n
    ):

        return serie.mean()

    return (
        serie.iloc[
            corte:
            n - corte
        ]
        .mean()
    )


# ============================================================
# RESUMEN DE UN PERIODO
# ============================================================

def resumir_periodo(
    datos
):

    if datos.empty:

        return None


    sesiones = (

        datos
        .groupby(
            "market_date",
            observed=True
        )
        .agg(

            casos=(
                "symbol",
                "size"
            ),

            retorno=(
                "retorno",
                "mean"
            ),

            exceso=(
                "exceso_spy",
                "mean"
            )
        )
        .reset_index()
    )


    return {

        "casos":
            len(
                datos
            ),

        "simbolos":
            datos[
                "symbol"
            ].nunique(),

        "sesiones":
            datos[
                "market_date"
            ].nunique(),

        "retorno_medio":
            datos[
                "retorno"
            ].mean(),

        "retorno_mediana":
            datos[
                "retorno"
            ].median(),

        "exceso_medio":
            datos[
                "exceso_spy"
            ].mean(),

        "exceso_mediana":
            datos[
                "exceso_spy"
            ].median(),

        "retorno_trimmed":
            trimmed_mean(
                datos[
                    "retorno"
                ]
            ),

        "exceso_trimmed":
            trimmed_mean(
                datos[
                    "exceso_spy"
                ]
            ),

        "beat_spy":
            porcentaje_positivo(
                datos[
                    "exceso_spy"
                ]
            ),

        "positivos":
            porcentaje_positivo(
                datos[
                    "retorno"
                ]
            ),

        "dias_beat":
            porcentaje_positivo(
                sesiones[
                    "exceso"
                ]
            ),

        "dias_positivos":
            porcentaje_positivo(
                sesiones[
                    "retorno"
                ]
            ),

        "mediana_exceso_dia":
            sesiones[
                "exceso"
            ].median(),

        "mediana_retorno_dia":
            sesiones[
                "retorno"
            ].median(),

        "drawdown":
            datos[
                "max_drawdown"
            ].mean(),
    }


# ============================================================
# CREAR BLOQUES TEMPORALES
# ============================================================

def crear_bloques_temporales(
    df
):
    """
    Divide las fechas cronologicamente
    en tres grupos de tamaño parecido.

    NO mezcla fechas aleatoriamente.
    """

    fechas = sorted(
        df[
            "market_date"
        ]
        .dropna()
        .unique()
    )

    bloques_np = np.array_split(
        fechas,
        3
    )

    bloques = []

    for numero, fechas_bloque in enumerate(
        bloques_np,
        start=1
    ):

        fechas_bloque = list(
            fechas_bloque
        )

        if not fechas_bloque:
            continue

        bloques.append(
            {
                "nombre":
                    f"BLOQUE {numero}",

                "fechas":
                    fechas_bloque,

                "inicio":
                    fechas_bloque[0],

                "fin":
                    fechas_bloque[-1],
            }
        )

    return bloques


# ============================================================
# IMPRIMIR RESUMEN
# ============================================================

def imprimir_resumen(
    titulo,
    r
):

    if r is None:

        print(
            f"{titulo:<18} | SIN DATOS"
        )

        return


    print(
        f"{titulo:<18} | "
        f"n={r['casos']:>4} | "
        f"sym={r['simbolos']:>3} | "
        f"dias={r['sesiones']:>2} | "
        f"Ret={r['retorno_medio']:+6.2f}% | "
        f"Med={r['retorno_mediana']:+6.2f}% | "
        f"Exc={r['exceso_medio']:+6.2f}pp | "
        f"ExcTrim={r['exceso_trimmed']:+6.2f}pp | "
        f"DiasBeat={r['dias_beat']:>5.1f}%"
    )


# ============================================================
# VALIDACION DE ESTABILIDAD
# ============================================================

def evaluar_estabilidad(
    resultados_bloques
):

    validos = [
        r
        for r in resultados_bloques
        if (
            r is not None
            and
            r[
                "casos"
            ] >= MIN_CASOS_BLOQUE
        )
    ]


    if len(
        validos
    ) < 2:

        return {
            "score": 0,
            "clasificacion":
                "MUESTRA INSUFICIENTE",
            "bloques_positivos": 0,
            "bloques": len(
                validos
            ),
        }


    score = 0


    # ========================================================
    # 1. EXCESO POSITIVO POR BLOQUE
    # max 30
    # ========================================================

    bloques_exceso = sum(

        1

        for r in validos

        if r[
            "exceso_trimmed"
        ] > 0
    )


    score += (
        bloques_exceso
        /
        len(
            validos
        )
        * 30
    )


    # ========================================================
    # 2. MEDIANA DIARIA POSITIVA
    # max 20
    # ========================================================

    bloques_mediana = sum(

        1

        for r in validos

        if r[
            "mediana_exceso_dia"
        ] > 0
    )


    score += (
        bloques_mediana
        /
        len(
            validos
        )
        * 20
    )


    # ========================================================
    # 3. BATE SPY EN MAYORIA DE DIAS
    # max 20
    # ========================================================

    bloques_dias = sum(

        1

        for r in validos

        if r[
            "dias_beat"
        ] >= 50
    )


    score += (
        bloques_dias
        /
        len(
            validos
        )
        * 20
    )


    # ========================================================
    # 4. ULTIMO BLOQUE
    # max 15
    # ========================================================

    ultimo = validos[
        -1
    ]


    if ultimo[
        "exceso_trimmed"
    ] > 1:

        score += 15

    elif ultimo[
        "exceso_trimmed"
    ] > 0:

        score += 10


    # ========================================================
    # 5. NO DEPENDE DE UN SOLO BLOQUE
    # max 15
    # ========================================================

    excesos = [
        r[
            "exceso_trimmed"
        ]
        for r in validos
    ]


    positivos = [
        x
        for x in excesos
        if x > 0
    ]


    if (
        len(
            positivos
        ) >= 2
    ):

        score += 15


    score = round(
        score
    )


    if (
        score >= 80
        and
        bloques_exceso
        ==
        len(
            validos
        )
    ):

        clasificacion = (
            "VALIDADO PRELIMINAR"
        )

    elif score >= 65:

        clasificacion = (
            "ESTABLE / PROMETEDOR"
        )

    elif score >= 45:

        clasificacion = (
            "MIXTO"
        )

    else:

        clasificacion = (
            "INESTABLE"
        )


    return {

        "score":
            score,

        "clasificacion":
            clasificacion,

        "bloques_positivos":
            bloques_exceso,

        "bloques":
            len(
                validos
            ),
    }


# ============================================================
# EXCLUIR MEJOR / PEOR FECHA
# ============================================================

def prueba_sin_fecha_extrema(
    datos
):
    """
    Comprueba si el resultado desaparece al quitar
    la mejor sesión y la peor sesión.
    """

    por_dia = (

        datos
        .groupby(
            "market_date"
        )[
            "exceso_spy"
        ]
        .mean()
        .sort_values()
    )


    if len(
        por_dia
    ) < 3:

        return None


    peor_fecha = (
        por_dia.index[
            0
        ]
    )

    mejor_fecha = (
        por_dia.index[
            -1
        ]
    )


    sin_mejor = datos[
        datos[
            "market_date"
        ]
        != mejor_fecha
    ]


    sin_peor = datos[
        datos[
            "market_date"
        ]
        != peor_fecha
    ]


    return {

        "mejor_fecha":
            mejor_fecha,

        "mejor_exceso":
            por_dia.iloc[
                -1
            ],

        "peor_fecha":
            peor_fecha,

        "peor_exceso":
            por_dia.iloc[
                0
            ],

        "sin_mejor":
            resumir_periodo(
                sin_mejor
            ),

        "sin_peor":
            resumir_periodo(
                sin_peor
            ),
    }


# ============================================================
# VALIDAR PATRON
# ============================================================

def validar_patron(
    nombre,
    datos,
    bloques
):

    print()

    print(
        "=" * 120
    )

    print(
        nombre
    )

    print(
        "=" * 120
    )


    global_result = resumir_periodo(
        datos
    )


    if global_result is None:

        print(
            "Sin datos."
        )

        return None


    imprimir_resumen(
        "GLOBAL",
        global_result
    )


    print()

    print(
        "EVOLUCION TEMPORAL"
    )

    print(
        "-" * 120
    )


    resultados_bloques = []


    for bloque in bloques:


        datos_bloque = datos[
            datos[
                "market_date"
            ].isin(
                bloque[
                    "fechas"
                ]
            )
        ]


        resumen = resumir_periodo(
            datos_bloque
        )


        resultados_bloques.append(
            resumen
        )


        etiqueta = (
            f"{bloque['nombre']} "
            f"{bloque['inicio']} "
            f"a {bloque['fin']}"
        )


        imprimir_resumen(
            etiqueta,
            resumen
        )


    # ========================================================
    # ESTABILIDAD
    # ========================================================

    estabilidad = evaluar_estabilidad(
        resultados_bloques
    )


    print()

    print(
        "ESTABILIDAD"
    )

    print(
        "-" * 120
    )


    print(
        f"Bloques con exceso trimmed positivo: "
        f"{estabilidad['bloques_positivos']}/"
        f"{estabilidad['bloques']}"
    )


    print(
        f"Score estabilidad temporal:          "
        f"{estabilidad['score']}/100"
    )


    print(
        f"Clasificacion:                       "
        f"{estabilidad['clasificacion']}"
    )


    # ========================================================
    # QUITAR FECHAS EXTREMAS
    # ========================================================

    extremos = prueba_sin_fecha_extrema(
        datos
    )


    if extremos:

        print()

        print(
            "PRUEBA DE DEPENDENCIA DE FECHA"
        )

        print(
            "-" * 120
        )


        print(
            f"Mejor fecha: "
            f"{extremos['mejor_fecha']} "
            f"({extremos['mejor_exceso']:+.2f}pp)"
        )


        print(
            f"Peor fecha:  "
            f"{extremos['peor_fecha']} "
            f"({extremos['peor_exceso']:+.2f}pp)"
        )


        print()


        imprimir_resumen(
            "SIN MEJOR FECHA",
            extremos[
                "sin_mejor"
            ]
        )


        imprimir_resumen(
            "SIN PEOR FECHA",
            extremos[
                "sin_peor"
            ]
        )


    return {

        "nombre":
            nombre,

        "global":
            global_result,

        "estabilidad":
            estabilidad,
    }


# ============================================================
# RANKING FINAL
# ============================================================

def imprimir_ranking(
    resultados
):

    resultados = [
        x
        for x in resultados
        if x is not None
    ]


    resultados = sorted(

        resultados,

        key=lambda x:
            x[
                "estabilidad"
            ][
                "score"
            ],

        reverse=True
    )


    print()

    print(
        "=" * 120
    )

    print(
        "       RANKING VALIDACION TEMPORAL"
    )

    print(
        "=" * 120
    )

    print()


    for resultado in resultados:


        g = resultado[
            "global"
        ]


        e = resultado[
            "estabilidad"
        ]


        print(
            f"{e['score']:>3}/100 | "
            f"{e['clasificacion']:<22} | "
            f"ExcTrim "
            f"{g['exceso_trimmed']:+6.2f}pp | "
            f"DiasBeat "
            f"{g['dias_beat']:>5.1f}% | "
            f"n={g['casos']:>4} | "
            f"dias={g['sesiones']:>2} | "
            f"{resultado['nombre']}"
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
        "     TEMPORAL VALIDATION V1"
    )

    print(
        "======================================"
    )


    df = cargar_dataset()


    if df.empty:

        print(
            "No existen resultados."
        )

        return


    df = crear_buckets(
        df
    )


    df = crear_configuraciones(
        df
    )


    df = df[
        df[
            "horizonte"
        ]
        == HORIZONTE
    ].copy()


    df[
        "market_date"
    ] = df[
        "market_date"
    ].astype(
        str
    )


    print()

    print(
        f"Resultados: "
        f"{len(df)}"
    )

    print(
        f"Simbolos:   "
        f"{df['symbol'].nunique()}"
    )

    print(
        f"Sesiones:   "
        f"{df['market_date'].nunique()}"
    )


    bloques = crear_bloques_temporales(
        df
    )


    print()

    print(
        "BLOQUES TEMPORALES"
    )

    print(
        "-" * 70
    )


    for bloque in bloques:

        print(
            f"{bloque['nombre']}: "
            f"{bloque['inicio']} -> "
            f"{bloque['fin']} "
            f"({len(bloque['fechas'])} sesiones)"
        )


    resultados = []


    for (
        nombre,
        funcion
    ) in PATRONES.items():


        mascara = funcion(
            df
        )


        datos = df[
            mascara
        ].copy()


        resultado = validar_patron(
            nombre,
            datos,
            bloques
        )


        resultados.append(
            resultado
        )


    imprimir_ranking(
        resultados
    )


if __name__ == "__main__":

    main()