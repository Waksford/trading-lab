import os

from pathlib import Path
from datetime import (
    datetime,
    timedelta
)

import pandas as pd

from market.paper_exit_variants import aplicar_take_profit

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

    inicializar_db,

    asegurar_columna_market_date,

    asegurar_columnas_sectoriales,

    asegurar_columnas_score_v3,

    asegurar_columnas_v4_reversal,

    asegurar_columnas_clasificacion,

    inicializar_tablas_paper,

    sincronizar_senales_paper,

    obtener_senales_paper_incompletas,

    obtener_horizontes_paper,

    guardar_resultado_paper,

    obtener_resultados_paper,

    obtener_resumen_paper
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

ESTRATEGIAS = (
    {
        "strategy": "MOMENTUM",
        "score_version": "v4",
        "prioridades": ("A+", "A", "B")
    },
    {
        "strategy": "REVERSAL",
        "score_version": "v4",
        "prioridades": ("A",)
    }
)


PRIORIDADES = [
    "A+",
    "A",
    "B"
]


HORIZONTES = [
    5,
    20,
    60
]


TAKE_PROFIT_POR_VARIANTE = {
    "TP25": 25.0,
    "TP10": 10.0
}


# Coste virtual de ida + vuelta.
#
# 0.10 = 0.10%
#
# Se aplica tanto al activo como a SPY
# para hacer la comparación más justa.

COSTE_TOTAL_PCT = 0.10


# ============================================================
# ALPACA
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
        "No se han encontrado las claves "
        "de Alpaca en .env"
    )


client = (
    StockHistoricalDataClient(
        API_KEY,
        SECRET_KEY
    )
)


# ============================================================
# DESCARGAR HISTÓRICO
# ============================================================

def descargar_historico(
    symbols,
    fecha_inicio,
    fecha_fin
):

    symbols = sorted(
        set(symbols)
    )


    TAMANO_BLOQUE = 100


    dataframes = []


    for inicio in range(
        0,
        len(symbols),
        TAMANO_BLOQUE
    ):

        bloque = symbols[
            inicio:
            inicio + TAMANO_BLOQUE
        ]


        numero = (
            inicio
            // TAMANO_BLOQUE
        ) + 1


        total = (
            len(symbols)
            + TAMANO_BLOQUE
            - 1
        ) // TAMANO_BLOQUE


        print(
            f"Descargando histórico "
            f"{numero}/{total} "
            f"({len(bloque)} símbolos)..."
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


            df = (
                bars.df
                .reset_index()
            )


            if not df.empty:

                dataframes.append(
                    df
                )


        except Exception as e:

            print(
                f"Error descargando bloque: "
                f"{e}"
            )


    if not dataframes:

        return pd.DataFrame()


    df = pd.concat(
        dataframes,
        ignore_index=True
    )


    df[
        "timestamp"
    ] = pd.to_datetime(
        df[
            "timestamp"
        ],
        utc=True
    )


    return df


# ============================================================
# PREPARAR HISTÓRICOS
# ============================================================

def preparar_historicos(
    df
):

    historicos = {}


    for symbol in df[
        "symbol"
    ].unique():

        datos = df[
            df["symbol"]
            == symbol
        ].copy()


        datos = datos.sort_values(
            "timestamp"
        )


        datos = datos.reset_index(
            drop=True
        )


        datos[
            "market_date"
        ] = (
            datos[
                "timestamp"
            ]
            .dt
            .date
        )


        historicos[
            symbol
        ] = datos


    return historicos


# ============================================================
# EVALUAR UNA SEÑAL
# ============================================================

def evaluar_senal(
    senal,
    datos_activo,
    datos_spy,
    horizonte
):
    """
    Regla de simulación:

    Día D:
        radar genera señal al cierre.

    Día D+1:
        entrada a apertura.

    Horizonte 5:
        salida al cierre de la quinta
        sesión bursátil desde la entrada.

    El calendario se obtiene desde SPY,
    evitando que una acción suspendida
    altere el contador de sesiones.
    """

    fecha_senal = (
        datetime.strptime(
            senal[
                "market_date"
            ],
            "%Y-%m-%d"
        )
        .date()
    )


    # ========================================================
    # CALENDARIO DE MERCADO
    # ========================================================

    sesiones_spy = datos_spy[
        datos_spy[
            "market_date"
        ] > fecha_senal
    ].copy()


    if len(
        sesiones_spy
    ) < horizonte:

        return None


    # Primera sesión posterior a señal.

    barra_spy_entrada = (
        sesiones_spy.iloc[0]
    )


    # Horizonte 5:
    #
    # índices:
    # 0 = sesión 1
    # 1 = sesión 2
    # ...
    # 4 = sesión 5

    barra_spy_salida = (
        sesiones_spy.iloc[
            horizonte - 1
        ]
    )


    fecha_entrada = (
        barra_spy_entrada[
            "market_date"
        ]
    )


    fecha_salida = (
        barra_spy_salida[
            "market_date"
        ]
    )


    # ========================================================
    # ACTIVO EN FECHA DE ENTRADA
    # ========================================================

    entrada_activo = datos_activo[
        datos_activo[
            "market_date"
        ] == fecha_entrada
    ]


    salida_activo = datos_activo[
        datos_activo[
            "market_date"
        ] == fecha_salida
    ]


    if (
        entrada_activo.empty
        or salida_activo.empty
    ):

        return None


    entrada_activo = (
        entrada_activo.iloc[0]
    )


    salida_activo = (
        salida_activo.iloc[0]
    )


    # ========================================================
    # PRECIOS
    # ========================================================

    precio_entrada = float(
        entrada_activo[
            "open"
        ]
    )


    precio_salida = float(
        salida_activo[
            "close"
        ]
    )


    spy_entrada = float(
        barra_spy_entrada[
            "open"
        ]
    )


    spy_salida = float(
        barra_spy_salida[
            "close"
        ]
    )


    if (
        precio_entrada <= 0
        or spy_entrada <= 0
    ):

        return None


    # ========================================================
    # RENTABILIDAD ACTIVO
    # ========================================================

    retorno_bruto = (
        (
            precio_salida
            / precio_entrada
        )
        - 1
    ) * 100


    retorno = (
        retorno_bruto
        - COSTE_TOTAL_PCT
    )


    # ========================================================
    # RENTABILIDAD SPY
    # ========================================================

    retorno_spy_bruto = (
        (
            spy_salida
            / spy_entrada
        )
        - 1
    ) * 100


    retorno_spy = (
        retorno_spy_bruto
        - COSTE_TOTAL_PCT
    )


    exceso_spy = (
        retorno
        - retorno_spy
    )


    # ========================================================
    # VENTANA DE LA OPERACIÓN
    # ========================================================

    ventana = datos_activo[
        (
            datos_activo[
                "market_date"
            ] >= fecha_entrada
        )
        &
        (
            datos_activo[
                "market_date"
            ] <= fecha_salida
        )
    ].copy()


    if ventana.empty:

        return None


    # ========================================================
    # MÁXIMA SUBIDA DESDE ENTRADA
    # ========================================================

    max_high = float(
        ventana[
            "high"
        ].max()
    )


    max_subida = (
        (
            max_high
            / precio_entrada
        )
        - 1
    ) * 100


    # ========================================================
    # MÁXIMA CAÍDA DESDE ENTRADA
    # ========================================================

    min_low = float(
        ventana[
            "low"
        ].min()
    )


    max_caida = (
        (
            min_low
            / precio_entrada
        )
        - 1
    ) * 100


    # ========================================================
    # MAX DRAWDOWN
    # ========================================================

    cierres = [
        precio_entrada
    ]


    cierres.extend(
        ventana[
            "close"
        ]
        .astype(float)
        .tolist()
    )


    serie = pd.Series(
        cierres
    )


    maximos = (
        serie.cummax()
    )


    drawdowns = (
        (
            serie
            / maximos
        )
        - 1
    ) * 100


    max_drawdown = float(
        drawdowns.min()
    )


    resultado = {

        "signal_id":
            senal[
                "id"
            ],

        "symbol":
            senal[
                "symbol"
            ],

        "prioridad":
            senal[
                "prioridad"
            ],

        "horizonte":
            horizonte,

        "fecha_entrada":
            str(
                fecha_entrada
            ),

        "precio_entrada":
            precio_entrada,

        "fecha_salida":
            str(
                fecha_salida
            ),

        "precio_salida":
            precio_salida,

        "retorno":
            retorno,

        "retorno_spy":
            retorno_spy,

        "exceso_spy":
            exceso_spy,

        "max_subida":
            max_subida,

        "max_caida":
            max_caida,

        "max_drawdown":
            max_drawdown,

        "variant":
            senal.get("variant", "BASE"),

        "exit_reason":
            "TIME",

        "planned_exit_date":
            str(fecha_salida),

        "actual_exit_date":
            str(fecha_salida),

        "holding_sessions_real":
            horizonte
    }

    variante = senal.get("variant", "BASE")

    if variante in TAKE_PROFIT_POR_VARIANTE:

        if horizonte != 5:
            return None

        return aplicar_take_profit(
            resultado,
            datos_activo,
            datos_spy,
            TAKE_PROFIT_POR_VARIANTE[variante],
            COSTE_TOTAL_PCT
        )

    return resultado


# ============================================================
# RESUMEN ESTADÍSTICO
# ============================================================

def resumir_resultados(
    resultados
):

    if not resultados:

        return None


    df = pd.DataFrame(
        resultados
    )


    return {

        "casos":
            len(df),

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
            (
                df[
                    "retorno"
                ] > 0
            ).mean()
            * 100,

        "bate_spy":
            (
                df[
                    "exceso_spy"
                ] > 0
            ).mean()
            * 100,

        "max_subida_media":
            df[
                "max_subida"
            ].mean(),

        "max_caida_media":
            df[
                "max_caida"
            ].mean(),

        "drawdown_medio":
            df[
                "max_drawdown"
            ].mean(),

        "peor_drawdown":
            df[
                "max_drawdown"
            ].min(),

        "mejor":
            df[
                "retorno"
            ].max(),

        "peor":
            df[
                "retorno"
            ].min()
    }


# ============================================================
# IMPRIMIR RESULTADO
# ============================================================

def imprimir_resultado(
    prioridad,
    horizonte,
    resumen
):

    print()

    print(
        "======================================"
    )

    print(
        f"   PRIORIDAD {prioridad} "
        f"| {horizonte} SESIONES"
    )

    print(
        "======================================"
    )

    print()


    if resumen is None:

        print(
            "Todavía no existen resultados "
            "maduros suficientes."
        )

        return


    print(
        f"Casos:                   "
        f"{resumen['casos']}"
    )


    print(
        f"Retorno medio:           "
        f"{resumen['retorno_medio']:+.2f}%"
    )


    print(
        f"Retorno mediana:         "
        f"{resumen['retorno_mediana']:+.2f}%"
    )


    print()


    print(
        f"SPY medio:               "
        f"{resumen['spy_medio']:+.2f}%"
    )


    print(
        f"Exceso medio vs SPY:     "
        f"{resumen['exceso_medio']:+.2f}pp"
    )


    print(
        f"Mediana exceso vs SPY:   "
        f"{resumen['exceso_mediana']:+.2f}pp"
    )


    print()


    print(
        f"% resultados positivos: "
        f"{resumen['positivas']:.1f}%"
    )


    print(
        f"% que baten SPY:         "
        f"{resumen['bate_spy']:.1f}%"
    )


    print()


    print(
        f"Subida máxima media:     "
        f"{resumen['max_subida_media']:+.2f}%"
    )


    print(
        f"Caída máxima media:      "
        f"{resumen['max_caida_media']:+.2f}%"
    )


    print(
        f"Drawdown medio:          "
        f"{resumen['drawdown_medio']:+.2f}%"
    )


    print(
        f"Peor drawdown:           "
        f"{resumen['peor_drawdown']:+.2f}%"
    )


    print()


    print(
        f"Mejor resultado:         "
        f"{resumen['mejor']:+.2f}%"
    )


    print(
        f"Peor resultado:          "
        f"{resumen['peor']:+.2f}%"
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
        "      PAPER SIMULATION V2"
    )

    print(
        "======================================"
    )

    print()


    # ========================================================
    # ASEGURAR DB
    # ========================================================

    inicializar_db()

    asegurar_columna_market_date()

    asegurar_columnas_sectoriales()

    asegurar_columnas_score_v3()

    asegurar_columnas_v4_reversal()

    asegurar_columnas_clasificacion()

    inicializar_tablas_paper()


    # ========================================================
    # SINCRONIZAR NUEVAS SEÑALES
    # ========================================================

    nuevas = 0

    for configuracion in ESTRATEGIAS:

        nuevas_estrategia = sincronizar_senales_paper(
            score_version=configuracion["score_version"],
            prioridades=configuracion["prioridades"],
            strategy=configuracion["strategy"]
        )

        nuevas += nuevas_estrategia

        print(
            f"Nuevas señales {configuracion['strategy']}: "
            f"{nuevas_estrategia}"
        )


    print(
        f"Nuevas señales paper guardadas: "
        f"{nuevas}"
    )


    # ========================================================
    # SEÑALES AÚN NO COMPLETAS
    # ========================================================

    senales = (
        obtener_senales_paper_incompletas()
    )


    print(
        f"Señales pendientes/parciales: "
        f"{len(senales)}"
    )


    if not senales:

        print(
            "No existen señales pendientes."
        )

    else:

        # ====================================================
        # SYMBOLS
        # ====================================================

        symbols = {
            senal[
                "symbol"
            ]
            for senal in senales
        }


        symbols.add(
            "SPY"
        )


        # ====================================================
        # RANGO HISTÓRICO
        # ====================================================

        primera_fecha = min(

            datetime.strptime(
                senal[
                    "market_date"
                ],
                "%Y-%m-%d"
            )

            for senal in senales
        )


        fecha_inicio = (
            primera_fecha
            - timedelta(
                days=5
            )
        )


        fecha_fin = (
            datetime.now()
            + timedelta(
                days=1
            )
        )


        # ====================================================
        # DESCARGAR
        # ====================================================

        print()


        df = descargar_historico(

            symbols,

            fecha_inicio,

            fecha_fin
        )


        if df.empty:

            print(
                "No se ha obtenido histórico."
            )

            return


        historicos = (
            preparar_historicos(
                df
            )
        )


        datos_spy = (
            historicos.get(
                "SPY"
            )
        )


        if datos_spy is None:

            raise ValueError(
                "No se han obtenido "
                "datos de SPY."
            )


        # ====================================================
        # MADURAR SEÑALES
        # ====================================================

        nuevos_resultados = 0


        print()
        print(
            "Evaluando señales maduras..."
        )


        for senal in senales:

            symbol = senal[
                "symbol"
            ]


            datos_activo = (
                historicos.get(
                    symbol
                )
            )


            if datos_activo is None:
                continue


            ya_calculados = (
                obtener_horizontes_paper(
                    senal[
                        "id"
                    ]
                )
            )


            horizontes_senal = (
                HORIZONTES
                if senal.get("variant", "BASE") == "BASE"
                else [5]
            )

            for horizonte in horizontes_senal:

                if horizonte in ya_calculados:
                    continue


                resultado = evaluar_senal(

                    senal,

                    datos_activo,

                    datos_spy,

                    horizonte
                )


                if resultado is None:
                    continue


                insertado = (
                    guardar_resultado_paper(
                        resultado
                    )
                )


                nuevos_resultados += (
                    insertado
                )


        print(
            f"Nuevos resultados maduros: "
            f"{nuevos_resultados}"
        )


    # ========================================================
    # RESUMEN TRACKING
    # ========================================================

    resumen_tracking = (
        obtener_resumen_paper()
    )


    print()

    print(
        "======================================"
    )

    print(
        "          PAPER TRACKING"
    )

    print(
        "======================================"
    )

    print()


    if resumen_tracking[
        "senales"
    ]:

        for fila in resumen_tracking[
            "senales"
        ]:

            print(
                f"{fila['strategy']:<8} | "
                f"{fila['variant']:<5} | "
                f"{fila['prioridad']:<3} | "
                f"{fila['estado']:<9} | "
                f"{fila['cantidad']:>4}"
            )


    print()

    print(
        "Resultados maduros:"
    )


    if resumen_tracking[
        "resultados"
    ]:

        for fila in resumen_tracking[
            "resultados"
        ]:

            print(
                f"{fila['strategy']:<8} | "
                f"{fila['variant']:<5} | "
                f"{fila['horizonte']:>2} sesiones: "
                f"{fila['cantidad']}"
            )

    else:

        print(
            "Todavía ninguno."
        )


    # ========================================================
    # PERFORMANCE ACUMULADA
    # ========================================================

    resultados_momentum = (
        obtener_resultados_paper(
            strategy="MOMENTUM"
        )
    )


    resultados_v4 = [

        resultado

        for resultado
        in resultados_momentum

        if resultado.get(
            "source_score_version"
        ) == "v4"
    ]


    resultados_v3 = [

        resultado

        for resultado
        in resultados_momentum

        if resultado.get(
            "source_score_version"
        ) == "v3"
    ]

    resultados_v4_base = [
        resultado
        for resultado in resultados_v4
        if resultado.get("variant", "BASE") == "BASE"
    ]

    resultados_v4_tp25 = [
        resultado
        for resultado in resultados_v4
        if resultado.get("variant") == "TP25"
    ]


    print(
        f"Resultados Momentum V4: {len(resultados_v4)} | "
        f"Historico V3 conservado: {len(resultados_v3)}"
    )


    for prioridad in PRIORIDADES:

        for horizonte in HORIZONTES:

            filtrados = [

                resultado

                for resultado
                in resultados_v4_base

                if (
                    resultado[
                        "prioridad"
                    ] == prioridad

                    and

                    resultado[
                        "horizonte"
                    ] == horizonte
                )
            ]


            resumen = (
                resumir_resultados(
                    filtrados
                )
            )


            imprimir_resultado(

                prioridad,

                horizonte,

                resumen
            )


    # ========================================================
    # A+ Y A COMBINADOS
    # ========================================================

    print()

    print(
        "======================================"
    )

    print(
        "        A+ + A COMBINADAS"
    )

    print(
        "======================================"
    )


    for horizonte in HORIZONTES:

        filtrados = [

            resultado

            for resultado
            in resultados_v4_base

            if (
                resultado[
                    "prioridad"
                ]
                in [
                    "A+",
                    "A"
                ]

                and

                resultado[
                    "horizonte"
                ]
                == horizonte
            )
        ]


        resumen = (
            resumir_resultados(
                filtrados
            )
        )


        imprimir_resultado(
            "A+/A",
            horizonte,
            resumen
        )

    print()
    print("======================================")
    print("        MOMENTUM V4 | TP25")
    print("======================================")

    for prioridad in PRIORIDADES:
        filtrados = [
            resultado
            for resultado in resultados_v4_tp25
            if resultado["prioridad"] == prioridad
        ]
        imprimir_resultado(
            prioridad,
            5,
            resumir_resultados(filtrados)
        )


    # ========================================================
    # REVERSAL V1
    # ========================================================

    print()
    print(
        "======================================"
    )
    print(
        "          REVERSAL V1"
    )
    print(
        "======================================"
    )

    resultados_reversal = obtener_resultados_paper(
        strategy="REVERSAL"
    )

    resultados_reversal_base = [
        resultado
        for resultado in resultados_reversal
        if resultado.get("variant", "BASE") == "BASE"
    ]

    resultados_reversal_tp10 = [
        resultado
        for resultado in resultados_reversal
        if resultado.get("variant") == "TP10"
    ]

    for horizonte in HORIZONTES:

        filtrados = [
            resultado
            for resultado in resultados_reversal_base
            if resultado["horizonte"] == horizonte
        ]

        imprimir_resultado(
            "REVERSAL A",
            horizonte,
            resumir_resultados(
                filtrados
            )
        )

    imprimir_resultado(
        "REVERSAL A | TP10",
        5,
        resumir_resultados(resultados_reversal_tp10)
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
        "Cada fila representa una señal diaria "
        "del radar, no una orden real."
    )

    print(
        "La entrada virtual se realiza en la "
        "apertura posterior a la señal."
    )

    print(
        f"Coste virtual aplicado a activo y SPY: "
        f"{COSTE_TOTAL_PCT:.2f}%."
    )

    print(
        "Los resultados históricos no garantizan "
        "rendimientos futuros."
    )


if __name__ == "__main__":

    main()
