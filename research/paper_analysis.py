import pandas as pd

from database.db import (
    obtener_conexion
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTES = [
    5,
    20
]

PRIORIDADES = [
    "A+",
    "A",
    "B"
]


# Una configuracion necesita como minimo
# este numero de señales.
MIN_CASOS_MOSTRAR = 20


# Y ademas debe haberse producido en varias
# sesiones diferentes.
#
# Evita sacar conclusiones de, por ejemplo:
#
# n=40
# dias=2
#
MIN_SESIONES_MOSTRAR = 5


# Estrategia analizada. Cambiar a "REVERSAL" permite estudiar
# Reversal V1 sin mezclarlo con el histórico Momentum.

STRATEGY = "MOMENTUM"


# ============================================================
# CARGAR DATASET
# ============================================================

def cargar_dataset():
    """
    Cruza:

        paper_results
            +
        paper_signals
            +
        scans

    utilizando el estado tecnico que existia
    exactamente en la fecha de la señal.

    No utiliza fundamentales ni noticias actuales.
    """

    conexion = obtener_conexion()

    query = """
        SELECT

            -- ================================================
            -- PAPER RESULT
            -- ================================================

            pr.id AS result_id,
            pr.signal_id,
            pr.horizonte,

            pr.fecha_entrada,
            pr.precio_entrada,

            pr.fecha_salida,
            pr.precio_salida,

            pr.retorno,
            pr.retorno_spy,
            pr.exceso_spy,

            pr.max_subida,
            pr.max_caida,
            pr.max_drawdown,


            -- ================================================
            -- PAPER SIGNAL
            -- ================================================

            ps.market_date,
            ps.symbol,
            ps.nombre,

            ps.score AS paper_score,
            ps.score_version,
            ps.strategy,
            ps.source_score_version,

            ps.prioridad,
            ps.perfil AS paper_perfil,

            ps.sector AS paper_sector,
            ps.sector_benchmark AS paper_sector_benchmark,

            ps.precio_senal,
            ps.alertas,


            -- ================================================
            -- SCAN ORIGINAL
            -- ================================================

            s.score,

            s.tendencia,
            s.momentum,
            s.volatilidad,

            s.rsi,
            s.volumen_relativo,

            s.return_20d,
            s.return_60d,

            s.fuerza_20d,
            s.fuerza_60d,

            s.score_tendencia,
            s.score_momentum,
            s.score_fuerza,
            s.score_sector,
            s.score_riesgo,
            s.score_volumen,

            s.penalizacion_relativa,

            s.distancia_sma20,
            s.distancia_sma50,

            s.sector,
            s.sector_benchmark,

            s.fuerza_sector_20d,
            s.fuerza_sector_60d,

            s.perfil,
            s.calidad,

            s.fortaleza_mercado,
            s.fortaleza_sector,

            s.riesgo_clasificacion,
            s.volumen_clasificacion,

            s.prioridad_estudio,
            s.motivo_prioridad,
            s.alertas_estudio

        FROM paper_results pr

        INNER JOIN paper_signals ps

            ON ps.id = pr.signal_id

        INNER JOIN scans s

            ON s.market_date = ps.market_date

            AND s.symbol = ps.symbol

            AND s.score_version = COALESCE(
                ps.source_score_version,
                ps.score_version
            )

        WHERE

            ps.strategy = ?

            AND

            ps.prioridad IN (
                'A+',
                'A',
                'B'
            )

        ORDER BY

            ps.market_date ASC,
            ps.symbol ASC,
            pr.horizonte ASC
    """

    df = pd.read_sql_query(
        query,
        conexion,
        params=(
            STRATEGY,
        )
    )

    conexion.close()

    return df


# ============================================================
# HELPERS
# ============================================================

def pct_positivos(
    serie
):

    if len(
        serie
    ) == 0:

        return 0.0

    return (
        (
            serie > 0
        ).mean()
        * 100
    )


def grupo_valido(
    grupo
):
    """
    Determina si un grupo tiene suficiente
    muestra para enseñarlo.

    Requisitos:

    - minimo N señales
    - minimo N sesiones distintas
    """

    if len(
        grupo
    ) < MIN_CASOS_MOSTRAR:

        return False


    sesiones = (
        grupo[
            "market_date"
        ].nunique()
    )


    if sesiones < MIN_SESIONES_MOSTRAR:

        return False


    return True


def resumir_grupo(
    df
):

    if df.empty:

        return None


    return {

        "casos":
            len(
                df
            ),

        "simbolos":
            df[
                "symbol"
            ].nunique(),

        "sesiones":
            df[
                "market_date"
            ].nunique(),

        "retorno_medio":
            df[
                "retorno"
            ].mean(),

        "retorno_mediana":
            df[
                "retorno"
            ].median(),

        "spy_medio":
            df[
                "retorno_spy"
            ].mean(),

        "exceso_medio":
            df[
                "exceso_spy"
            ].mean(),

        "exceso_mediana":
            df[
                "exceso_spy"
            ].median(),

        "positivas":
            pct_positivos(
                df[
                    "retorno"
                ]
            ),

        "bate_spy":
            pct_positivos(
                df[
                    "exceso_spy"
                ]
            ),

        "drawdown":
            df[
                "max_drawdown"
            ].mean(),

        "mejor":
            df[
                "retorno"
            ].max(),

        "peor":
            df[
                "retorno"
            ].min()
    }


def imprimir_resumen(
    nombre,
    resumen
):

    if resumen is None:

        return


    print(
        f"{nombre:<32} | "
        f"n={resumen['casos']:>4} | "
        f"sym={resumen['simbolos']:>3} | "
        f"dias={resumen['sesiones']:>3} | "
        f"Ret {resumen['retorno_medio']:+6.2f}% | "
        f"Med {resumen['retorno_mediana']:+6.2f}% | "
        f"Exc {resumen['exceso_medio']:+6.2f}pp | "
        f"MedExc {resumen['exceso_mediana']:+6.2f}pp | "
        f"Beat {resumen['bate_spy']:>5.1f}% | "
        f"Pos {resumen['positivas']:>5.1f}% | "
        f"DD {resumen['drawdown']:+6.2f}%"
    )


# ============================================================
# BUCKETS
# ============================================================

def crear_buckets(
    df
):

    df = df.copy()


    # ========================================================
    # RSI
    # ========================================================

    df[
        "bucket_rsi"
    ] = pd.cut(

        df[
            "rsi"
        ],

        bins=[
            -float(
                "inf"
            ),
            55,
            60,
            65,
            70,
            75,
            float(
                "inf"
            )
        ],

        labels=[
            "<55",
            "55-60",
            "60-65",
            "65-70",
            "70-75",
            ">75"
        ],

        right=False
    )


    # ========================================================
    # DISTANCIA SMA20
    # ========================================================

    df[
        "bucket_sma20"
    ] = pd.cut(

        df[
            "distancia_sma20"
        ],

        bins=[
            -float(
                "inf"
            ),
            0,
            3,
            6,
            10,
            15,
            float(
                "inf"
            )
        ],

        labels=[
            "<0%",
            "0-3%",
            "3-6%",
            "6-10%",
            "10-15%",
            ">15%"
        ],

        right=False
    )


    # ========================================================
    # DISTANCIA SMA50
    # ========================================================

    df[
        "bucket_sma50"
    ] = pd.cut(

        df[
            "distancia_sma50"
        ],

        bins=[
            -float(
                "inf"
            ),
            0,
            5,
            10,
            20,
            30,
            float(
                "inf"
            )
        ],

        labels=[
            "<0%",
            "0-5%",
            "5-10%",
            "10-20%",
            "20-30%",
            ">30%"
        ],

        right=False
    )


    # ========================================================
    # RS20
    # ========================================================

    df[
        "bucket_rs20"
    ] = pd.cut(

        df[
            "fuerza_20d"
        ],

        bins=[
            -float(
                "inf"
            ),
            0,
            5,
            10,
            15,
            25,
            float(
                "inf"
            )
        ],

        labels=[
            "<0pp",
            "0-5pp",
            "5-10pp",
            "10-15pp",
            "15-25pp",
            ">25pp"
        ],

        right=False
    )


    # ========================================================
    # RS60
    # ========================================================

    df[
        "bucket_rs60"
    ] = pd.cut(

        df[
            "fuerza_60d"
        ],

        bins=[
            -float(
                "inf"
            ),
            0,
            10,
            20,
            30,
            50,
            float(
                "inf"
            )
        ],

        labels=[
            "<0pp",
            "0-10pp",
            "10-20pp",
            "20-30pp",
            "30-50pp",
            ">50pp"
        ],

        right=False
    )


    # ========================================================
    # FUERZA SECTOR 20D
    # ========================================================

    df[
        "bucket_sector20"
    ] = pd.cut(

        df[
            "fuerza_sector_20d"
        ],

        bins=[
            -float(
                "inf"
            ),
            0,
            5,
            10,
            20,
            float(
                "inf"
            )
        ],

        labels=[
            "<0pp",
            "0-5pp",
            "5-10pp",
            "10-20pp",
            ">20pp"
        ],

        right=False
    )


    # ========================================================
    # VOLUMEN RELATIVO
    # ========================================================

    df[
        "bucket_volrel"
    ] = pd.cut(

        df[
            "volumen_relativo"
        ],

        bins=[
            -float(
                "inf"
            ),
            0.75,
            1.0,
            1.5,
            2.0,
            3.0,
            float(
                "inf"
            )
        ],

        labels=[
            "<0.75x",
            "0.75-1x",
            "1-1.5x",
            "1.5-2x",
            "2-3x",
            ">3x"
        ],

        right=False
    )


    # ========================================================
    # SCORE TOTAL
    # ========================================================

    df[
        "bucket_score"
    ] = pd.cut(

        df[
            "score"
        ],

        bins=[
            0,
            80,
            85,
            90,
            95,
            101
        ],

        labels=[
            "<80",
            "80-84",
            "85-89",
            "90-94",
            "95+"
        ],

        right=False
    )


    return df


# ============================================================
# CONFIGURACIONES DERIVADAS
# ============================================================

def crear_configuraciones(
    df
):

    df = df.copy()


    # ========================================================
    # CERCA DE SMA20
    # ========================================================

    df[
        "cerca_sma20"
    ] = "OTRA"


    mascara = (

        df[
            "distancia_sma20"
        ].notna()

        &

        (
            df[
                "distancia_sma20"
            ] >= 0
        )

        &

        (
            df[
                "distancia_sma20"
            ] <= 5
        )
    )


    df.loc[
        mascara,
        "cerca_sma20"
    ] = "0-5% SMA20"


    # ========================================================
    # RSI SANO
    # ========================================================

    df[
        "rsi_sano"
    ] = "OTRO"


    mascara = (

        df[
            "rsi"
        ].notna()

        &

        (
            df[
                "rsi"
            ] >= 50
        )

        &

        (
            df[
                "rsi"
            ] < 65
        )
    )


    df.loc[
        mascara,
        "rsi_sano"
    ] = "RSI 50-65"


    # ========================================================
    # EXTENSION
    # ========================================================

    df[
        "extension"
    ] = "NORMAL"


    mascara = (

        (
            df[
                "distancia_sma20"
            ] >= 10
        )

        |

        (
            df[
                "rsi"
            ] >= 70
        )
    )


    df.loc[
        mascara,
        "extension"
    ] = "EXTENDIDA"


    # ========================================================
    # SETUP ENTRADA V1
    # ========================================================

    df[
        "setup_entrada"
    ] = "NO"


    mascara = (

        df[
            "rsi"
        ].between(
            50,
            65,
            inclusive="left"
        )

        &

        df[
            "distancia_sma20"
        ].between(
            0,
            5,
            inclusive="both"
        )

        &

        (
            df[
                "fuerza_20d"
            ] > 0
        )
    )


    df.loc[
        mascara,
        "setup_entrada"
    ] = "SI"


    return df


# ============================================================
# ANALISIS GENERICO
# ============================================================

def analizar_variable(
    df,
    columna,
    titulo,
    horizonte
):

    datos = df[
        df[
            "horizonte"
        ]
        == horizonte
    ]


    print()

    print(
        "=" * 145
    )

    print(
        f"{titulo} | "
        f"{horizonte} SESIONES"
    )

    print(
        "=" * 145
    )


    if datos.empty:

        print(
            "Sin resultados."
        )

        return


    agrupados = []


    for valor, grupo in datos.groupby(
        columna,
        observed=True
    ):


        if not grupo_valido(
            grupo
        ):

            continue


        resumen = resumir_grupo(
            grupo
        )


        agrupados.append(
            (
                str(
                    valor
                ),
                resumen
            )
        )


    if not agrupados:

        print(
            (
                "No existen grupos con muestra "
                f"suficiente "
                f"(n>={MIN_CASOS_MOSTRAR}, "
                f"sesiones>={MIN_SESIONES_MOSTRAR})."
            )
        )

        return


    agrupados = sorted(

        agrupados,

        key=lambda x:
            x[
                1
            ][
                "exceso_medio"
            ],

        reverse=True
    )


    for (
        nombre,
        resumen
    ) in agrupados:

        imprimir_resumen(
            nombre,
            resumen
        )


# ============================================================
# PRIORIDAD + VARIABLE
# ============================================================

def analizar_prioridad_variable(
    df,
    columna,
    titulo,
    horizonte
):

    datos = df[
        df[
            "horizonte"
        ]
        == horizonte
    ]


    print()

    print(
        "=" * 145
    )

    print(
        f"PRIORIDAD + {titulo} | "
        f"{horizonte} SESIONES"
    )

    print(
        "=" * 145
    )


    resultados = []


    for prioridad in PRIORIDADES:


        datos_prioridad = datos[
            datos[
                "prioridad"
            ]
            == prioridad
        ]


        for valor, grupo in (
            datos_prioridad.groupby(
                columna,
                observed=True
            )
        ):


            if not grupo_valido(
                grupo
            ):

                continue


            resumen = resumir_grupo(
                grupo
            )


            resultados.append(
                (
                    prioridad,
                    str(
                        valor
                    ),
                    resumen
                )
            )


    if not resultados:

        print(
            (
                "No existen grupos con muestra "
                f"suficiente "
                f"(n>={MIN_CASOS_MOSTRAR}, "
                f"sesiones>={MIN_SESIONES_MOSTRAR})."
            )
        )

        return


    resultados = sorted(

        resultados,

        key=lambda x:
            x[
                2
            ][
                "exceso_medio"
            ],

        reverse=True
    )


    for (
        prioridad,
        valor,
        resumen
    ) in resultados:


        nombre = (
            f"{prioridad} | "
            f"{valor}"
        )


        imprimir_resumen(
            nombre,
            resumen
        )


# ============================================================
# MEJORES CONFIGURACIONES
# ============================================================

def analizar_mejores_configuraciones(
    df,
    horizonte
):

    datos = df[
        df[
            "horizonte"
        ]
        == horizonte
    ]


    print()

    print(
        "=" * 145
    )

    print(
        f"MEJORES CONFIGURACIONES | "
        f"{horizonte} SESIONES"
    )

    print(
        "=" * 145
    )


    columnas = [

        "prioridad",

        "bucket_rsi",

        "bucket_sma20",

        "riesgo_clasificacion",

        "volumen_clasificacion"
    ]


    grupos = (
        datos
        .groupby(
            columnas,
            observed=True
        )
    )


    resultados = []


    for (
        claves,
        grupo
    ) in grupos:


        if not grupo_valido(
            grupo
        ):

            continue


        resumen = resumir_grupo(
            grupo
        )


        resultados.append(
            (
                claves,
                resumen
            )
        )


    if not resultados:

        print()

        print(
            (
                "No existen configuraciones "
                "con muestra suficiente."
            )
        )

        print(
            (
                f"Requisito: "
                f"n>={MIN_CASOS_MOSTRAR} y "
                f"sesiones>={MIN_SESIONES_MOSTRAR}."
            )
        )

        return


    resultados = sorted(

        resultados,

        key=lambda x:
            x[
                1
            ][
                "exceso_medio"
            ],

        reverse=True
    )


    # ========================================================
    # TOP
    # ========================================================

    print()

    print(
        "TOP 10"
    )

    print(
        "-" * 145
    )


    for (
        claves,
        resumen
    ) in resultados[
        :10
    ]:


        (

            prioridad,
            rsi,
            sma20,
            riesgo,
            volumen

        ) = claves


        nombre = (
            f"{prioridad} | "
            f"RSI {rsi} | "
            f"SMA20 {sma20} | "
            f"{riesgo} | "
            f"{volumen}"
        )


        imprimir_resumen(
            nombre,
            resumen
        )


    # ========================================================
    # BOTTOM
    # ========================================================

    print()

    print(
        "BOTTOM 10"
    )

    print(
        "-" * 145
    )


    # Evitamos que TOP y BOTTOM sean exactamente
    # la misma lista cuando hay muy pocos grupos.

    if len(
        resultados
    ) <= 10:

        print(
            (
                "No se muestra BOTTOM separado: "
                "hay 10 o menos configuraciones validas."
            )
        )

        return


    for (
        claves,
        resumen
    ) in resultados[
        -10:
    ]:


        (

            prioridad,
            rsi,
            sma20,
            riesgo,
            volumen

        ) = claves


        nombre = (
            f"{prioridad} | "
            f"RSI {rsi} | "
            f"SMA20 {sma20} | "
            f"{riesgo} | "
            f"{volumen}"
        )


        imprimir_resumen(
            nombre,
            resumen
        )


# ============================================================
# RESUMEN DATASET
# ============================================================

def imprimir_resumen_dataset(
    df
):

    print()

    print(
        "======================================"
    )

    print(
        "        PAPER ANALYSIS V2"
    )

    print(
        "======================================"
    )

    print()


    print(
        f"Resultados maduros cargados: "
        f"{len(df)}"
    )


    print(
        f"Señales únicas: "
        f"{df['signal_id'].nunique()}"
    )


    print(
        f"Símbolos únicos: "
        f"{df['symbol'].nunique()}"
    )


    print(
        f"Sesiones únicas: "
        f"{df['market_date'].nunique()}"
    )


    print()


    print(
        (
            "Filtro estadistico: "
            f"minimo {MIN_CASOS_MOSTRAR} casos "
            f"y {MIN_SESIONES_MOSTRAR} sesiones."
        )
    )


    print()


    for horizonte in HORIZONTES:


        datos = df[
            df[
                "horizonte"
            ]
            == horizonte
        ]


        print(
            f"{horizonte:>2} sesiones: "
            f"{len(datos)} resultados | "
            f"{datos['market_date'].nunique()} "
            f"sesiones de señal"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    df = cargar_dataset()


    if df.empty:

        print(
            "No existen resultados paper maduros."
        )

        return


    # ========================================================
    # BUCKETS
    # ========================================================

    df = crear_buckets(
        df
    )


    # ========================================================
    # CONFIGURACIONES
    # ========================================================

    df = crear_configuraciones(
        df
    )


    # ========================================================
    # RESUMEN
    # ========================================================

    imprimir_resumen_dataset(
        df
    )


    # ========================================================
    # ANALISIS POR HORIZONTE
    # ========================================================

    for horizonte in HORIZONTES:


        # ----------------------------------------------------
        # PRIORIDAD
        # ----------------------------------------------------

        analizar_variable(
            df,
            "prioridad",
            "PRIORIDAD",
            horizonte
        )


        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_rsi",
            "RSI",
            horizonte
        )


        # ----------------------------------------------------
        # DISTANCIA SMA20
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_sma20",
            "DISTANCIA SMA20",
            horizonte
        )


        # ----------------------------------------------------
        # DISTANCIA SMA50
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_sma50",
            "DISTANCIA SMA50",
            horizonte
        )


        # ----------------------------------------------------
        # RS20
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_rs20",
            "FUERZA VS SPY 20D",
            horizonte
        )


        # ----------------------------------------------------
        # RS60
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_rs60",
            "FUERZA VS SPY 60D",
            horizonte
        )


        # ----------------------------------------------------
        # SECTOR
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_sector20",
            "FUERZA SECTOR 20D",
            horizonte
        )


        # ----------------------------------------------------
        # VOLUMEN RELATIVO
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_volrel",
            "VOLUMEN RELATIVO",
            horizonte
        )


        # ----------------------------------------------------
        # RIESGO
        # ----------------------------------------------------

        analizar_variable(
            df,
            "riesgo_clasificacion",
            "RIESGO",
            horizonte
        )


        # ----------------------------------------------------
        # VOLUMEN HUMANO
        # ----------------------------------------------------

        analizar_variable(
            df,
            "volumen_clasificacion",
            "CLASIFICACION VOLUMEN",
            horizonte
        )


        # ----------------------------------------------------
        # FORTALEZA SECTOR
        # ----------------------------------------------------

        analizar_variable(
            df,
            "fortaleza_sector",
            "FORTALEZA SECTOR",
            horizonte
        )


        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        analizar_variable(
            df,
            "bucket_score",
            "SCORE TECNICO",
            horizonte
        )


        # ----------------------------------------------------
        # EXTENSION
        # ----------------------------------------------------

        analizar_variable(
            df,
            "extension",
            "EXTENSION",
            horizonte
        )


        # ----------------------------------------------------
        # SETUP ENTRADA
        # ----------------------------------------------------

        analizar_variable(
            df,
            "setup_entrada",
            "SETUP ENTRADA",
            horizonte
        )


        # ====================================================
        # PRIORIDAD + VARIABLE
        # ====================================================

        analizar_prioridad_variable(
            df,
            "bucket_rsi",
            "RSI",
            horizonte
        )


        analizar_prioridad_variable(
            df,
            "bucket_sma20",
            "DISTANCIA SMA20",
            horizonte
        )


        analizar_prioridad_variable(
            df,
            "riesgo_clasificacion",
            "RIESGO",
            horizonte
        )


        analizar_prioridad_variable(
            df,
            "volumen_clasificacion",
            "VOLUMEN",
            horizonte
        )


        analizar_prioridad_variable(
            df,
            "extension",
            "EXTENSION",
            horizonte
        )


        analizar_prioridad_variable(
            df,
            "setup_entrada",
            "SETUP ENTRADA",
            horizonte
        )


        # ====================================================
        # CONFIGURACIONES COMPLEJAS
        # ====================================================

        analizar_mejores_configuraciones(
            df,
            horizonte
        )


if __name__ == "__main__":

    main()
