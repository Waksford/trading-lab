import pandas as pd

from research.paper_analysis import (
    cargar_dataset
)

from scoring.momentum_v4 import (
    calcular_score_v4,
    clasificar_prioridad_v4
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTES = [
    5,
    20
]


ORDEN_PRIORIDAD = [
    "A+",
    "A",
    "B",
    "C",
    "D"
]


# ============================================================
# CALCULAR V4
# ============================================================

def aplicar_v4(
    df
):

    df = df.copy()


    resultados = []


    for _, fila in df.iterrows():


        score = calcular_score_v4(

            tendencia=(
                fila[
                    "tendencia"
                ]
            ),

            rsi=(
                fila[
                    "rsi"
                ]
            ),

            fuerza_20d=(
                fila[
                    "fuerza_20d"
                ]
            ),

            fuerza_60d=(
                fila[
                    "fuerza_60d"
                ]
            ),

            fuerza_sector_20d=(
                fila[
                    "fuerza_sector_20d"
                ]
            ),

            fuerza_sector_60d=(
                fila[
                    "fuerza_sector_60d"
                ]
            ),

            distancia_sma20=(
                fila[
                    "distancia_sma20"
                ]
            ),

            volumen_relativo=(
                fila[
                    "volumen_relativo"
                ]
            ),

            volatilidad=(
                fila[
                    "volatilidad"
                ]
            )
        )


        resultados.append(
            score
        )


    df[
        "score_v4"
    ] = [
        r[
            "total"
        ]
        for r in resultados
    ]


    df[
        "prioridad_v4"
    ] = [
        clasificar_prioridad_v4(
            r[
                "total"
            ]
        )
        for r in resultados
    ]


    df[
        "continuacion_v4"
    ] = [
        r[
            "continuacion"
        ]
        for r in resultados
    ]


    df[
        "riesgo_v4"
    ] = [
        r[
            "riesgo"
        ]
        for r in resultados
    ]


    return df


# ============================================================
# HELPERS
# ============================================================

def pct(
    serie
):

    if serie.empty:

        return 0.0


    return (
        (
            serie > 0
        ).mean()
        * 100
    )


def trimmed_mean(
    serie,
    porcentaje=0.05
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

        return 0.0


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
            "market_date"
        )[
            "exceso_spy"
        ]
        .mean()
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

        "dias":
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

        "exceso_trimmed":
            trimmed_mean(
                datos[
                    "exceso_spy"
                ]
            ),

        "positivos":
            pct(
                datos[
                    "retorno"
                ]
            ),

        "bate_spy":
            pct(
                datos[
                    "exceso_spy"
                ]
            ),

        "dias_beat":
            pct(
                sesiones
            ),

        "drawdown":
            datos[
                "max_drawdown"
            ].mean()
    }


def imprimir(
    nombre,
    r
):

    if r is None:

        return


    print(
        f"{nombre:<8} | "
        f"n={r['n']:>4} | "
        f"sym={r['simbolos']:>3} | "
        f"dias={r['dias']:>2} | "
        f"Ret={r['retorno']:+6.2f}% | "
        f"Med={r['mediana']:+6.2f}% | "
        f"Exc={r['exceso']:+6.2f}pp | "
        f"ExcTrim={r['exceso_trimmed']:+6.2f}pp | "
        f"Beat={r['bate_spy']:>5.1f}% | "
        f"DiasBeat={r['dias_beat']:>5.1f}% | "
        f"DD={r['drawdown']:+6.2f}%"
    )


# ============================================================
# DISTRIBUCION SCORE
# ============================================================

def imprimir_distribucion(
    datos
):

    print()

    print(
        "DISTRIBUCION SCORE V4"
    )

    print(
        "-" * 80
    )


    print(
        datos[
            "score_v4"
        ]
        .describe(
            percentiles=[
                .10,
                .25,
                .50,
                .75,
                .90,
                .95,
                .99
            ]
        )
        .to_string()
    )


# ============================================================
# MATRIZ V3 VS V4
# ============================================================

def imprimir_matriz(
    datos
):

    print()

    print(
        "MATRIZ PRIORIDAD V3 -> V4"
    )

    print(
        "-" * 80
    )


    matriz = pd.crosstab(

        datos[
            "prioridad"
        ],

        datos[
            "prioridad_v4"
        ]
    )


    columnas = [
        x
        for x in ORDEN_PRIORIDAD
        if x in matriz.columns
    ]


    matriz = matriz.reindex(
        columns=columnas
    )


    print(
        matriz.to_string()
    )


# ============================================================
# COMPARACION
# ============================================================

def comparar_horizonte(
    df,
    horizonte
):

    datos = df[
        df[
            "horizonte"
        ]
        == horizonte
    ].copy()


    print()

    print(
        "=" * 120
    )

    print(
        f"        {horizonte} SESIONES"
    )

    print(
        "=" * 120
    )


    print()

    print(
        "V3"
    )

    print(
        "-" * 120
    )


    for prioridad in [
        "A+",
        "A",
        "B"
    ]:


        grupo = datos[
            datos[
                "prioridad"
            ]
            == prioridad
        ]


        imprimir(
            prioridad,
            resumir(
                grupo
            )
        )


    print()

    print(
        "V4 EXPERIMENTAL"
    )

    print(
        "-" * 120
    )


    for prioridad in ORDEN_PRIORIDAD:


        grupo = datos[
            datos[
                "prioridad_v4"
            ]
            == prioridad
        ]


        if grupo.empty:

            continue


        imprimir(
            prioridad,
            resumir(
                grupo
            )
        )


    imprimir_matriz(
        datos
    )


# ============================================================
# TOP SCORE V4
# ============================================================

def analizar_top_percentiles(
    df
):

    datos = df[
        df[
            "horizonte"
        ]
        == 5
    ].copy()


    print()

    print(
        "=" * 120
    )

    print(
        "        TOP PERCENTILES V4 | 5 SESIONES"
    )

    print(
        "=" * 120
    )


    for q in [
        0.50,
        0.75,
        0.90,
        0.95
    ]:


        limite = (
            datos[
                "score_v4"
            ].quantile(
                q
            )
        )


        grupo = datos[
            datos[
                "score_v4"
            ]
            >= limite
        ]


        nombre = (
            f"TOP {int((1-q)*100):>2}% "
            f"(>={limite:.0f})"
        )


        imprimir(
            nombre,
            resumir(
                grupo
            )
        )


# ============================================================
# CORRELACION SCORE / RESULTADO
# ============================================================

def analizar_correlacion(
    df
):

    datos = df[
        df[
            "horizonte"
        ]
        == 5
    ]


    correlacion_retorno = (
        datos[
            [
                "score_v4",
                "retorno"
            ]
        ]
        .corr()
        .iloc[
            0,
            1
        ]
    )


    correlacion_exceso = (
        datos[
            [
                "score_v4",
                "exceso_spy"
            ]
        ]
        .corr()
        .iloc[
            0,
            1
        ]
    )


    print()

    print(
        "CORRELACION SCORE V4"
    )

    print(
        "-" * 80
    )


    print(
        f"Score V4 vs retorno 5d: "
        f"{correlacion_retorno:+.4f}"
    )


    print(
        f"Score V4 vs exceso SPY: "
        f"{correlacion_exceso:+.4f}"
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
        "       SCORE V4 BACKTEST"
    )

    print(
        "======================================"
    )


    df = cargar_dataset()


    if df.empty:

        print(
            "No existen resultados maduros."
        )

        return


    df = aplicar_v4(
        df
    )


    print()

    print(
        f"Resultados: "
        f"{len(df)}"
    )

    print(
        f"Senales:    "
        f"{df['signal_id'].nunique()}"
    )

    print(
        f"Simbolos:   "
        f"{df['symbol'].nunique()}"
    )

    print(
        f"Sesiones:   "
        f"{df['market_date'].nunique()}"
    )


    imprimir_distribucion(
        df[
            df[
                "horizonte"
            ]
            == 5
        ]
    )


    for horizonte in HORIZONTES:

        comparar_horizonte(
            df,
            horizonte
        )


    analizar_top_percentiles(
        df
    )


    analizar_correlacion(
        df
    )


if __name__ == "__main__":

    main()