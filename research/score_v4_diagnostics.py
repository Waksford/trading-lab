# score_v4_diagnostics.py

import pandas as pd
import numpy as np

from research.backtest_v4_full import (
    cargar_scans,
    aplicar_v4,
    descargar_historico,
    construir_mapa_barras,
    evaluar_todo,
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTE = 5

LOW_MIN = 5
LOW_MAX = 12

HIGH_MIN = 96
HIGH_MAX = 100

TOP_SECTORES = 10

COLUMNAS_DIAGNOSTICO = [
    "rsi",
    "distancia_sma20",
    "distancia_sma50",
    "volumen_relativo",
    "fuerza_20d",
    "fuerza_60d",
    "fuerza_sector_20d",
    "fuerza_sector_60d",
    "return_20d",
    "return_60d",
]


# ============================================================
# HELPERS
# ============================================================

def pct(
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
        return None

    corte = int(
        n * porcentaje
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


def safe_mean(
    serie
):

    serie = pd.to_numeric(
        serie,
        errors="coerce"
    )

    serie = serie.dropna()

    if serie.empty:
        return None

    return serie.mean()

def safe_median(
    serie
):

    serie = pd.to_numeric(
        serie,
        errors="coerce"
    )

    serie = serie.dropna()

    if serie.empty:
        return None

    return serie.median()
def fmt(
    valor,
    decimales=2
):

    if valor is None:
        return "N/A"

    if pd.isna(
        valor
    ):
        return "N/A"

    return (
        f"{valor:.{decimales}f}"
    )


# ============================================================
# UNIR RESULTADOS CON SCANS
# ============================================================

def construir_dataset(
    scans,
    resultados
):
    """
    Une el resultado futuro con los datos tecnicos
    originales disponibles el dia de la senal.
    """

    resultados_5d = resultados[
        resultados[
            "horizonte"
        ]
        == HORIZONTE
    ].copy()


    columnas_scan = [

        "market_date",
        "symbol",

        "score_v3",
        "prioridad_v3",

        "score_v4",
        "prioridad_v4",

        "tendencia",
        "momentum",
        "volatilidad",

        "rsi",
        "volumen_relativo",

        "return_20d",
        "return_60d",

        "fuerza_20d",
        "fuerza_60d",

        "distancia_sma20",
        "distancia_sma50",

        "sector",
        "sector_benchmark",

        "fuerza_sector_20d",
        "fuerza_sector_60d",

        "riesgo_clasificacion",
        "volumen_clasificacion",

        "perfil",
        "calidad",
        "fortaleza_mercado",
        "fortaleza_sector",
    ]


    scans_reducido = scans[
        [
            columna
            for columna in columnas_scan
            if columna in scans.columns
        ]
    ].copy()


    # Quitamos duplicados por seguridad.

    scans_reducido = (
        scans_reducido
        .sort_values(
            [
                "market_date",
                "symbol"
            ]
        )
        .drop_duplicates(
            subset=[
                "market_date",
                "symbol"
            ],
            keep="last"
        )
    )


    # Algunas columnas ya existen en resultados.
    # Evitamos duplicarlas.

    columnas_ya_presentes = {

        "score_v3",
        "prioridad_v3",
        "score_v4",
        "prioridad_v4",
    }


    scans_join = scans_reducido.drop(
        columns=[
            columna
            for columna in columnas_ya_presentes
            if columna in scans_reducido.columns
        ],
        errors="ignore"
    )


    df = resultados_5d.merge(

        scans_join,

        on=[
            "market_date",
            "symbol"
        ],

        how="left"
    )


    return df


# ============================================================
# RESUMEN PERFORMANCE
# ============================================================

def resumen_performance(
    datos
):

    if datos.empty:
        return None


    por_dia = (
        datos
        .groupby(
            "market_date"
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

        "dias":
            datos[
                "market_date"
            ].nunique(),

        "retorno":
            datos[
                "retorno"
            ].mean(),

        "retorno_mediana":
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

        "beat":
            pct(
                datos[
                    "exceso_spy"
                ]
            ),

        "dias_positivos":
            pct(
                por_dia[
                    "retorno"
                ]
            ),

        "dias_beat":
            pct(
                por_dia[
                    "exceso"
                ]
            ),

        "drawdown":
            datos[
                "max_drawdown"
            ].mean(),

        "mejor":
            datos[
                "retorno"
            ].max(),

        "peor":
            datos[
                "retorno"
            ].min(),
    }


def imprimir_performance(
    titulo,
    datos
):

    r = resumen_performance(
        datos
    )


    print()

    print(
        titulo
    )

    print(
        "-" * 100
    )


    if r is None:

        print(
            "Sin datos."
        )

        return


    print(
        f"Casos:                   "
        f"{r['n']}"
    )

    print(
        f"Simbolos:                "
        f"{r['simbolos']}"
    )

    print(
        f"Sesiones:                "
        f"{r['dias']}"
    )

    print()

    print(
        f"Retorno medio:           "
        f"{r['retorno']:+.2f}%"
    )

    print(
        f"Retorno mediana:         "
        f"{r['retorno_mediana']:+.2f}%"
    )

    print()

    print(
        f"Exceso medio:            "
        f"{r['exceso']:+.2f}pp"
    )

    print(
        f"Exceso mediana:          "
        f"{r['exceso_mediana']:+.2f}pp"
    )

    print(
        f"Exceso trimmed:          "
        f"{r['exceso_trimmed']:+.2f}pp"
    )

    print()

    print(
        f"Resultados positivos:    "
        f"{r['positivos']:.1f}%"
    )

    print(
        f"Baten SPY:               "
        f"{r['beat']:.1f}%"
    )

    print(
        f"Sesiones positivas:      "
        f"{r['dias_positivos']:.1f}%"
    )

    print(
        f"Sesiones baten SPY:      "
        f"{r['dias_beat']:.1f}%"
    )

    print()

    print(
        f"Drawdown medio:          "
        f"{r['drawdown']:+.2f}%"
    )

    print(
        f"Mejor caso:              "
        f"{r['mejor']:+.2f}%"
    )

    print(
        f"Peor caso:               "
        f"{r['peor']:+.2f}%"
    )


# ============================================================
# ESTADISTICAS TECNICAS
# ============================================================

def imprimir_metricas(
    titulo,
    datos
):

    print()

    print(
        titulo
    )

    print(
        "-" * 100
    )


    print(
        f"{'METRICA':<25} "
        f"{'MEDIA':>12} "
        f"{'MEDIANA':>12} "
        f"{'P25':>12} "
        f"{'P75':>12} "
        f"{'NULOS':>10}"
    )


    print(
        "-" * 100
    )


    for columna in COLUMNAS_DIAGNOSTICO:


        if columna not in datos.columns:
            continue


        serie = pd.to_numeric(
            datos[
                columna
            ],
            errors="coerce"
        )


        validos = serie.dropna()


        if validos.empty:

            print(
                f"{columna:<25} "
                f"{'N/A':>12} "
                f"{'N/A':>12} "
                f"{'N/A':>12} "
                f"{'N/A':>12} "
                f"{100:>9.1f}%"
            )

            continue


        porcentaje_nulos = (
            serie.isna().mean()
            * 100
        )


        print(
            f"{columna:<25} "
            f"{validos.mean():>12.2f} "
            f"{validos.median():>12.2f} "
            f"{validos.quantile(0.25):>12.2f} "
            f"{validos.quantile(0.75):>12.2f} "
            f"{porcentaje_nulos:>9.1f}%"
        )


# ============================================================
# DATOS AUSENTES
# ============================================================

def imprimir_missingness(
    titulo,
    datos
):

    print()

    print(
        titulo
    )

    print(
        "-" * 80
    )


    filas = []


    for columna in COLUMNAS_DIAGNOSTICO:


        if columna not in datos.columns:
            continue


        porcentaje = (
            datos[
                columna
            ].isna().mean()
            * 100
        )


        filas.append(
            (
                columna,
                porcentaje
            )
        )


    filas = sorted(
        filas,
        key=lambda x:
            x[
                1
            ],
        reverse=True
    )


    for columna, porcentaje in filas:

        print(
            f"{columna:<25} "
            f"{porcentaje:>6.2f}% sin datos"
        )


# ============================================================
# DISTRIBUCIONES CATEGORICAS
# ============================================================

def imprimir_distribucion(
    datos,
    columna,
    titulo,
    limite=15
):

    if columna not in datos.columns:
        return


    print()

    print(
        titulo
    )

    print(
        "-" * 80
    )


    serie = (
        datos[
            columna
        ]
        .fillna(
            "SIN DATOS"
        )
        .astype(
            str
        )
    )


    conteo = (
        serie
        .value_counts(
            dropna=False
        )
    )


    total = len(
        datos
    )


    for valor, cantidad in conteo.head(
        limite
    ).items():

        porcentaje = (
            cantidad
            /
            total
            *
            100
        )


        print(
            f"{valor:<35} "
            f"{cantidad:>6} "
            f"{porcentaje:>7.2f}%"
        )


# ============================================================
# DISTRIBUCION V3
# ============================================================

def imprimir_prioridad_v3(
    datos
):

    imprimir_distribucion(
        datos,
        "prioridad_v3",
        "PRIORIDAD ORIGINAL V3"
    )


# ============================================================
# SECTORES
# ============================================================

def imprimir_sectores(
    datos
):

    imprimir_distribucion(
        datos,
        "sector",
        "TOP SECTORES",
        limite=TOP_SECTORES
    )


# ============================================================
# EXTREMOS
# ============================================================

def imprimir_extremos(
    datos,
    titulo,
    cantidad=15
):

    print()

    print(
        titulo
    )

    print(
        "-" * 120
    )


    columnas = [
        "market_date",
        "symbol",
        "score_v3",
        "prioridad_v3",
        "score_v4",
        "retorno",
        "exceso_spy",
        "rsi",
        "distancia_sma20",
        "volatilidad",
        "volumen_relativo",
        "fuerza_20d",
        "fuerza_60d",
        "sector",
    ]


    columnas = [
        columna
        for columna in columnas
        if columna in datos.columns
    ]


    top = (
        datos
        .sort_values(
            "retorno",
            ascending=False
        )
        .head(
            cantidad
        )
    )


    bottom = (
        datos
        .sort_values(
            "retorno",
            ascending=True
        )
        .head(
            cantidad
        )
    )


    print()

    print(
        "MEJORES CASOS"
    )

    print(
        top[
            columnas
        ].to_string(
            index=False
        )
    )


    print()

    print(
        "PEORES CASOS"
    )

    print(
        bottom[
            columnas
        ].to_string(
            index=False
        )
    )


# ============================================================
# CONTRIBUCION DE OUTLIERS
# ============================================================

def analizar_outliers(
    datos,
    titulo
):

    print()

    print(
        titulo
    )

    print(
        "-" * 100
    )


    if len(
        datos
    ) < 20:

        print(
            "Muestra insuficiente."
        )

        return


    serie = datos[
        "retorno"
    ].dropna()


    p01 = serie.quantile(
        0.01
    )

    p05 = serie.quantile(
        0.05
    )

    p95 = serie.quantile(
        0.95
    )

    p99 = serie.quantile(
        0.99
    )


    print(
        f"P01 retorno:             "
        f"{p01:+.2f}%"
    )

    print(
        f"P05 retorno:             "
        f"{p05:+.2f}%"
    )

    print(
        f"P95 retorno:             "
        f"{p95:+.2f}%"
    )

    print(
        f"P99 retorno:             "
        f"{p99:+.2f}%"
    )


    media_normal = serie.mean()


    sin_top_1 = datos[
        datos[
            "retorno"
        ]
        <= p99
    ]


    sin_top_bottom_1 = datos[

        (
            datos[
                "retorno"
            ]
            >= p01
        )

        &

        (
            datos[
                "retorno"
            ]
            <= p99
        )
    ]


    print()

    print(
        f"Media original:          "
        f"{media_normal:+.2f}%"
    )

    print(
        f"Media sin top 1%:        "
        f"{sin_top_1['retorno'].mean():+.2f}%"
    )

    print(
        f"Media sin extremos 1%:   "
        f"{sin_top_bottom_1['retorno'].mean():+.2f}%"
    )

    print(
        f"Exceso trimmed 5%:       "
        f"{trimmed_mean(datos['exceso_spy']):+.2f}pp"
    )


# ============================================================
# DECILES SCORE V4
# ============================================================

def analizar_deciles(
    df
):

    print()

    print(
        "=" * 140
    )

    print(
        "        DIAGNOSTICO POR DECILES V4"
    )

    print(
        "=" * 140
    )


    df = df.copy()


    try:

        df[
            "decil_v4"
        ] = pd.qcut(

            df[
                "score_v4"
            ],

            q=10,

            duplicates="drop"
        )

    except Exception as exc:

        print(
            f"No se pudieron crear deciles: {exc}"
        )

        return


    grupos = []


    for bucket, grupo in df.groupby(
        "decil_v4",
        observed=True
    ):


        r = resumen_performance(
            grupo
        )


        grupos.append(
            {

                "bucket":
                    str(
                        bucket
                    ),

                "score_min":
                    grupo[
                        "score_v4"
                    ].min(),

                "score_med":
                    grupo[
                        "score_v4"
                    ].median(),

                "score_max":
                    grupo[
                        "score_v4"
                    ].max(),

                "n":
                    len(
                        grupo
                    ),

                "sym":
                    grupo[
                        "symbol"
                    ].nunique(),

                "ret":
                    r[
                        "retorno"
                    ],

                "med":
                    r[
                        "retorno_mediana"
                    ],

                "exc":
                    r[
                        "exceso"
                    ],

                "trim":
                    r[
                        "exceso_trimmed"
                    ],

                "beat":
                    r[
                        "beat"
                    ],

                "dias_beat":
                    r[
                        "dias_beat"
                    ],

                "rsi":
                    safe_median(
                        grupo[
                            "rsi"
                        ]
                    ),

                "sma20":
                    safe_median(
                        grupo[
                            "distancia_sma20"
                        ]
                    ),

                "volrel":
                    safe_median(
                        grupo[
                            "volumen_relativo"
                        ]
                    ),

                "rs20":
                    safe_median(
                        grupo[
                            "fuerza_20d"
                        ]
                    ),

                "rs60":
                    safe_median(
                        grupo[
                            "fuerza_60d"
                        ]
                    ),
            }
        )


    resumen = pd.DataFrame(
        grupos
    )


    resumen = resumen.sort_values(
        "score_med",
        ascending=False
    )


    print()

    print(
        f"{'SCORE':<18} "
        f"{'N':>6} "
        f"{'RET':>8} "
        f"{'MED':>8} "
        f"{'EXC':>8} "
        f"{'TRIM':>8} "
        f"{'BEAT':>8} "
        f"{'RSI':>8} "
        f"{'SMA20':>8} "
        f"{'VOL':>8} "
        f"{'VOLREL':>8} "
        f"{'RS20':>8} "
        f"{'RS60':>8}"
    )


    print(
        "-" * 140
    )


    for _, fila in resumen.iterrows():

        print(
            f"{fila['bucket']:<18} "
            f"{int(fila['n']):>6} "
            f"{fila['ret']:>+7.2f}% "
            f"{fila['med']:>+7.2f}% "
            f"{fila['exc']:>+7.2f} "
            f"{fila['trim']:>+7.2f} "
            f"{fila['beat']:>7.1f}% "
            f"{fmt(fila['rsi']):>8} "
            f"{fmt(fila['sma20']):>8} "
            f"{fmt(fila['volrel']):>8} "
            f"{fmt(fila['rs20']):>8} "
            f"{fmt(fila['rs60']):>8}"
        )


# ============================================================
# COMPARACION LOW VS HIGH
# ============================================================

def comparar_low_high(
    df
):

    low = df[

        df[
            "score_v4"
        ].between(
            LOW_MIN,
            LOW_MAX,
            inclusive="both"
        )

    ].copy()


    high = df[

        df[
            "score_v4"
        ].between(
            HIGH_MIN,
            HIGH_MAX,
            inclusive="both"
        )

    ].copy()


    print()

    print(
        "=" * 120
    )

    print(
        "        COMPARACION EXTREMOS V4"
    )

    print(
        "=" * 120
    )


    imprimir_performance(
        f"SCORE V4 {LOW_MIN}-{LOW_MAX}",
        low
    )


    imprimir_performance(
        f"SCORE V4 {HIGH_MIN}-{HIGH_MAX}",
        high
    )


    imprimir_metricas(
        f"METRICAS SCORE {LOW_MIN}-{LOW_MAX}",
        low
    )


    imprimir_metricas(
        f"METRICAS SCORE {HIGH_MIN}-{HIGH_MAX}",
        high
    )


    imprimir_missingness(
        f"MISSINGNESS SCORE {LOW_MIN}-{LOW_MAX}",
        low
    )


    imprimir_missingness(
        f"MISSINGNESS SCORE {HIGH_MIN}-{HIGH_MAX}",
        high
    )


    # ========================================================
    # V3
    # ========================================================

    imprimir_prioridad_v3(
        low
    )


    imprimir_prioridad_v3(
        high
    )


    # ========================================================
    # SECTORES
    # ========================================================

    print()

    print(
        "=" * 100
    )

    print(
        f"SECTORES SCORE {LOW_MIN}-{LOW_MAX}"
    )

    print(
        "=" * 100
    )

    imprimir_sectores(
        low
    )


    print()

    print(
        "=" * 100
    )

    print(
        f"SECTORES SCORE {HIGH_MIN}-{HIGH_MAX}"
    )

    print(
        "=" * 100
    )

    imprimir_sectores(
        high
    )


    # ========================================================
    # CATEGORIAS HUMANAS
    # ========================================================

    for columna in [

        "tendencia",
        "momentum",
        "volatilidad",
        "riesgo_clasificacion",
        "volumen_clasificacion",
        "fortaleza_mercado",
        "fortaleza_sector",
        "perfil",
        "calidad",

    ]:


        imprimir_distribucion(

            low,

            columna,

            (
                f"{columna.upper()} "
                f"SCORE {LOW_MIN}-{LOW_MAX}"
            )
        )


        imprimir_distribucion(

            high,

            columna,

            (
                f"{columna.upper()} "
                f"SCORE {HIGH_MIN}-{HIGH_MAX}"
            )
        )


    # ========================================================
    # OUTLIERS
    # ========================================================

    analizar_outliers(

        low,

        (
            f"OUTLIERS SCORE "
            f"{LOW_MIN}-{LOW_MAX}"
        )
    )


    analizar_outliers(

        high,

        (
            f"OUTLIERS SCORE "
            f"{HIGH_MIN}-{HIGH_MAX}"
        )
    )


    # ========================================================
    # EXTREMOS
    # ========================================================

    imprimir_extremos(

        low,

        (
            f"CASOS EXTREMOS SCORE "
            f"{LOW_MIN}-{LOW_MAX}"
        )
    )


    imprimir_extremos(

        high,

        (
            f"CASOS EXTREMOS SCORE "
            f"{HIGH_MIN}-{HIGH_MAX}"
        )
    )


# ============================================================
# ESTUDIAR SCORES BAJOS POR SUBGRUPOS
# ============================================================

def analizar_low_subgrupos(
    df
):

    low = df[
        df[
            "score_v4"
        ].between(
            LOW_MIN,
            LOW_MAX,
            inclusive="both"
        )
    ].copy()


    # Asegurar tipos numericos antes de crear buckets.
    columnas_numericas = [
        "score_v4",
        "rsi",
        "distancia_sma20",
        "distancia_sma50",
        "volumen_relativo",
        "fuerza_20d",
        "fuerza_60d",
        "fuerza_sector_20d",
        "fuerza_sector_60d",
        "return_20d",
        "return_60d",
    ]

    for columna in columnas_numericas:

        if columna in low.columns:

            low[columna] = pd.to_numeric(
                low[columna],
                errors="coerce"
            )


    print()

    print(
        "=" * 120
    )

    print(
        "        SUBGRUPOS DEL SCORE BAJO"
    )

    print(
        "=" * 120
    )


    # ========================================================
    # RSI
    # ========================================================

    low[
        "rsi_bucket_diag"
    ] = pd.cut(

        low[
            "rsi"
        ],

        bins=[
            -np.inf,
            30,
            40,
            50,
            60,
            70,
            80,
            np.inf
        ],

        labels=[
            "<30",
            "30-40",
            "40-50",
            "50-60",
            "60-70",
            "70-80",
            ">80"
        ],

        right=False
    )


    # ========================================================
    # SMA20
    # ========================================================

    low[
        "sma20_bucket_diag"
    ] = pd.cut(

        low[
            "distancia_sma20"
        ],

        bins=[
            -np.inf,
            -20,
            -10,
            -5,
            0,
            5,
            10,
            20,
            np.inf
        ],

        labels=[
            "<-20%",
            "-20/-10%",
            "-10/-5%",
            "-5/0%",
            "0/5%",
            "5/10%",
            "10/20%",
            ">20%"
        ],

        right=False
    )


    # ========================================================
    # VOLATILIDAD
    # ========================================================
    #
    # En la DB volatilidad es una clasificacion categorica
    # (BAJA / MEDIA / ALTA / MUY ALTA), no un valor numerico.
    # La analizamos directamente, sin pd.cut().

    analizar_variable_low(
        low,
        "rsi_bucket_diag",
        "RSI"
    )


    analizar_variable_low(
        low,
        "sma20_bucket_diag",
        "DISTANCIA SMA20"
    )


    analizar_variable_low(
        low,
        "volatilidad",
        "VOLATILIDAD"
    )


    analizar_variable_low(
        low,
        "prioridad_v3",
        "PRIORIDAD V3"
    )


    analizar_variable_low(
        low,
        "sector",
        "SECTOR",
        minimo=50
    )


def analizar_variable_low(
    datos,
    columna,
    titulo,
    minimo=20
):

    print()

    print(
        titulo
    )

    print(
        "-" * 120
    )


    resultados = []


    for valor, grupo in datos.groupby(
        columna,
        observed=True
    ):


        if len(
            grupo
        ) < minimo:

            continue


        r = resumen_performance(
            grupo
        )


        resultados.append(
            (
                str(
                    valor
                ),
                r
            )
        )


    resultados = sorted(

        resultados,

        key=lambda x:
            x[
                1
            ][
                "exceso_trimmed"
            ],

        reverse=True
    )


    for nombre, r in resultados:

        print(
            f"{nombre:<25} | "
            f"n={r['n']:>5} | "
            f"sym={r['simbolos']:>4} | "
            f"Ret={r['retorno']:+6.2f}% | "
            f"Med={r['retorno_mediana']:+6.2f}% | "
            f"Exc={r['exceso']:+6.2f}pp | "
            f"Trim={r['exceso_trimmed']:+6.2f}pp | "
            f"Beat={r['beat']:>5.1f}% | "
            f"DD={r['drawdown']:+6.2f}%"
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
        "      SCORE V4 DIAGNOSTICS"
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
            "No hay scans historicos."
        )

        return


    print()

    print(
        f"Scans:     {len(scans)}"
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
    # PRECIOS FUTUROS
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
    # DECILES
    # ========================================================

    analizar_deciles(
        df
    )


    # ========================================================
    # EXTREMOS
    # ========================================================

    comparar_low_high(
        df
    )


    # ========================================================
    # SUBGRUPOS DEL LOW SCORE
    # ========================================================

    analizar_low_subgrupos(
        df
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