# test_reversal_v1.py

import itertools

import numpy as np
import pandas as pd

from research.backtest_v4_full import (
    cargar_scans,
    aplicar_v4,
    descargar_historico,
    construir_mapa_barras,
    evaluar_todo,
)

from research.score_v4_diagnostics import (
    construir_dataset,
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTE = 5

MIN_CASOS = 100
MIN_SIMBOLOS = 50
MIN_SESIONES = 10

TRIM_PERCENT = 0.05


# ============================================================
# RANGOS A PROBAR
# ============================================================

SCORE_RANGES = [
    (5, 12),
    (5, 18),
    (5, 26),
    (12, 18),
    (12, 26),
]


RSI_RANGES = [
    (25, 40),
    (30, 40),
    (30, 45),
    (35, 45),
    (30, 50),
]


SMA20_RANGES = [
    (-30, -20),
    (-20, -10),
    (-20, -5),
    (-15, -5),
    (-10, -5),
    (-10, 0),
]


VOLATILIDADES = [
    ("MUY ALTA",),
    ("ALTA", "MUY ALTA"),
]


# ============================================================
# HELPERS
# ============================================================

def pct_positivo(
    serie
):

    serie = (
        serie
        .dropna()
    )

    if serie.empty:
        return 0.0

    return (
        (serie > 0).mean()
        * 100
    )


def trimmed_mean(
    serie,
    porcentaje=TRIM_PERCENT
):

    serie = (
        pd.to_numeric(
            serie,
            errors="coerce"
        )
        .dropna()
        .sort_values()
    )


    n = len(
        serie
    )


    if n == 0:
        return None


    corte = int(
        n
        * porcentaje
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
# PREPARAR TIPOS
# ============================================================

def preparar_dataset(
    df
):

    df = df.copy()


    columnas_numericas = [

        "score_v4",

        "rsi",

        "distancia_sma20",
        "distancia_sma50",

        "volumen_relativo",

        "fuerza_20d",
        "fuerza_60d",

        "return_20d",
        "return_60d",

        "retorno",
        "exceso_spy",
        "max_drawdown",
    ]


    for columna in columnas_numericas:

        if columna in df.columns:

            df[
                columna
            ] = pd.to_numeric(

                df[
                    columna
                ],

                errors="coerce"
            )


    if "volatilidad" in df.columns:

        df[
            "volatilidad"
        ] = (

            df[
                "volatilidad"
            ]

            .fillna(
                "SIN DATOS"
            )

            .astype(
                str
            )

            .str.strip()

            .str.upper()
        )


    return df


# ============================================================
# RESUMEN
# ============================================================

def resumir(
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

            retorno=(
                "retorno",
                "mean"
            ),

            exceso=(
                "exceso_spy",
                "mean"
            ),
        )
    )


    return {

        "n":
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

        "retorno":
            datos[
                "retorno"
            ].mean(),

        "mediana":
            datos[
                "retorno"
            ].median(),

        "exceso":
            datos[
                "exceso_spy"
            ].mean(),

        "exceso_mediana":
            datos[
                "exceso_spy"
            ].median(),

        "trim":
            trimmed_mean(
                datos[
                    "exceso_spy"
                ]
            ),

        "positivos":
            pct_positivo(
                datos[
                    "retorno"
                ]
            ),

        "beat":
            pct_positivo(
                datos[
                    "exceso_spy"
                ]
            ),

        "dias_positivos":
            pct_positivo(
                sesiones[
                    "retorno"
                ]
            ),

        "dias_beat":
            pct_positivo(
                sesiones[
                    "exceso"
                ]
            ),

        "drawdown":
            datos[
                "max_drawdown"
            ].mean(),

        "peor":
            datos[
                "retorno"
            ].min(),

        "mejor":
            datos[
                "retorno"
            ].max(),
    }


# ============================================================
# BLOQUES TEMPORALES
# ============================================================

def crear_bloques(
    df
):

    fechas = sorted(

        df[
            "market_date"
        ]

        .dropna()

        .unique()
    )


    arrays = np.array_split(
        fechas,
        3
    )


    bloques = []


    for numero, fechas_bloque in enumerate(
        arrays,
        start=1
    ):


        fechas_bloque = list(
            fechas_bloque
        )


        if not fechas_bloque:
            continue


        bloques.append(
            {

                "numero":
                    numero,

                "fechas":
                    fechas_bloque,

                "inicio":
                    fechas_bloque[
                        0
                    ],

                "fin":
                    fechas_bloque[
                        -1
                    ],
            }
        )


    return bloques


# ============================================================
# ESTABILIDAD TEMPORAL
# ============================================================

def calcular_estabilidad(
    datos,
    bloques
):

    excesos = []


    for bloque in bloques:


        bloque_df = datos[

            datos[
                "market_date"
            ].isin(
                bloque[
                    "fechas"
                ]
            )

        ]


        if len(
            bloque_df
        ) < 10:

            excesos.append(
                None
            )

            continue


        valor = trimmed_mean(

            bloque_df[
                "exceso_spy"
            ]
        )


        excesos.append(
            valor
        )


    validos = [
        x
        for x in excesos
        if x is not None
    ]


    positivos = sum(
        1
        for x in validos
        if x > 0
    )


    if not validos:

        porcentaje = 0.0

    else:

        porcentaje = (
            positivos
            /
            len(
                validos
            )
            *
            100
        )


    return {

        "bloques":
            excesos,

        "positivos":
            positivos,

        "validos":
            len(
                validos
            ),

        "pct_positivos":
            porcentaje,
    }


# ============================================================
# ROBUSTEZ REVERSAL
# ============================================================

def score_robustez(
    resumen,
    estabilidad
):
    """
    No es un score de trading.
    Solo sirve para ordenar las reglas del test.
    """

    puntos = 0


    # ========================================================
    # MUESTRA
    # MAX 15
    # ========================================================

    if resumen[
        "n"
    ] >= 1000:

        puntos += 15

    elif resumen[
        "n"
    ] >= 500:

        puntos += 12

    elif resumen[
        "n"
    ] >= 250:

        puntos += 9

    else:

        puntos += 5


    # ========================================================
    # EXCESO TRIMMED
    # MAX 25
    # ========================================================

    trim = resumen[
        "trim"
    ]


    if trim >= 2:

        puntos += 25

    elif trim >= 1.5:

        puntos += 22

    elif trim >= 1:

        puntos += 18

    elif trim >= 0.5:

        puntos += 12

    elif trim > 0:

        puntos += 6


    # ========================================================
    # BEAT SPY
    # MAX 15
    # ========================================================

    beat = resumen[
        "beat"
    ]


    if beat >= 60:

        puntos += 15

    elif beat >= 55:

        puntos += 12

    elif beat >= 52:

        puntos += 9

    elif beat >= 50:

        puntos += 5


    # ========================================================
    # DIAS BEAT
    # MAX 20
    # ========================================================

    dias_beat = resumen[
        "dias_beat"
    ]


    if dias_beat >= 75:

        puntos += 20

    elif dias_beat >= 65:

        puntos += 16

    elif dias_beat >= 55:

        puntos += 12

    elif dias_beat >= 50:

        puntos += 7


    # ========================================================
    # ESTABILIDAD EN 3 BLOQUES
    # MAX 15
    # ========================================================

    pct_bloques = estabilidad[
        "pct_positivos"
    ]


    if pct_bloques == 100:

        puntos += 15

    elif pct_bloques >= 66:

        puntos += 10

    elif pct_bloques >= 33:

        puntos += 4


    # ========================================================
    # RIESGO
    # MAX 10
    # ========================================================

    dd = resumen[
        "drawdown"
    ]


    if dd >= -4:

        puntos += 10

    elif dd >= -5:

        puntos += 8

    elif dd >= -6:

        puntos += 5

    elif dd >= -8:

        puntos += 2


    return min(
        100,
        puntos
    )


# ============================================================
# CREAR REGLA
# ============================================================

def aplicar_regla(
    df,
    score_range,
    rsi_range,
    sma_range,
    volatilidades
):

    score_min, score_max = (
        score_range
    )

    rsi_min, rsi_max = (
        rsi_range
    )

    sma_min, sma_max = (
        sma_range
    )


    mascara = (

        df[
            "score_v4"
        ].between(
            score_min,
            score_max,
            inclusive="both"
        )

        &

        df[
            "rsi"
        ].between(
            rsi_min,
            rsi_max,
            inclusive="left"
        )

        &

        df[
            "distancia_sma20"
        ].between(
            sma_min,
            sma_max,
            inclusive="left"
        )

        &

        df[
            "volatilidad"
        ].isin(
            volatilidades
        )
    )


    return df[
        mascara
    ].copy()


# ============================================================
# TEST SISTEMATICO
# ============================================================

def probar_combinaciones(
    df
):

    bloques = crear_bloques(
        df
    )


    resultados = []


    combinaciones = itertools.product(

        SCORE_RANGES,
        RSI_RANGES,
        SMA20_RANGES,
        VOLATILIDADES
    )


    total = (

        len(
            SCORE_RANGES
        )

        *

        len(
            RSI_RANGES
        )

        *

        len(
            SMA20_RANGES
        )

        *

        len(
            VOLATILIDADES
        )
    )


    print()

    print(
        f"Combinaciones a evaluar: "
        f"{total}"
    )


    for numero, (
        score_range,
        rsi_range,
        sma_range,
        volatilidades
    ) in enumerate(
        combinaciones,
        start=1
    ):


        datos = aplicar_regla(

            df,

            score_range,

            rsi_range,

            sma_range,

            volatilidades
        )


        if len(
            datos
        ) < MIN_CASOS:

            continue


        if (
            datos[
                "symbol"
            ].nunique()
            <
            MIN_SIMBOLOS
        ):

            continue


        if (
            datos[
                "market_date"
            ].nunique()
            <
            MIN_SESIONES
        ):

            continue


        resumen = resumir(
            datos
        )


        estabilidad = calcular_estabilidad(
            datos,
            bloques
        )


        robustez = score_robustez(
            resumen,
            estabilidad
        )


        resultados.append(
            {

                "score_min":
                    score_range[
                        0
                    ],

                "score_max":
                    score_range[
                        1
                    ],

                "rsi_min":
                    rsi_range[
                        0
                    ],

                "rsi_max":
                    rsi_range[
                        1
                    ],

                "sma_min":
                    sma_range[
                        0
                    ],

                "sma_max":
                    sma_range[
                        1
                    ],

                "volatilidad":
                    "+".join(
                        volatilidades
                    ),

                "n":
                    resumen[
                        "n"
                    ],

                "simbolos":
                    resumen[
                        "simbolos"
                    ],

                "sesiones":
                    resumen[
                        "sesiones"
                    ],

                "retorno":
                    resumen[
                        "retorno"
                    ],

                "mediana":
                    resumen[
                        "mediana"
                    ],

                "exceso":
                    resumen[
                        "exceso"
                    ],

                "trim":
                    resumen[
                        "trim"
                    ],

                "beat":
                    resumen[
                        "beat"
                    ],

                "dias_beat":
                    resumen[
                        "dias_beat"
                    ],

                "drawdown":
                    resumen[
                        "drawdown"
                    ],

                "peor":
                    resumen[
                        "peor"
                    ],

                "mejor":
                    resumen[
                        "mejor"
                    ],

                "bloque1":
                    estabilidad[
                        "bloques"
                    ][
                        0
                    ],

                "bloque2":
                    estabilidad[
                        "bloques"
                    ][
                        1
                    ],

                "bloque3":
                    estabilidad[
                        "bloques"
                    ][
                        2
                    ],

                "robustez":
                    robustez,
            }
        )


    return pd.DataFrame(
        resultados
    )


# ============================================================
# FORMATEAR BLOQUE
# ============================================================

def fmt_bloque(
    valor
):

    if valor is None:
        return " N/A "

    return (
        f"{valor:+5.2f}"
    )


# ============================================================
# IMPRIMIR RANKING
# ============================================================

def imprimir_ranking(
    resultados
):

    print()

    print(
        "=" * 170
    )

    print(
        "        TOP REVERSAL V1"
    )

    print(
        "=" * 170
    )


    if resultados.empty:

        print(
            "No hay configuraciones validas."
        )

        return


    resultados = resultados.sort_values(

        by=[
            "robustez",
            "trim",
            "dias_beat"
        ],

        ascending=[
            False,
            False,
            False
        ]
    )


    print()

    print(
        f"{'ROB':>4} | "
        f"{'SCORE':<7} | "
        f"{'RSI':<7} | "
        f"{'SMA20':<10} | "
        f"{'VOLATILIDAD':<18} | "
        f"{'N':>5} | "
        f"{'SYM':>4} | "
        f"{'RET':>7} | "
        f"{'MED':>7} | "
        f"{'EXC':>7} | "
        f"{'TRIM':>7} | "
        f"{'BEAT':>6} | "
        f"{'DBEAT':>6} | "
        f"{'DD':>7} | "
        f"{'B1':>6} | "
        f"{'B2':>6} | "
        f"{'B3':>6}"
    )


    print(
        "-" * 170
    )


    for _, r in resultados.head(
        30
    ).iterrows():


        print(
            f"{int(r['robustez']):>3}/100 | "

            f"{int(r['score_min'])}-"
            f"{int(r['score_max']):<4} | "

            f"{int(r['rsi_min'])}-"
            f"{int(r['rsi_max']):<4} | "

            f"{int(r['sma_min'])}/"
            f"{int(r['sma_max']):<6} | "

            f"{r['volatilidad']:<18} | "

            f"{int(r['n']):>5} | "

            f"{int(r['simbolos']):>4} | "

            f"{r['retorno']:+6.2f}% | "

            f"{r['mediana']:+6.2f}% | "

            f"{r['exceso']:+6.2f} | "

            f"{r['trim']:+6.2f} | "

            f"{r['beat']:>5.1f}% | "

            f"{r['dias_beat']:>5.1f}% | "

            f"{r['drawdown']:+6.2f}% | "

            f"{fmt_bloque(r['bloque1']):>6} | "

            f"{fmt_bloque(r['bloque2']):>6} | "

            f"{fmt_bloque(r['bloque3']):>6}"
        )


# ============================================================
# MEJOR CONFIGURACION
# ============================================================

def imprimir_mejor(
    resultados
):

    if resultados.empty:
        return


    mejor = (

        resultados

        .sort_values(

            by=[
                "robustez",
                "trim"
            ],

            ascending=[
                False,
                False
            ]
        )

        .iloc[
            0
        ]
    )


    print()

    print(
        "=" * 100
    )

    print(
        "        MEJOR CANDIDATO REVERSAL V1"
    )

    print(
        "=" * 100
    )

    print()


    print(
        f"Score V4:       "
        f"{int(mejor['score_min'])}-"
        f"{int(mejor['score_max'])}"
    )


    print(
        f"RSI:            "
        f"{int(mejor['rsi_min'])}-"
        f"{int(mejor['rsi_max'])}"
    )


    print(
        f"Distancia SMA20:"
        f" {int(mejor['sma_min'])}% "
        f"a {int(mejor['sma_max'])}%"
    )


    print(
        f"Volatilidad:    "
        f"{mejor['volatilidad']}"
    )


    print()

    print(
        f"Casos:          "
        f"{int(mejor['n'])}"
    )


    print(
        f"Simbolos:       "
        f"{int(mejor['simbolos'])}"
    )


    print()

    print(
        f"Retorno:        "
        f"{mejor['retorno']:+.2f}%"
    )


    print(
        f"Mediana:        "
        f"{mejor['mediana']:+.2f}%"
    )


    print(
        f"Exceso:         "
        f"{mejor['exceso']:+.2f}pp"
    )


    print(
        f"Exceso trimmed: "
        f"{mejor['trim']:+.2f}pp"
    )


    print(
        f"Beat SPY:       "
        f"{mejor['beat']:.1f}%"
    )


    print(
        f"Dias Beat:      "
        f"{mejor['dias_beat']:.1f}%"
    )


    print(
        f"Drawdown:       "
        f"{mejor['drawdown']:+.2f}%"
    )


    print()

    print(
        f"Bloque 1:       "
        f"{fmt_bloque(mejor['bloque1'])}pp"
    )


    print(
        f"Bloque 2:       "
        f"{fmt_bloque(mejor['bloque2'])}pp"
    )


    print(
        f"Bloque 3:       "
        f"{fmt_bloque(mejor['bloque3'])}pp"
    )


    print()

    print(
        f"Robustez:       "
        f"{int(mejor['robustez'])}/100"
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
        "       REVERSAL V1 BACKTEST"
    )

    print(
        "======================================"
    )


    # ========================================================
    # SCANS
    # ========================================================

    scans = cargar_scans()


    if scans.empty:

        print(
            "No existen scans."
        )

        return


    print()

    print(
        f"Scans:     "
        f"{len(scans)}"
    )


    print(
        f"Simbolos:  "
        f"{scans['symbol'].nunique()}"
    )


    print(
        f"Sesiones:  "
        f"{scans['market_date'].nunique()}"
    )


    # ========================================================
    # V4
    # ========================================================

    scans = aplicar_v4(
        scans
    )


    # ========================================================
    # PRECIOS
    # ========================================================

    bars = descargar_historico(
        scans
    )


    mapa = construir_mapa_barras(
        bars
    )


    resultados = evaluar_todo(
        scans,
        mapa
    )


    if resultados.empty:

        print(
            "No hay resultados maduros."
        )

        return


    # ========================================================
    # DATASET
    # ========================================================

    df = construir_dataset(
        scans,
        resultados
    )


    df = preparar_dataset(
        df
    )


    print()

    print(
        f"Resultados 5d: "
        f"{len(df)}"
    )


    print(
        f"Simbolos:      "
        f"{df['symbol'].nunique()}"
    )


    print(
        f"Sesiones:      "
        f"{df['market_date'].nunique()}"
    )


    # ========================================================
    # TEST
    # ========================================================

    resultados_test = probar_combinaciones(
        df
    )


    imprimir_ranking(
        resultados_test
    )


    imprimir_mejor(
        resultados_test
    )


    print()

    print(
        "======================================"
    )

    print(
        "              FIN"
    )

    print(
        "======================================"
    )

    print()

    print(
        "No se ha modificado la base de datos."
    )


if __name__ == "__main__":

    main()