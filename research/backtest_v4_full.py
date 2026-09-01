import os

from datetime import (
    datetime,
    timedelta
)

import numpy as np
import pandas as pd

from dotenv import load_dotenv

from alpaca.data.historical import (
    StockHistoricalDataClient
)

from alpaca.data.requests import (
    StockBarsRequest
)

from alpaca.data.timeframe import (
    TimeFrame
)

from alpaca.data.enums import (
    DataFeed
)

from database.db import (
    obtener_conexion
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

TAMANO_BLOQUE = 100

COSTE_OPERACION = 0.001

PRIORIDADES = [
    "A+",
    "A",
    "B",
    "C",
    "D"
]


# ============================================================
# CREDENCIALES
# ============================================================

load_dotenv()


API_KEY = os.getenv(
    "ALPACA_API_KEY"
)

SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY"
)


if not API_KEY or not SECRET_KEY:

    raise ValueError(
        "No se han cargado las claves "
        "de Alpaca desde .env"
    )


client = StockHistoricalDataClient(
    API_KEY,
    SECRET_KEY
)


# ============================================================
# CARGAR TODOS LOS SCANS
# ============================================================

def cargar_scans():
    """
    Lee TODOS los scans históricos.

    No limita por prioridad.

    Para cada market_date + symbol nos quedamos
    con una única fila.
    """

    conexion = obtener_conexion()


    query = """
        SELECT

            id,
            scan_time,
            market_date,

            symbol,
            nombre,

            precio,

            score AS score_v3,
            score_version,

            tendencia,
            momentum,
            volatilidad,

            rsi,
            volumen_relativo,

            return_20d,
            return_60d,

            fuerza_20d,
            fuerza_60d,

            score_tendencia,
            score_momentum,
            score_fuerza,
            score_sector,
            score_riesgo,
            score_volumen,

            penalizacion_relativa,

            distancia_sma20,
            distancia_sma50,

            sector,
            sector_benchmark,

            fuerza_sector_20d,
            fuerza_sector_60d,

            perfil,
            calidad,

            fortaleza_mercado,
            fortaleza_sector,

            riesgo_clasificacion,
            volumen_clasificacion,

            prioridad_estudio AS prioridad_v3

        FROM scans

        WHERE market_date IS NOT NULL

        ORDER BY

            market_date ASC,
            symbol ASC,
            scan_time DESC
    """


    df = pd.read_sql_query(
        query,
        conexion
    )


    conexion.close()


    if df.empty:

        return df


    # --------------------------------------------------------
    # UNA FILA POR SIMBOLO / SESION
    # --------------------------------------------------------

    df = (

        df
        .sort_values(
            [
                "market_date",
                "symbol",
                "scan_time"
            ]
        )
        .drop_duplicates(
            subset=[
                "market_date",
                "symbol"
            ],
            keep="last"
        )
        .reset_index(
            drop=True
        )
    )


    return df


# ============================================================
# RECALCULAR V4
# ============================================================

def aplicar_v4(
    df
):

    resultados = []


    total = len(
        df
    )


    print()

    print(
        "Calculando Score V4..."
    )


    for numero, (_, fila) in enumerate(
        df.iterrows(),
        start=1
    ):


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


        if (
            numero % 1000 == 0
            or
            numero == total
        ):

            print(
                f"  {numero}/{total}"
            )


    df = df.copy()


    df[
        "score_v4"
    ] = [
        x[
            "total"
        ]
        for x in resultados
    ]


    df[
        "prioridad_v4"
    ] = [
        clasificar_prioridad_v4(
            x[
                "total"
            ]
        )
        for x in resultados
    ]


    df[
        "score_continuacion_v4"
    ] = [
        x[
            "continuacion"
        ]
        for x in resultados
    ]


    df[
        "riesgo_v4"
    ] = [
        x[
            "riesgo"
        ]
        for x in resultados
    ]


    return df


# ============================================================
# DESCARGAR HISTORICO FUTURO
# ============================================================

def descargar_historico(
    scans
):

    symbols = sorted(
        set(
            scans[
                "symbol"
            ].dropna()
        )
    )


    if "SPY" not in symbols:

        symbols.append(
            "SPY"
        )


    fecha_min = pd.to_datetime(
        scans[
            "market_date"
        ]
    ).min()


    fecha_max = pd.to_datetime(
        scans[
            "market_date"
        ]
    ).max()


    # Necesitamos margen antes/después.

    fecha_inicio = (
        fecha_min
        - timedelta(
            days=5
        )
    )


    fecha_fin = (
        fecha_max
        + timedelta(
            days=50
        )
    )


    # Nunca pedir futuro.

    ahora = datetime.now()


    if fecha_fin > ahora:

        fecha_fin = ahora


    dataframes = []


    total_bloques = (

        len(
            symbols
        )
        +
        TAMANO_BLOQUE
        -
        1

    ) // TAMANO_BLOQUE


    print()

    print(
        "Descargando historico..."
    )


    for inicio in range(
        0,
        len(
            symbols
        ),
        TAMANO_BLOQUE
    ):


        bloque = symbols[
            inicio:
            inicio
            +
            TAMANO_BLOQUE
        ]


        numero = (
            inicio
            //
            TAMANO_BLOQUE
        ) + 1


        print(
            f"Descargando "
            f"{numero}/"
            f"{total_bloques} "
            f"({len(bloque)} simbolos)..."
        )


        try:

            request = StockBarsRequest(

                symbol_or_symbols=bloque,

                timeframe=TimeFrame.Day,

                start=fecha_inicio,

                end=fecha_fin,

                feed=DataFeed.IEX
            )


            bars = (
                client
                .get_stock_bars(
                    request
                )
            )


            df_bloque = (
                bars
                .df
                .reset_index()
            )


            if not df_bloque.empty:

                dataframes.append(
                    df_bloque
                )


        except Exception as exc:

            print(
                f"ERROR bloque "
                f"{numero}: "
                f"{exc}"
            )


    if not dataframes:

        raise RuntimeError(
            "No se han descargado barras."
        )


    df = pd.concat(
        dataframes,
        ignore_index=True
    )


    df[
        "timestamp"
    ] = pd.to_datetime(
        df[
            "timestamp"
        ]
    )


    df[
        "market_date"
    ] = (
        df[
            "timestamp"
        ]
        .dt
        .date
        .astype(
            str
        )
    )


    return df


# ============================================================
# CREAR MAPA DE BARRAS
# ============================================================

def construir_mapa_barras(
    bars
):

    mapa = {}


    for symbol, grupo in bars.groupby(
        "symbol"
    ):


        grupo = (

            grupo
            .sort_values(
                "timestamp"
            )
            .reset_index(
                drop=True
            )
        )


        mapa[
            symbol
        ] = grupo


    return mapa


# ============================================================
# RETORNO CON COSTE
# ============================================================

def calcular_retorno(
    entrada,
    salida
):

    if (
        entrada is None
        or
        salida is None
        or
        entrada <= 0
    ):

        return None


    retorno = (
        (
            salida
            /
            entrada
        )
        -
        1
    )


    # 0.10% coste virtual.

    retorno -= (
        COSTE_OPERACION
    )


    return (
        retorno
        *
        100
    )


# ============================================================
# MAX DRAWDOWN
# ============================================================

def calcular_drawdown(
    precios,
    precio_entrada
):

    if (
        precios is None
        or
        len(
            precios
        ) == 0
        or
        precio_entrada <= 0
    ):

        return None


    precios = np.array(
        precios,
        dtype=float
    )


    serie = np.concatenate(
        [
            [
                precio_entrada
            ],
            precios
        ]
    )


    maximos = np.maximum.accumulate(
        serie
    )


    drawdowns = (
        serie
        /
        maximos
        -
        1
    )


    return (
        float(
            drawdowns.min()
        )
        *
        100
    )


# ============================================================
# EVALUAR UNA SEÑAL
# ============================================================

def evaluar_senal(
    fila,
    mapa_barras,
    horizonte
):
    """
    Entrada:
        apertura de la primera sesion posterior
        a market_date.

    Salida:
        cierre de la sesion N.

    Benchmark:
        SPY utilizando las mismas fechas.
    """

    symbol = fila[
        "symbol"
    ]


    market_date = fila[
        "market_date"
    ]


    if (
        symbol not in mapa_barras
        or
        "SPY" not in mapa_barras
    ):

        return None


    df_symbol = mapa_barras[
        symbol
    ]


    df_spy = mapa_barras[
        "SPY"
    ]


    # ========================================================
    # SESIONES POSTERIORES A LA SEÑAL
    # ========================================================

    futuro = df_symbol[
        df_symbol[
            "market_date"
        ]
        >
        market_date
    ].copy()


    if len(
        futuro
    ) < horizonte:

        return None


    periodo = futuro.iloc[
        :horizonte
    ]


    fecha_entrada = (
        periodo.iloc[
            0
        ][
            "market_date"
        ]
    )


    fecha_salida = (
        periodo.iloc[
            horizonte - 1
        ][
            "market_date"
        ]
    )


    precio_entrada = float(
        periodo.iloc[
            0
        ][
            "open"
        ]
    )


    precio_salida = float(
        periodo.iloc[
            horizonte - 1
        ][
            "close"
        ]
    )


    # ========================================================
    # SPY MISMAS FECHAS
    # ========================================================

    spy_entrada = df_spy[
        df_spy[
            "market_date"
        ]
        ==
        fecha_entrada
    ]


    spy_salida = df_spy[
        df_spy[
            "market_date"
        ]
        ==
        fecha_salida
    ]


    if (
        spy_entrada.empty
        or
        spy_salida.empty
    ):

        return None


    precio_spy_entrada = float(
        spy_entrada.iloc[
            0
        ][
            "open"
        ]
    )


    precio_spy_salida = float(
        spy_salida.iloc[
            0
        ][
            "close"
        ]
    )


    retorno = calcular_retorno(
        precio_entrada,
        precio_salida
    )


    retorno_spy = calcular_retorno(
        precio_spy_entrada,
        precio_spy_salida
    )


    if (
        retorno is None
        or
        retorno_spy is None
    ):

        return None


    exceso = (
        retorno
        -
        retorno_spy
    )


    max_subida = (

        (
            periodo[
                "high"
            ].max()
            /
            precio_entrada
        )
        -
        1

    ) * 100


    max_caida = (

        (
            periodo[
                "low"
            ].min()
            /
            precio_entrada
        )
        -
        1

    ) * 100


    max_drawdown = calcular_drawdown(

        periodo[
            "close"
        ].values,

        precio_entrada
    )


    return {

        "market_date":
            market_date,

        "symbol":
            symbol,

        "score_v3":
            fila[
                "score_v3"
            ],

        "prioridad_v3":
            fila[
                "prioridad_v3"
            ],

        "score_v4":
            fila[
                "score_v4"
            ],

        "prioridad_v4":
            fila[
                "prioridad_v4"
            ],

        "horizonte":
            horizonte,

        "fecha_entrada":
            fecha_entrada,

        "fecha_salida":
            fecha_salida,

        "retorno":
            retorno,

        "retorno_spy":
            retorno_spy,

        "exceso_spy":
            exceso,

        "max_subida":
            max_subida,

        "max_caida":
            max_caida,

        "max_drawdown":
            max_drawdown,
    }


# ============================================================
# EVALUAR TODO
# ============================================================

def evaluar_todo(
    scans,
    mapa_barras
):

    resultados = []


    total = len(
        scans
    )


    print()

    print(
        "Evaluando scans..."
    )


    for numero, (_, fila) in enumerate(
        scans.iterrows(),
        start=1
    ):


        for horizonte in HORIZONTES:


            resultado = evaluar_senal(

                fila,
                mapa_barras,
                horizonte
            )


            if resultado:

                resultados.append(
                    resultado
                )


        if (
            numero % 1000 == 0
            or
            numero == total
        ):

            print(
                f"  {numero}/{total}"
            )


    return pd.DataFrame(
        resultados
    )


# ============================================================
# HELPERS ESTADISTICOS
# ============================================================

def pct_positivo(
    serie
):

    if serie.empty:

        return 0.0


    return (
        (
            serie > 0
        ).mean()
        *
        100
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
        n
        *
        porcentaje
    )


    if (
        corte == 0
        or
        corte * 2 >= n
    ):

        return (
            serie.mean()
        )


    return (

        serie.iloc[
            corte:
            n - corte
        ]
        .mean()
    )


# ============================================================
# RESUMIR GRUPO
# ============================================================

def resumir(
    datos
):

    if datos.empty:

        return None


    por_dia = (

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
            pct_positivo(
                datos[
                    "retorno"
                ]
            ),

        "bate_spy":
            pct_positivo(
                datos[
                    "exceso_spy"
                ]
            ),

        "dias_beat":
            pct_positivo(
                por_dia
            ),

        "drawdown":
            datos[
                "max_drawdown"
            ].mean()
    }


def imprimir_resumen(
    nombre,
    r
):

    if r is None:

        return


    print(
        f"{nombre:<10} | "
        f"n={r['n']:>5} | "
        f"sym={r['simbolos']:>4} | "
        f"dias={r['dias']:>3} | "
        f"Ret={r['retorno']:+7.2f}% | "
        f"Med={r['mediana']:+7.2f}% | "
        f"Exc={r['exceso']:+7.2f}pp | "
        f"ExcTrim={r['exceso_trimmed']:+7.2f}pp | "
        f"Beat={r['bate_spy']:>5.1f}% | "
        f"DiasBeat={r['dias_beat']:>5.1f}% | "
        f"DD={r['drawdown']:+7.2f}%"
    )


# ============================================================
# COMPARACION V3 VS V4
# ============================================================

def comparar(
    resultados,
    horizonte
):

    datos = resultados[
        resultados[
            "horizonte"
        ]
        ==
        horizonte
    ]


    print()

    print(
        "=" * 130
    )

    print(
        f"        {horizonte} SESIONES"
    )

    print(
        "=" * 130
    )


    # ========================================================
    # V3
    # ========================================================

    print()

    print(
        "V3 - UNIVERSO COMPLETO"
    )

    print(
        "-" * 130
    )


    for prioridad in PRIORIDADES:


        grupo = datos[
            datos[
                "prioridad_v3"
            ]
            ==
            prioridad
        ]


        if grupo.empty:

            continue


        imprimir_resumen(
            prioridad,
            resumir(
                grupo
            )
        )


    # ========================================================
    # V4
    # ========================================================

    print()

    print(
        "V4 - UNIVERSO COMPLETO"
    )

    print(
        "-" * 130
    )


    for prioridad in PRIORIDADES:


        grupo = datos[
            datos[
                "prioridad_v4"
            ]
            ==
            prioridad
        ]


        if grupo.empty:

            continue


        imprimir_resumen(
            prioridad,
            resumir(
                grupo
            )
        )


# ============================================================
# MIGRACIONES DE PRIORIDAD
# ============================================================

def imprimir_migraciones(
    scans
):

    print()

    print(
        "=" * 100
    )

    print(
        "        MATRIZ V3 -> V4 | TODOS LOS SCANS"
    )

    print(
        "=" * 100
    )


    matriz = pd.crosstab(

        scans[
            "prioridad_v3"
        ],

        scans[
            "prioridad_v4"
        ]
    )


    columnas = [
        x
        for x in PRIORIDADES
        if x in matriz.columns
    ]


    matriz = matriz.reindex(
        columns=columnas
    )


    print()

    print(
        matriz.to_string()
    )


# ============================================================
# DESCUBRIMIENTOS V4
# ============================================================

def analizar_descubrimientos(
    resultados
):
    """
    Activos que V3 tenia como C/D
    pero V4 habria elevado a A+/A/B.
    """

    print()

    print(
        "=" * 130
    )

    print(
        "        DESCUBRIMIENTOS V4"
    )

    print(
        "=" * 130
    )


    datos = resultados[
        resultados[
            "horizonte"
        ]
        ==
        5
    ]


    descubrimientos = datos[

        datos[
            "prioridad_v3"
        ].isin(
            [
                "C",
                "D"
            ]
        )

        &

        datos[
            "prioridad_v4"
        ].isin(
            [
                "A+",
                "A",
                "B"
            ]
        )
    ]


    print()

    imprimir_resumen(
        "TOTAL",
        resumir(
            descubrimientos
        )
    )


    print()


    for prioridad in [
        "A+",
        "A",
        "B"
    ]:


        grupo = descubrimientos[
            descubrimientos[
                "prioridad_v4"
            ]
            ==
            prioridad
        ]


        if grupo.empty:

            continue


        imprimir_resumen(
            prioridad,
            resumir(
                grupo
            )
        )


# ============================================================
# DESCARTES V4
# ============================================================

def analizar_descartes(
    resultados
):
    """
    Señales que V3 consideraba A+/A/B,
    pero V4 habría enviado a C/D.
    """

    print()

    print(
        "=" * 130
    )

    print(
        "        DESCARTES V4"
    )

    print(
        "=" * 130
    )


    datos = resultados[
        resultados[
            "horizonte"
        ]
        ==
        5
    ]


    descartes = datos[

        datos[
            "prioridad_v3"
        ].isin(
            [
                "A+",
                "A",
                "B"
            ]
        )

        &

        datos[
            "prioridad_v4"
        ].isin(
            [
                "C",
                "D"
            ]
        )
    ]


    print()

    imprimir_resumen(
        "TOTAL",
        resumir(
            descartes
        )
    )


# ============================================================
# SCORE V4 POR DECILES
# ============================================================

def analizar_deciles(
    resultados
):

    datos = resultados[
        resultados[
            "horizonte"
        ]
        ==
        5
    ].copy()


    if datos.empty:

        return


    try:

        datos[
            "decil_v4"
        ] = pd.qcut(

            datos[
                "score_v4"
            ],

            q=10,

            duplicates="drop"
        )

    except Exception:

        return


    print()

    print(
        "=" * 130
    )

    print(
        "        SCORE V4 POR DECILES"
    )

    print(
        "=" * 130
    )


    grupos = []


    for bucket, grupo in datos.groupby(
        "decil_v4",
        observed=True
    ):


        grupos.append(
            (
                grupo[
                    "score_v4"
                ].mean(),
                str(
                    bucket
                ),
                resumir(
                    grupo
                )
            )
        )


    grupos = sorted(
        grupos,
        key=lambda x:
            x[
                0
            ],
        reverse=True
    )


    for _, bucket, r in grupos:

        imprimir_resumen(
            bucket,
            r
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
        "     FULL V4 HISTORICAL BACKTEST"
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
            "No hay scans."
        )

        return


    print()

    print(
        f"Scans historicos: "
        f"{len(scans)}"
    )


    print(
        f"Simbolos:         "
        f"{scans['symbol'].nunique()}"
    )


    print(
        f"Sesiones:         "
        f"{scans['market_date'].nunique()}"
    )


    print(
        f"Primera sesion:   "
        f"{scans['market_date'].min()}"
    )


    print(
        f"Ultima sesion:    "
        f"{scans['market_date'].max()}"
    )


    # ========================================================
    # V4
    # ========================================================

    scans = aplicar_v4(
        scans
    )


    imprimir_migraciones(
        scans
    )


    # ========================================================
    # HISTORICO
    # ========================================================

    bars = descargar_historico(
        scans
    )


    mapa_barras = construir_mapa_barras(
        bars
    )


    # ========================================================
    # RESULTADOS
    # ========================================================

    resultados = evaluar_todo(
        scans,
        mapa_barras
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
        f"Resultados maduros: "
        f"{len(resultados)}"
    )


    for horizonte in HORIZONTES:

        cantidad = len(

            resultados[
                resultados[
                    "horizonte"
                ]
                ==
                horizonte
            ]
        )


        print(
            f"{horizonte:>2} sesiones: "
            f"{cantidad}"
        )


    # ========================================================
    # COMPARATIVA
    # ========================================================

    for horizonte in HORIZONTES:

        comparar(
            resultados,
            horizonte
        )


    # ========================================================
    # DESCUBRIMIENTOS
    # ========================================================

    analizar_descubrimientos(
        resultados
    )


    # ========================================================
    # DESCARTES
    # ========================================================

    analizar_descartes(
        resultados
    )


    # ========================================================
    # DECILES
    # ========================================================

    analizar_deciles(
        resultados
    )


    print()

    print(
        "======================================"
    )

    print(
        "              NOTA"
    )

    print(
        "======================================"
    )

    print()

    print(
        "Este script NO modifica la base de datos."
    )

    print(
        "V4 se calcula retrospectivamente usando "
        "solo los campos almacenados en cada scan."
    )

    print(
        "La entrada virtual se realiza en la "
        "apertura posterior a la señal."
    )

    print(
        "Se aplica un coste virtual del 0.10%."
    )


if __name__ == "__main__":

    main()