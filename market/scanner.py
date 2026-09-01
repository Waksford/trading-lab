import pandas as pd
import requests

from io import StringIO

from market.indicators import (
    calcular_indicadores
)

from analysis.scorer import (
    interpretar_activo,
    calcular_score,
    clasificar_candidato,
    calcular_prioridad_estudio
)


# ============================================================
# OBTENER S&P 500
# ============================================================

def obtener_sp500():
    """
    Obtiene dinámicamente la lista
    de empresas del S&P 500.
    """

    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_500_companies"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/151.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    tablas = pd.read_html(
        StringIO(
            response.text
        )
    )

    sp500 = tablas[0]

    empresas = []

    for _, fila in sp500.iterrows():

        symbol = fila[
            "Symbol"
        ]

        # Algunos tickers usan clases con punto:
        # BRK.B, BF.B...
        #
        # Los omitimos temporalmente hasta
        # normalizarlos correctamente para Alpaca.

        if "." in symbol:

            print(
                f"Ticker especial omitido: "
                f"{symbol}"
            )

            continue

        empresas.append(
            {
                "symbol":
                    symbol,

                "empresa":
                    fila["Security"],

                "sector":
                    fila["GICS Sector"]
            }
        )

    return empresas


# ============================================================
# SCANNER S&P 500
# ============================================================

def escanear_mercado(
    df,
    empresas
):
    """
    Scanner antiguo del S&P 500.

    Se mantiene por compatibilidad.

    No utiliza todavía benchmark sectorial.
    """

    resultados = []

    empresas_info = {

        empresa["symbol"]:
            empresa

        for empresa in empresas
    }

    for symbol in df[
        "symbol"
    ].unique():

        try:

            datos = df[
                df["symbol"]
                == symbol
            ].copy()

            datos = datos.sort_values(
                "timestamp"
            )

            if len(datos) < 50:
                continue

            datos = calcular_indicadores(
                datos
            )

            ultimo = datos.iloc[-1]

            if (
                pd.isna(
                    ultimo["sma_20"]
                )
                or pd.isna(
                    ultimo["sma_50"]
                )
                or pd.isna(
                    ultimo["rsi_14"]
                )
                or pd.isna(
                    ultimo[
                        "volatility_20"
                    ]
                )
            ):
                continue

            analisis = interpretar_activo(
                ultimo
            )

            # V3 funciona también sin fuerza relativa,
            # gracias a los valores por defecto.

            score = calcular_score(
                ultimo,
                analisis
            )

            info = empresas_info.get(
                symbol,
                {
                    "empresa": symbol,
                    "sector":
                        "Desconocido"
                }
            )

            resultados.append(
                {
                    "symbol":
                        symbol,

                    "empresa":
                        info["empresa"],

                    "sector":
                        info["sector"],

                    "precio":
                        ultimo["close"],

                    "score":
                        score["total"],

                    "score_version":
                        score["version"],

                    "tendencia":
                        analisis[
                            "tendencia"
                        ],

                    "momentum":
                        analisis[
                            "momentum"
                        ],

                    "volatilidad":
                        analisis[
                            "volatilidad"
                        ],

                    "rsi":
                        ultimo[
                            "rsi_14"
                        ],

                    "volumen_relativo":
                        ultimo[
                            "relative_volume"
                        ],

                    "distancia_sma20":
                        ultimo[
                            "distance_sma20"
                        ],

                    "distancia_sma50":
                        ultimo[
                            "distance_sma50"
                        ]
                }
            )

        except Exception as e:

            print(
                f"Error analizando "
                f"{symbol}: {e}"
            )

    return sorted(
        resultados,
        key=lambda x: x[
            "score"
        ],
        reverse=True
    )


# ============================================================
# SCANNER FUERA DEL S&P 500
# ============================================================

def escanear_descubrimientos(
    df,
    metadata_activos,
    spy_return_20d,
    spy_return_60d,
    sectores_por_symbol,
    sector_benchmarks
):
    """
    Analiza empresas operativas fuera del S&P 500.

    Score V3:
    - tendencia
    - momentum
    - fuerza contra SPY
    - fuerza contra sector
    - riesgo
    - volumen

    También genera una clasificación humana
    para facilitar la interpretación.
    """

    resultados = []

    metadata = {
        activo["symbol"]: activo
        for activo in metadata_activos
    }


    for symbol in df["symbol"].unique():

        try:

            # =================================================
            # SOLO EMPRESAS DEL UNIVERSO
            #
            # Excluye:
            # - SPY
            # - XLK
            # - XLF
            # - XLV
            # - resto de ETFs sectoriales
            # =================================================

            if symbol not in metadata:
                continue


            datos = df[
                df["symbol"] == symbol
            ].copy()

            datos = datos.sort_values(
                "timestamp"
            )


            # =================================================
            # HISTÓRICO MÍNIMO
            # =================================================

            if len(datos) < 50:
                continue


            # =================================================
            # PRECIO MÍNIMO
            # =================================================

            precio_actual = (
                datos.iloc[-1]["close"]
            )

            if precio_actual < 5:
                continue


            # =================================================
            # INDICADORES
            # =================================================

            datos = calcular_indicadores(
                datos
            )

            ultimo = datos.iloc[-1]


            # =================================================
            # VALIDAR INDICADORES
            # =================================================

            if (
                pd.isna(
                    ultimo["sma_20"]
                )
                or pd.isna(
                    ultimo["sma_50"]
                )
                or pd.isna(
                    ultimo["rsi_14"]
                )
                or pd.isna(
                    ultimo["volatility_20"]
                )
                or pd.isna(
                    ultimo["return_20d"]
                )
                or pd.isna(
                    ultimo["return_60d"]
                )
            ):
                continue


            # =================================================
            # INTERPRETACIÓN TÉCNICA
            # =================================================

            analisis = interpretar_activo(
                ultimo
            )


            # =================================================
            # RENTABILIDAD ABSOLUTA
            # =================================================

            return_20d = float(
                ultimo["return_20d"]
            )

            return_60d = float(
                ultimo["return_60d"]
            )


            # =================================================
            # FUERZA CONTRA SPY
            # =================================================

            fuerza_20d = (
                return_20d
                - spy_return_20d
            )

            fuerza_60d = (
                return_60d
                - spy_return_60d
            )


            # =================================================
            # SECTOR
            # =================================================

            sector = (
                sectores_por_symbol.get(
                    symbol,
                    "Unknown"
                )
            )


            benchmark_sector = (
                sector_benchmarks.get(
                    sector
                )
            )


            sector_ticker = None

            fuerza_sector_20d = None

            fuerza_sector_60d = None


            if benchmark_sector is not None:

                sector_ticker = (
                    benchmark_sector[
                        "ticker"
                    ]
                )

                fuerza_sector_20d = (
                    return_20d
                    - benchmark_sector[
                        "return_20d"
                    ]
                )

                fuerza_sector_60d = (
                    return_60d
                    - benchmark_sector[
                        "return_60d"
                    ]
                )


            # =================================================
            # SCORE V3
            # =================================================

            score = calcular_score(
                ultimo,
                analisis,
                fuerza_20d,
                fuerza_60d,
                fuerza_sector_20d,
                fuerza_sector_60d
            )


            # =================================================
            # CLASIFICACIÓN HUMANA
            # =================================================

            clasificacion = (
                clasificar_candidato(
                    score=score,
                    analisis=analisis,
                    fuerza_20d=fuerza_20d,
                    fuerza_60d=fuerza_60d,
                    fuerza_sector_20d=(
                        fuerza_sector_20d
                    ),
                    fuerza_sector_60d=(
                        fuerza_sector_60d
                    )
                )
            )
            prioridad = calcular_prioridad_estudio(
                score=score,
                clasificacion=clasificacion,
                rsi=float(
                    ultimo["rsi_14"]
                ),
                distancia_sma20=float(
                    ultimo["distance_sma20"]
                ),
                distancia_sma50=float(
                    ultimo["distance_sma50"]
                ),
                fuerza_sector_20d=(
                    fuerza_sector_20d
                ),
                fuerza_sector_60d=(
                    fuerza_sector_60d
                )
            )

            # =================================================
            # METADATA
            # =================================================

            info = metadata.get(
                symbol,
                {}
            )


            # =================================================
            # RESULTADO
            # =================================================

            resultados.append(
                {

                    # -----------------------------------------
                    # IDENTIDAD
                    # -----------------------------------------

                    "symbol":
                        symbol,

                    "nombre":
                        info.get(
                            "nombre",
                            symbol
                        ),

                    "exchange":
                        info.get(
                            "exchange",
                            "N/A"
                        ),

                    "fractionable":
                        info.get(
                            "fractionable",
                            False
                        ),


                    # -----------------------------------------
                    # PRECIO
                    # -----------------------------------------

                    "precio":
                        precio_actual,


                    # -----------------------------------------
                    # SCORE V3
                    # -----------------------------------------

                    "score":
                        score["total"],

                    "score_version":
                        score["version"],

                    "score_tendencia":
                        score[
                            "tendencia"
                        ],

                    "score_momentum":
                        score[
                            "momentum"
                        ],

                    "score_fuerza":
                        score[
                            "fuerza_relativa"
                        ],

                    "score_sector":
                        score[
                            "sector"
                        ],

                    "score_riesgo":
                        score[
                            "riesgo"
                        ],

                    "score_volumen":
                        score[
                            "volumen"
                        ],

                    "penalizacion_relativa":
                        score[
                            "penalizacion_relativa"
                        ],


                    # -----------------------------------------
                    # INTERPRETACIÓN
                    # -----------------------------------------

                    "tendencia":
                        analisis[
                            "tendencia"
                        ],

                    "momentum":
                        analisis[
                            "momentum"
                        ],

                    "volatilidad":
                        analisis[
                            "volatilidad"
                        ],


                    # -----------------------------------------
                    # CLASIFICACIÓN HUMANA
                    # -----------------------------------------

                    "perfil":
                        clasificacion[
                            "perfil"
                        ],

                    "calidad":
                        clasificacion[
                            "calidad"
                        ],

                    "fortaleza_mercado":
                        clasificacion[
                            "fortaleza_mercado"
                        ],

                    "fortaleza_sector":
                        clasificacion[
                            "fortaleza_sector"
                        ],

                    "riesgo_clasificacion":
                        clasificacion[
                            "riesgo"
                        ],

                    "volumen_clasificacion":
                        clasificacion[
                            "volumen"
                        ],

                    "prioridad_estudio":
                        prioridad[
                            "prioridad"
                        ],

                    "motivo_prioridad":
                        prioridad[
                            "motivo_prioridad"
                        ],

                    "alertas_estudio":
                        prioridad[
                            "alertas"
                        ],
                    # -----------------------------------------
                    # INDICADORES
                    # -----------------------------------------

                    "rsi":
                        float(
                            ultimo[
                                "rsi_14"
                            ]
                        ),

                    "volumen_relativo":
                        float(
                            ultimo[
                                "relative_volume"
                            ]
                        ),

                    "distancia_sma20":
                        float(
                            ultimo[
                                "distance_sma20"
                            ]
                        ),

                    "distancia_sma50":
                        float(
                            ultimo[
                                "distance_sma50"
                            ]
                        ),


                    # -----------------------------------------
                    # RETORNOS
                    # -----------------------------------------

                    "return_20d":
                        return_20d,

                    "return_60d":
                        return_60d,


                    # -----------------------------------------
                    # FUERZA CONTRA SPY
                    # -----------------------------------------

                    "fuerza_20d":
                        fuerza_20d,

                    "fuerza_60d":
                        fuerza_60d,


                    # -----------------------------------------
                    # SECTOR
                    # -----------------------------------------

                    "sector":
                        sector,

                    "sector_benchmark":
                        sector_ticker,

                    "fuerza_sector_20d":
                        fuerza_sector_20d,

                    "fuerza_sector_60d":
                        fuerza_sector_60d
                }
            )


        except Exception as e:

            print(
                f"Error analizando "
                f"{symbol}: {e}"
            )


    # ========================================================
    # ORDENAR POR SCORE
    # ========================================================

    resultados = sorted(
        resultados,
        key=lambda x: x["score"],
        reverse=True
    )

    return resultados