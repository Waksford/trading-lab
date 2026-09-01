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

from datetime import (
    datetime,
    timedelta
)

from market.sectors import (
    SECTOR_ETF,
    obtener_etfs_sectoriales
)
import argparse
import os
import pandas as pd

from dotenv import load_dotenv

from market.scanner import (
    obtener_sp500,
    escanear_descubrimientos
)

from market.universe import (
    obtener_universo_usa
)

from market.indicators import (
    calcular_indicadores
)

from analysis.events import (
    detectar_eventos
)

from scoring.momentum_v4 import (
    calcular_score_v4,
    clasificar_prioridad_v4,
)

from scoring.reversal_v1 import (
    detectar_reversal_v1,
)

from refresh_analyst_consensus import (
    actualizar_analyst_consensus,
)

from database.db import (
    inicializar_db,
    inicializar_tabla_eventos,
    inicializar_tabla_benchmark,
    guardar_benchmark_spy,
    asegurar_columna_market_date,
    asegurar_columnas_sectoriales,
    asegurar_columnas_score_v3,
    asegurar_columnas_v4_reversal,
    guardar_scan,
    guardar_eventos,
    obtener_operating_company_symbols,
    obtener_resumen_asset_types,
    obtener_scan_times,
    obtener_sectores_operating_companies,
    obtener_scan_por_fecha,
    asegurar_columnas_clasificacion,
    existe_market_date
)


# ============================================================
# INICIO
# ============================================================

print()

print(
    "======================================"
)

print(
    "       INICIANDO TRADING RADAR"
)

print(
    "======================================"
)

print(
    "Fecha ejecución:",
    datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )
)

print()


# ============================================================
# CONFIGURACIÓN
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


# ============================================================
# BASE DE DATOS
# ============================================================

inicializar_db()

def obtener_argumentos():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--market-date",
        type=str,
        default=None,
        help=(
            "Reconstruye el radar usando datos "
            "disponibles hasta YYYY-MM-DD"
        )
    )

    return parser.parse_args()


args = obtener_argumentos()

market_date_objetivo = args.market_date
market_date_objetivo_fecha = None
modo_backfill = market_date_objetivo is not None


if modo_backfill:

    try:

        market_date_objetivo_fecha = (
            datetime.strptime(
                market_date_objetivo,
                "%Y-%m-%d"
            ).date()
        )

    except ValueError as exc:

        raise ValueError(
            "--market-date debe usar formato YYYY-MM-DD"
        ) from exc


    if market_date_objetivo_fecha > datetime.now().date():

        raise ValueError(
            "No se puede reconstruir una fecha futura."
        )


    print(
        "Modo BACKFILL activado: "
        f"{market_date_objetivo}"
    )


inicializar_tabla_eventos()

asegurar_columna_market_date()

asegurar_columnas_sectoriales()

asegurar_columnas_score_v3()

asegurar_columnas_v4_reversal()

inicializar_tabla_benchmark()

asegurar_columnas_clasificacion()

# ============================================================
# CLIENTE ALPACA
# ============================================================

client = StockHistoricalDataClient(
    API_KEY,
    SECRET_KEY
)


# ============================================================
# FECHAS
# ============================================================

if modo_backfill:

    # StockBarsRequest usa 'end' como limite superior.
    # Sumamos un dia para incluir completamente la vela diaria
    # correspondiente a market_date_objetivo.
    fecha_fin = (
        datetime.combine(
            market_date_objetivo_fecha,
            datetime.min.time()
        )
        + timedelta(days=1)
    )

else:

    fecha_fin = datetime.now()


fecha_inicio = (
    fecha_fin
    - timedelta(days=120)
)


print(
    "Rango historico: "
    f"{fecha_inicio.date()} -> "
    f"{fecha_fin.date()}"
)


# ============================================================
# S&P 500
# ============================================================

print(
    "\n======================================"
)

print(
    "          CARGANDO S&P 500"
)

print(
    "======================================\n"
)


empresas_sp500 = obtener_sp500()


symbols_sp500 = {

    empresa["symbol"]

    for empresa in empresas_sp500
}


print(
    f"Empresas S&P 500: "
    f"{len(symbols_sp500)}"
)


# ============================================================
# UNIVERSO USA
# ============================================================

print(
    "\n======================================"
)

print(
    "       CARGANDO MERCADO USA"
)

print(
    "======================================\n"
)


universo_usa = obtener_universo_usa(
    API_KEY,
    SECRET_KEY
)


print(
    f"Activos USA negociables: "
    f"{len(universo_usa)}"
)


# ============================================================
# EMPRESAS OPERATIVAS
# ============================================================

operating_symbols = (
    obtener_operating_company_symbols()
)


sectores_por_symbol = (
    obtener_sectores_operating_companies()
)


resumen_asset_types = (
    obtener_resumen_asset_types()
)


print(
    f"Empresas con sector conocido: "
    f"{len(sectores_por_symbol)}"
)


print(
    "\n======================================"
)

print(
    "       CLASIFICACIÓN DE ACTIVOS"
)

print(
    "======================================\n"
)


for tipo, cantidad in (
    resumen_asset_types.items()
):

    print(
        f"{tipo:<22} "
        f"{cantidad:>5}"
    )


print(
    f"\nEmpresas operativas disponibles: "
    f"{len(operating_symbols)}"
)


# ============================================================
# FUERA DEL S&P 500
# SOLO EMPRESAS OPERATIVAS
# ============================================================

universo_fuera_sp500 = [

    activo

    for activo in universo_usa

    if (
        activo["symbol"]
        not in symbols_sp500

        and

        activo["symbol"]
        in operating_symbols
    )
]


print(
    f"Empresas operativas fuera del S&P 500: "
    f"{len(universo_fuera_sp500)}"
)


# ============================================================
# TODO EL UNIVERSO
# ============================================================

universo_prueba = (
    universo_fuera_sp500
)


symbols_prueba = [

    activo["symbol"]

    for activo in universo_prueba
]


print(
    f"\nAnalizando "
    f"{len(symbols_prueba)} activos..."
)


# ============================================================
# SÍMBOLOS A DESCARGAR
# ============================================================

symbols_descarga = (
    symbols_prueba.copy()
)


# ============================================================
# SPY - BENCHMARK GENERAL
# ============================================================

if "SPY" not in symbols_descarga:

    symbols_descarga.append(
        "SPY"
    )


# ============================================================
# ETFs SECTORIALES
# ============================================================

etfs_sectoriales = (
    obtener_etfs_sectoriales()
)


for ticker in etfs_sectoriales:

    if ticker not in symbols_descarga:

        symbols_descarga.append(
            ticker
        )


print(
    f"Benchmarks sectoriales añadidos: "
    f"{len(etfs_sectoriales)}"
)


# ============================================================
# DESCARGA POR BLOQUES
# ============================================================

TAMANO_BLOQUE = 100


dataframes = []


for inicio in range(
    0,
    len(symbols_descarga),
    TAMANO_BLOQUE
):

    bloque = symbols_descarga[
        inicio:
        inicio + TAMANO_BLOQUE
    ]


    numero_bloque = (
        inicio
        // TAMANO_BLOQUE
    ) + 1


    total_bloques = (
        len(symbols_descarga)
        + TAMANO_BLOQUE
        - 1
    ) // TAMANO_BLOQUE


    print(
        f"Descargando bloque "
        f"{numero_bloque}/"
        f"{total_bloques} "
        f"({len(bloque)} activos)..."
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
            bars.df
            .reset_index()
        )


        if not df_bloque.empty:

            dataframes.append(
                df_bloque
            )


    except Exception as e:

        print(
            f"Error descargando bloque: "
            f"{e}"
        )


# ============================================================
# UNIR DATOS
# ============================================================

if not dataframes:

    raise ValueError(
        "No se han obtenido "
        "datos de mercado."
    )


df = pd.concat(
    dataframes,
    ignore_index=True
)


# ============================================================
# CORTE POINT-IN-TIME PARA BACKFILL
# ============================================================

if modo_backfill:

    df[
        "timestamp"
    ] = pd.to_datetime(
        df[
            "timestamp"
        ]
    )


    df = df[
        df[
            "timestamp"
        ].dt.date
        <= market_date_objetivo_fecha
    ].copy()


    if df.empty:

        raise ValueError(
            "El backfill no ha recibido velas "
            f"hasta {market_date_objetivo}."
        )


print(
    f"\nSímbolos con datos: "
    f"{df['symbol'].nunique()}"
)


print(
    f"Velas descargadas: "
    f"{len(df)}"
)


# ============================================================
# EMPRESAS CON HISTÓRICO
# ============================================================

simbolos_empresas_con_historico = (

    df[
        df["symbol"].isin(
            symbols_prueba
        )
    ]["symbol"]

    .nunique()
)


# ============================================================
# DATOS DE SPY
# ============================================================

datos_spy = df[
    df["symbol"] == "SPY"
].copy()


if datos_spy.empty:

    raise ValueError(
        "No se han recibido "
        "datos de SPY."
    )


datos_spy = (
    datos_spy
    .sort_values(
        "timestamp"
    )
)


datos_spy = calcular_indicadores(
    datos_spy
)


ultimo_spy = (
    datos_spy
    .iloc[-1]
)


# ============================================================
# FECHA REAL DE SESIÓN
# ============================================================

ultima_fecha_spy = (
    datos_spy
    .iloc[-1]["timestamp"]
)


market_date = (
    ultima_fecha_spy
    .date()
    .isoformat()
)


# ============================================================
# VALIDACION DE SESION HISTORICA
# ============================================================

if modo_backfill:

    if market_date != market_date_objetivo:

        raise ValueError(
            "La fecha solicitada no coincide con una "
            "sesion de mercado disponible. "
            f"Solicitada: {market_date_objetivo} | "
            f"Ultima vela SPY: {market_date}"
        )


    print(
        "Backfill validado con SPY: "
        f"{market_date}"
    )


# ============================================================
# DATOS BENCHMARK SPY
# ============================================================

spy_precio = float(
    ultimo_spy["close"]
)


spy_return_20d = float(
    ultimo_spy["return_20d"]
)


spy_return_60d = float(
    ultimo_spy["return_60d"]
)


# ============================================================
# BENCHMARKS SECTORIALES
# ============================================================

sector_benchmarks = {}


print()

print(
    "======================================"
)

print(
    "       BENCHMARKS SECTORIALES"
)

print(
    "======================================"
)

print()


for sector, ticker in (
    SECTOR_ETF.items()
):

    datos_sector = df[
        df["symbol"]
        == ticker
    ].copy()


    if datos_sector.empty:

        print(
            f"{sector:<26} "
            f"{ticker:<5} SIN DATOS"
        )

        continue


    datos_sector = (
        datos_sector
        .sort_values(
            "timestamp"
        )
    )


    datos_sector = (
        calcular_indicadores(
            datos_sector
        )
    )


    ultimo_sector = (
        datos_sector.iloc[-1]
    )


    return_20d = float(
        ultimo_sector[
            "return_20d"
        ]
    )


    return_60d = float(
        ultimo_sector[
            "return_60d"
        ]
    )


    sector_benchmarks[
        sector
    ] = {

        "ticker":
            ticker,

        "return_20d":
            return_20d,

        "return_60d":
            return_60d
    }


    print(
        f"{sector:<26} | "
        f"{ticker:<4} | "
        f"20D {return_20d:+6.2f}% | "
        f"60D {return_60d:+6.2f}%"
    )


# ============================================================
# BENCHMARK SPY
# ============================================================

print(
    "\n======================================"
)

print(
    "          BENCHMARK SPY"
)

print(
    "======================================\n"
)


print(
    f"Última sesión disponible: "
    f"{market_date}"
)


print(
    f"Precio SPY: "
    f"${spy_precio:.2f}"
)


print(
    f"Rentabilidad 20 sesiones: "
    f"{spy_return_20d:+.2f}%"
)


print(
    f"Rentabilidad 60 sesiones: "
    f"{spy_return_60d:+.2f}%"
)


# ============================================================
# SCANNER
# ============================================================

print(
    "\nAnalizando indicadores..."
)


ranking = escanear_descubrimientos(

    df,

    universo_prueba,

    spy_return_20d,

    spy_return_60d,

    sectores_por_symbol,

    sector_benchmarks
)


# ============================================================
# MOMENTUM V4 + REVERSAL V1
# ============================================================
#
# El scanner sigue calculando indicadores y clasificaciones
# auxiliares. A partir de aqui Momentum V4 pasa a ser el score
# tecnico principal que se guarda en scans.
#
# Reversal V1 es una estrategia paralela. No modifica el score
# momentum ni la prioridad principal.

for activo in ranking:

    resultado_v4 = calcular_score_v4(

        tendencia=activo.get("tendencia"),

        rsi=activo.get("rsi"),

        fuerza_20d=activo.get("fuerza_20d"),

        fuerza_60d=activo.get("fuerza_60d"),

        fuerza_sector_20d=activo.get(
            "fuerza_sector_20d"
        ),

        fuerza_sector_60d=activo.get(
            "fuerza_sector_60d"
        ),

        distancia_sma20=activo.get(
            "distancia_sma20"
        ),

        volumen_relativo=activo.get(
            "volumen_relativo"
        ),

        volatilidad=activo.get(
            "volatilidad"
        )
    )


    score_v4 = int(
        resultado_v4.get(
            "total",
            0
        )
    )


    prioridad_v4 = clasificar_prioridad_v4(
        score_v4
    )


    # --------------------------------------------------------
    # SCORE MOMENTUM OFICIAL
    # --------------------------------------------------------

    activo["score"] = score_v4

    activo["score_version"] = "v4"

    activo["prioridad_estudio"] = (
        prioridad_v4
    )


    activo["score_tendencia"] = (
        resultado_v4.get(
            "tendencia",
            0
        )
    )


    activo["score_momentum"] = (
        resultado_v4.get(
            "momentum",
            0
        )
    )


    activo["score_fuerza"] = (
        resultado_v4.get(
            "fuerza_relativa",
            0
        )
    )


    activo["score_sector"] = (
        resultado_v4.get(
            "sector",
            0
        )
    )


    activo["score_continuacion"] = (
        resultado_v4.get(
            "continuacion",
            0
        )
    )


    activo["score_volumen"] = (
        resultado_v4.get(
            "volumen",
            0
        )
    )


    # En V4 el riesgo es un overlay y no concede puntos.

    activo["score_riesgo"] = 0

    activo["penalizacion_relativa"] = 0


    activo["motivo_prioridad"] = (
        f"Momentum V4 {score_v4}/100 | "
        f"prioridad {prioridad_v4}"
    )


    # --------------------------------------------------------
    # REVERSAL V1
    # --------------------------------------------------------

    reversal = detectar_reversal_v1(

        score_v4=score_v4,

        rsi=activo.get(
            "rsi"
        ),

        distancia_sma20=activo.get(
            "distancia_sma20"
        ),

        volatilidad=activo.get(
            "volatilidad"
        )
    )


    activo["reversal_candidate"] = (
        1
        if reversal.get(
            "candidate"
        )
        else 0
    )


    activo["reversal_version"] = (
        reversal.get(
            "version"
        )
    )


    activo["reversal_priority"] = (
        reversal.get(
            "priority"
        )
    )


    activo["reversal_reason"] = (
        reversal.get(
            "reason"
        )
    )


# El scanner entregaba el ranking ordenado con el score anterior.
# Lo reordenamos usando Momentum V4.

ranking = sorted(

    ranking,

    key=lambda activo: activo.get(
        "score",
        0
    ),

    reverse=True
)


print(
    f"Activos que han pasado "
    f"los filtros básicos: "
    f"{len(ranking)}"
)


# ============================================================
# BENCHMARK SPY EN SQLITE
# ============================================================

benchmark_guardado = guardar_benchmark_spy(

    market_date,

    spy_precio,

    spy_return_20d,

    spy_return_60d
)


# ============================================================
# GUARDAR SNAPSHOT
# ============================================================

nuevo_scan_guardado = False


if existe_market_date(
    market_date,
    score_version="v4"
):

    print()


    print(
        f"La sesión {market_date} "
        f"ya existe en SQLite."
    )


    print(
        "No se guardará un "
        "snapshot duplicado."
    )


    registros_guardados = 0


else:

    scan_time_override = (
        f"{market_date}T23:59:59"
        if modo_backfill
        else None
    )


    registros_guardados = guardar_scan(
        ranking,
        market_date,
        scan_time_override=scan_time_override
    )


    nuevo_scan_guardado = True


    print()


    print(
        f"Sesión guardada: "
        f"{market_date}"
    )


    print(
        f"Registros guardados en SQLite: "
        f"{registros_guardados}"
    )


print(
    f"Benchmark SPY: "
    f"{'guardado' if benchmark_guardado else 'ya existía'}"
)


# ============================================================
# YAHOO ANALYST CONSENSUS
# ============================================================

if not modo_backfill:

    try:

        actualizar_analyst_consensus()

    except Exception as exc:

        print(
            "\nYahoo Analyst Consensus: "
            f"ERROR - {exc}"
        )

        print(
            "El radar principal se ha generado correctamente."
        )


else:

    print(
        "\nYahoo Analyst Consensus: omitido en modo backfill."
    )


# ============================================================
# EVENTOS
# ============================================================

if nuevo_scan_guardado and not modo_backfill:

    scan_times = obtener_scan_times(
        limite=2
    )


    if len(scan_times) >= 2:

        scan_actual = (
            obtener_scan_por_fecha(
                scan_times[0]
            )
        )


        scan_anterior = (
            obtener_scan_por_fecha(
                scan_times[1]
            )
        )


        eventos = detectar_eventos(
            scan_actual,
            scan_anterior
        )


        eventos_guardados = (
            guardar_eventos(
                eventos
            )
        )


        print(
            "\n======================================"
        )

        print(
            "          EVENTOS DEL RADAR"
        )

        print(
            "======================================\n"
        )


        if not eventos:

            print(
                "Sin cambios importantes "
                "desde el último scan."
            )


        else:

            for evento in eventos[:20]:

                icono = {

                    "NUEVO_CANDIDATO":
                        "NUEVO",

                    "ACELERANDO":
                        "SUBE",

                    "FUERZA_CRECIENTE":
                        "FUERZA",

                    "DETERIORO":
                        "ALERTA"

                }.get(
                    evento["tipo"],
                    "INFO"
                )


                print(
                    f"[{icono}] "
                    f"{evento['mensaje']}"
                )


            print(
                f"\nEventos detectados: "
                f"{len(eventos)}"
            )


            print(
                f"Eventos guardados: "
                f"{eventos_guardados}"
            )


    else:

        print(
            "\nTodavía no existe "
            "una sesión anterior "
            "para comparar."
        )


else:

    print()


    if modo_backfill and nuevo_scan_guardado:

        print(
            "No se calculan eventos durante el backfill "
            "para evitar comparar sesiones fuera de orden."
        )

    else:

        print(
            "No se calculan eventos "
            "porque no hay una sesión nueva."
        )


# ============================================================
# TOP 20
# ============================================================

print(
    "\n======================================"
)

print(
    "      TOP 20 DESCUBRIMIENTOS"
)

print(
    "======================================\n"
)


for posicion, activo in enumerate(
    ranking[:20],
    start=1
):

    print(

        f"{posicion:>2}. "

        f"{activo['symbol']:<7} | "

        f"{activo['score']:>3}/100 | "

        f"{activo['tendencia']:<15} | "

        f"RSI "
        f"{activo['rsi']:>5.1f} | "

        f"RS20 "
        f"{activo['fuerza_20d']:+6.1f}pp | "

        f"RS60 "
        f"{activo['fuerza_60d']:+6.1f}pp | "

        f"${activo['precio']:>8.2f} | "

        f"{activo['nombre']}"
    )


    # --------------------------------------------------------
    # SECTOR
    # --------------------------------------------------------

    sector_20 = activo.get(
        "fuerza_sector_20d"
    )


    sector_60 = activo.get(
        "fuerza_sector_60d"
    )


    if (
        sector_20 is not None
        and sector_60 is not None
    ):

        print(
            f"      Sector: "
            f"{activo.get('sector', 'Unknown')} "
            f"({activo.get('sector_benchmark', 'N/A')}) | "
            f"S20 {sector_20:+.1f}pp | "
            f"S60 {sector_60:+.1f}pp"
        )


    # --------------------------------------------------------
    # DESGLOSE SCORE
    # --------------------------------------------------------

    if activo.get("score_version") == "v4":

        print(
            f"      Score v4: "
            f"T {activo.get('score_tendencia', 0)}/20 | "
            f"M {activo.get('score_momentum', 0)}/20 | "
            f"SPY {activo.get('score_fuerza', 0)}/20 | "
            f"SEC {activo.get('score_sector', 0)}/10 | "
            f"CONT {activo.get('score_continuacion', 0)}/20 | "
            f"V {activo.get('score_volumen', 0)}/10"
        )

    else:

        # Compatibilidad visual con scans antiguos V3.
        print(
            f"      Score "
            f"{activo.get('score_version', 'N/A')}: "
            f"T {activo.get('score_tendencia', 0)}/25 | "
            f"M {activo.get('score_momentum', 0)}/15 | "
            f"SPY {activo.get('score_fuerza', 0)}/20 | "
            f"SEC {activo.get('score_sector', 0)}/15 | "
            f"R {activo.get('score_riesgo', 0)}/15 | "
            f"V {activo.get('score_volumen', 0)}/10 | "
            f"P -{activo.get('penalizacion_relativa', 0)}"
        )
    # --------------------------------------------------------
    # CALIFICACION
    # --------------------------------------------------------
    print(
        f"      Perfil: "
        f"{activo.get('perfil', 'N/A')} | "
        f"Calidad: "
        f"{activo.get('calidad', 'N/A')} | "
        f"Mercado: "
        f"{activo.get('fortaleza_mercado', 'N/A')} | "
        f"Sector: "
        f"{activo.get('fortaleza_sector', 'N/A')} | "
        f"Riesgo: "
        f"{activo.get('riesgo_clasificacion', 'N/A')} | "
        f"Volumen: "
        f"{activo.get('volumen_clasificacion', 'N/A')}"
    )
    alertas = activo.get(
        "alertas_estudio",
        []
    )

    alertas_texto = (
        ", ".join(alertas)
        if alertas
        else "NINGUNA"
    )

    print(
        f"      Prioridad: "
        f"{activo.get('prioridad_estudio', 'N/A')} | "
        f"Alertas: {alertas_texto}"
    )

# ============================================================
# TOP REVERSAL V1
# ============================================================

reversals = [

    activo

    for activo in ranking

    if activo.get(
        "reversal_candidate"
    ) == 1
]


reversals = sorted(

    reversals,

    key=lambda activo: (

        activo.get(
            "reversal_priority"
        ) == "A",

        -abs(
            float(
                activo.get(
                    "distancia_sma20",
                    0
                )
                or 0
            )
        ),

        -float(
            activo.get(
                "rsi",
                100
            )
            or 100
        )
    ),

    reverse=True
)


print(
    "\n======================================"
)

print(
    "          TOP REVERSAL V1"
)

print(
    "======================================\n"
)


if not reversals:

    print(
        "No se han detectado candidatos Reversal V1."
    )


else:

    for posicion, activo in enumerate(
        reversals[:20],
        start=1
    ):

        print(
            f"{posicion:>2}. "
            f"{activo['symbol']:<7} | "
            f"Momentum {activo.get('score', 0):>3}/100 | "
            f"RSI {activo.get('rsi', 0):>5.1f} | "
            f"SMA20 {activo.get('distancia_sma20', 0):>+6.1f}% | "
            f"Volatilidad {activo.get('volatilidad', 'N/A'):<9} | "
            f"${activo.get('precio', 0):>8.2f} | "
            f"{activo.get('nombre', '')}"
        )

        print(
            f"      Reversal: "
            f"{activo.get('reversal_priority', 'N/A')} | "
            f"Version: {activo.get('reversal_version', 'N/A')}"
        )

        print(
            f"      Motivo: "
            f"{activo.get('reversal_reason', 'N/A')}"
        )


# ============================================================
# WATCHLIST ALCISTA
# ============================================================

alcistas = [

    activo

    for activo in ranking

    if activo["tendencia"]
    in [
        "FUERTE ALCISTA",
        "ALCISTA"
    ]

    and 50 <= activo[
        "rsi"
    ] < 70

    and activo.get(
        "prioridad_estudio"
    ) in [
        "A+",
        "A",
        "B"
    ]
]


print(
    "\n======================================"
)

print(
    "       WATCHLIST ALCISTA"
)

print(
    "======================================\n"
)


if not alcistas:

    print(
        "No se han encontrado candidatos."
    )


else:

    for posicion, activo in enumerate(
        alcistas[:20],
        start=1
    ):

        print(

            f"{posicion:>2}. "

            f"{activo['symbol']:<7} | "

            f"{activo['score']:>3}/100 | "

            f"{activo['exchange']:<8} | "

            f"RSI "
            f"{activo['rsi']:>5.1f} | "

            f"RS20 "
            f"{activo['fuerza_20d']:+6.1f}pp | "

            f"RS60 "
            f"{activo['fuerza_60d']:+6.1f}pp | "

            f"${activo['precio']:>8.2f} | "

            f"{activo['nombre']}"
        )


        sector_20 = activo.get(
            "fuerza_sector_20d"
        )


        sector_60 = activo.get(
            "fuerza_sector_60d"
        )


        if (
            sector_20 is not None
            and sector_60 is not None
        ):

            print(
                f"      Sector: "
                f"{activo.get('sector', 'Unknown')} "
                f"({activo.get('sector_benchmark', 'N/A')}) | "
                f"S20 {sector_20:+.1f}pp | "
                f"S60 {sector_60:+.1f}pp"
            )


        print(
            f"      Score "
            f"{activo.get('score_version', 'v4')}: "
            f"T {activo.get('score_tendencia', 0)}/20 | "
            f"M {activo.get('score_momentum', 0)}/20 | "
            f"SPY {activo.get('score_fuerza', 0)}/20 | "
            f"SEC {activo.get('score_sector', 0)}/10 | "
            f"CONT {activo.get('score_continuacion', 0)}/20 | "
            f"V {activo.get('score_volumen', 0)}/10"
        )


# ============================================================
# RESUMEN
# ============================================================

print(
    "\n======================================"
)

print(
    "              RESUMEN"
)

print(
    "======================================\n"
)


print(
    f"Sesión de mercado:                 "
    f"{market_date}"
)


print(
    f"Precio SPY:                        "
    f"${spy_precio:.2f}"
)


print(
    f"Posibles acciones ordinarias USA: "
    f"{len(universo_usa)}"
)


print(
    f"Empresas operativas USA:          "
    f"{len(operating_symbols)}"
)


print(
    f"Operativas fuera S&P 500:          "
    f"{len(universo_fuera_sp500)}"
)


print(
    f"Analizados esta ejecución:         "
    f"{len(symbols_prueba)}"
)


print(
    f"Con histórico disponible:          "
    f"{simbolos_empresas_con_historico}"
)


print(
    f"Tras filtros básicos:              "
    f"{len(ranking)}"
)


print(
    f"Candidatos alcistas:               "
    f"{len(alcistas)}"
)


print(
    f"Registros nuevos en SQLite:        "
    f"{registros_guardados}"
)


print(
    f"Benchmark SPY nuevo:               "
    f"{'sí' if benchmark_guardado else 'no'}"
)


print(
    f"Benchmarks sectoriales disponibles:"
    f" {len(sector_benchmarks)}/"
    f"{len(SECTOR_ETF)}"
)


print(
    "Score activo:                      "
    "v4"
)
