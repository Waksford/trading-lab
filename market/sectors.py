import requests
import csv

from io import StringIO


# ============================================================
# CONFIGURACIÓN SEC
# ============================================================

SEC_HEADERS = {
    "User-Agent": (
        "TradingRadar/1.0 "
        "jaimealguacilplaza@gmail.com"
    )
}


# ============================================================
# SIC -> SECTOR
# ============================================================

def sic_a_sector(sic):
    """
    Convierte un código SIC de SEC
    a uno de nuestros sectores amplios.

    No pretende replicar GICS exactamente.
    Es una clasificación práctica para
    nuestro radar.
    """

    if sic is None:
        return "Unknown"

    try:
        sic = int(sic)

    except (TypeError, ValueError):
        return "Unknown"


    # ========================================================
    # OVERRIDES ESPECÍFICOS
    #
    # IMPORTANTE:
    # Estos deben ir ANTES de los rangos amplios.
    # ========================================================


    # --------------------------------------------------------
    # HEALTH CARE
    # FARMACÉUTICAS / BIOTECH / DIAGNÓSTICO
    # --------------------------------------------------------

    if 2833 <= sic <= 2836:
        return "Health Care"


    # --------------------------------------------------------
    # HEALTH CARE
    # DISPOSITIVOS / EQUIPAMIENTO MÉDICO
    # --------------------------------------------------------

    if 3841 <= sic <= 3845:
        return "Health Care"


    # --------------------------------------------------------
    # HEALTH CARE
    # SERVICIOS MÉDICOS
    # --------------------------------------------------------

    if 8000 <= sic <= 8099:
        return "Health Care"


    # ========================================================
    # AGRICULTURA
    # ========================================================

    if 100 <= sic <= 999:
        return "Consumer Staples"


    # ========================================================
    # MINERÍA
    # ========================================================

    if 1000 <= sic <= 1499:

        # Petróleo y gas
        if 1300 <= sic <= 1399:
            return "Energy"

        return "Materials"


    # ========================================================
    # CONSTRUCCIÓN
    # ========================================================

    if 1500 <= sic <= 1799:
        return "Industrials"


    # ========================================================
    # MANUFACTURING
    # ========================================================

    if 2000 <= sic <= 3999:

        # ----------------------------------------------------
        # Alimentación / tabaco
        # ----------------------------------------------------

        if 2000 <= sic <= 2199:
            return "Consumer Staples"


        # ----------------------------------------------------
        # Textil / ropa / muebles
        # ----------------------------------------------------

        if 2200 <= sic <= 2599:
            return "Consumer Discretionary"


        # ----------------------------------------------------
        # Papel / químicos / materiales
        #
        # IMPORTANTE:
        # 2833-2836 ya fueron capturados
        # arriba como Health Care.
        # ----------------------------------------------------

        if 2600 <= sic <= 2899:
            return "Materials"


        # ----------------------------------------------------
        # Petróleo
        # ----------------------------------------------------

        if 2900 <= sic <= 2999:
            return "Energy"


        # ----------------------------------------------------
        # Caucho / cuero
        # ----------------------------------------------------

        if 3000 <= sic <= 3199:
            return "Materials"


        # ----------------------------------------------------
        # Piedra / metal
        # ----------------------------------------------------

        if 3200 <= sic <= 3499:
            return "Materials"


        # ----------------------------------------------------
        # Maquinaria
        # ----------------------------------------------------

        if 3500 <= sic <= 3599:
            return "Industrials"


        # ----------------------------------------------------
        # Electrónica / semiconductores
        # ----------------------------------------------------

        if 3600 <= sic <= 3699:
            return "Technology"


        # ----------------------------------------------------
        # Transporte / vehículos / componentes
        # ----------------------------------------------------

        if 3700 <= sic <= 3799:
            return "Consumer Discretionary"


        # ----------------------------------------------------
        # Instrumentación
        #
        # 3841-3845 ya fueron capturados como Health Care.
        # ----------------------------------------------------

        if 3800 <= sic <= 3899:
            return "Technology"


        return "Industrials"


    # ========================================================
    # TRANSPORTE / COMUNICACIONES / UTILITIES
    # ========================================================

    if 4000 <= sic <= 4999:

        # ----------------------------------------------------
        # Transporte
        # ----------------------------------------------------

        if 4000 <= sic <= 4799:
            return "Industrials"


        # ----------------------------------------------------
        # Telecom
        # ----------------------------------------------------

        if 4800 <= sic <= 4899:
            return "Communication Services"


        # ----------------------------------------------------
        # Utilities
        # ----------------------------------------------------

        if 4900 <= sic <= 4999:
            return "Utilities"


    # ========================================================
    # COMERCIO MAYORISTA
    # ========================================================

    if 5000 <= sic <= 5199:
        return "Industrials"


    # ========================================================
    # RETAIL
    # ========================================================

    if 5200 <= sic <= 5999:

        # ----------------------------------------------------
        # Alimentación
        # ----------------------------------------------------

        if 5400 <= sic <= 5499:
            return "Consumer Staples"


        # ----------------------------------------------------
        # Restaurantes
        # ----------------------------------------------------

        if 5800 <= sic <= 5899:
            return "Consumer Discretionary"


        return "Consumer Discretionary"


    # ========================================================
    # FINANZAS / SEGUROS / REAL ESTATE
    # ========================================================

    if 6000 <= sic <= 6799:

        # ----------------------------------------------------
        # Real estate
        # ----------------------------------------------------

        if 6500 <= sic <= 6599:
            return "Real Estate"


        # ----------------------------------------------------
        # REIT
        # ----------------------------------------------------

        if 6798 <= sic <= 6799:
            return "Real Estate"


        # ----------------------------------------------------
        # SPAC / BLANK CHECK
        #
        # Seguimos devolviendo Financials aquí porque
        # asset_type=SPAC se resolverá en classify_assets.py.
        # No queremos mezclar clasificación sectorial
        # con tipo de instrumento.
        # ----------------------------------------------------

        if sic == 6770:
            return "Financials"


        return "Financials"


    # ========================================================
    # SERVICIOS
    # ========================================================

    if 7000 <= sic <= 8999:

        # ----------------------------------------------------
        # Hoteles
        # ----------------------------------------------------

        if 7000 <= sic <= 7099:
            return "Consumer Discretionary"


        # ----------------------------------------------------
        # Servicios empresariales
        # ----------------------------------------------------

        if 7300 <= sic <= 7399:

            # Software / informática
            if 7370 <= sic <= 7379:
                return "Technology"

            return "Industrials"


        # ----------------------------------------------------
        # Automoción / reparación
        # ----------------------------------------------------

        if 7500 <= sic <= 7599:
            return "Consumer Discretionary"


        # ----------------------------------------------------
        # Cine / entretenimiento
        # ----------------------------------------------------

        if 7800 <= sic <= 7999:
            return "Communication Services"


        # ----------------------------------------------------
        # Salud
        # ----------------------------------------------------

        if 8000 <= sic <= 8099:
            return "Health Care"


        # ----------------------------------------------------
        # Ingeniería / servicios profesionales
        # ----------------------------------------------------

        if 8700 <= sic <= 8799:
            return "Industrials"


        return "Industrials"


    return "Unknown"


# ============================================================
# DESCARGAR MAPA TICKER -> CIK
# ============================================================

def obtener_mapa_sec():
    """
    Descarga el fichero oficial SEC que relaciona:

    ticker -> CIK -> nombre
    """

    url = (
        "https://www.sec.gov/files/"
        "company_tickers.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    datos = response.json()

    mapa = {}

    for empresa in datos.values():

        ticker = (
            empresa["ticker"]
            .upper()
        )

        mapa[ticker] = {

            "cik": str(
                empresa["cik_str"]
            ).zfill(10),

            "nombre_sec": (
                empresa["title"]
            )
        }

    return mapa


# ============================================================
# OBTENER METADATA SEC
# ============================================================

def obtener_metadata_sec(cik):
    """
    Obtiene la metadata de una compañía
    mediante su CIK.
    """

    url = (
        "https://data.sec.gov/"
        f"submissions/CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    datos = response.json()

    sic = datos.get(
        "sic"
    )

    sic_description = datos.get(
        "sicDescription"
    )

    return {
        "sic": sic,

        "sic_description":
            sic_description,

        "sector":
            sic_a_sector(sic)
    }


# ============================================================
# DATASETS SEC DE VEHÍCULOS DE INVERSIÓN
# ============================================================

BDC_URL = (
    "https://www.sec.gov/files/investment/data/other/"
    "business-development-company-report/"
    "business-development-company-2026.csv"
)


CEF_URL = (
    "https://www.sec.gov/files/investment/data/other/"
    "closed-end-fund-information/"
    "closed-end-investment-company-2026.csv"
)


# ============================================================
# NORMALIZAR CIK
# ============================================================

def normalizar_cik(cik):
    """
    Convierte cualquier formato de CIK
    a string de 10 dígitos.
    """

    if cik is None:
        return None


    texto = str(
        cik
    ).strip()


    if not texto:
        return None


    # Algunos CSV pueden traer:
    # 123456.0

    if texto.endswith(
        ".0"
    ):
        texto = texto[:-2]


    if not texto.isdigit():
        return None


    return texto.zfill(
        10
    )


# ============================================================
# DESCARGAR CIKs DESDE CSV SEC
# ============================================================

def descargar_ciks_csv_sec(url):
    """
    Descarga un CSV SEC y devuelve
    el conjunto de CIK encontrados.
    """

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    contenido = (
        response.text
    )

    reader = csv.DictReader(
        StringIO(
            contenido
        )
    )

    ciks = set()


    for fila in reader:

        # Buscamos la columna CIK
        # independientemente de cómo venga escrita.

        cik_raw = None


        for clave, valor in fila.items():

            if (
                clave
                and clave.strip().upper()
                == "CIK"
            ):

                cik_raw = valor
                break


        cik = normalizar_cik(
            cik_raw
        )


        if cik:

            ciks.add(
                cik
            )


    return ciks


# ============================================================
# BDC
# ============================================================

def obtener_ciks_bdc():
    """
    Devuelve los CIK presentes
    en el informe oficial BDC de SEC.
    """

    return descargar_ciks_csv_sec(
        BDC_URL
    )


# ============================================================
# CLOSED-END FUNDS
# ============================================================

def obtener_ciks_closed_end_funds():
    """
    Devuelve los CIK presentes
    en el informe oficial de Closed-End Funds.
    """

    return descargar_ciks_csv_sec(
        CEF_URL
    )


# ============================================================
# BENCHMARKS SECTORIALES
# ============================================================

SECTOR_ETF = {

    "Technology":
        "XLK",

    "Financials":
        "XLF",

    "Health Care":
        "XLV",

    "Industrials":
        "XLI",

    "Consumer Discretionary":
        "XLY",

    "Consumer Staples":
        "XLP",

    "Energy":
        "XLE",

    "Materials":
        "XLB",

    "Utilities":
        "XLU",

    "Real Estate":
        "XLRE",

    "Communication Services":
        "XLC"
}


# ============================================================
# OBTENER ETFs SECTORIALES
# ============================================================

def obtener_etfs_sectoriales():
    """
    Devuelve todos los ETFs utilizados
    como benchmark sectorial.
    """

    return list(
        SECTOR_ETF.values()
    )