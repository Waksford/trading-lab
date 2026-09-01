import time

from database.db import (
    inicializar_tabla_company_metadata,
    obtener_company_metadata,
    guardar_company_metadata
)

from market.sectors import (
    obtener_mapa_sec,
    obtener_metadata_sec
)

from market.universe import (
    obtener_universo_usa
)

import os

from dotenv import load_dotenv


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
        "de Alpaca."
    )


# ============================================================
# DB
# ============================================================

inicializar_tabla_company_metadata()


# ============================================================
# UNIVERSO
# ============================================================

print()
print("======================================")
print("       ACTUALIZANDO SECTORES")
print("======================================")
print()


universo = obtener_universo_usa(
    API_KEY,
    SECRET_KEY
)


print(
    f"Empresas del universo: "
    f"{len(universo)}"
)


# ============================================================
# MAPA SEC
# ============================================================

print(
    "\nDescargando mapa "
    "ticker -> CIK..."
)


mapa_sec = obtener_mapa_sec()


print(
    f"Tickers disponibles en SEC: "
    f"{len(mapa_sec)}"
)


# ============================================================
# CONTADORES
# ============================================================

ya_existentes = 0

guardadas = 0

sin_cik = 0

errores = 0

unknown = 0


# ============================================================
# ENRIQUECER
# ============================================================

for numero, activo in enumerate(
    universo,
    start=1
):

    symbol = (
        activo["symbol"]
        .upper()
    )


    # --------------------------------------------------------
    # YA TENEMOS METADATA
    # --------------------------------------------------------

    existente = obtener_company_metadata(
        symbol
    )


    if existente is not None:

        ya_existentes += 1

        continue


    # --------------------------------------------------------
    # BUSCAR CIK
    # --------------------------------------------------------

    sec_info = mapa_sec.get(
        symbol
    )


    if sec_info is None:

        sin_cik += 1

        continue


    cik = sec_info["cik"]


    # --------------------------------------------------------
    # CONSULTAR SEC
    # --------------------------------------------------------

    try:

        metadata = obtener_metadata_sec(
            cik
        )


        guardar_company_metadata(

            symbol=symbol,

            cik=cik,

            sic=metadata["sic"],

            sic_description=(
                metadata[
                    "sic_description"
                ]
            ),

            sector=metadata[
                "sector"
            ],

            source="SEC"
        )


        guardadas += 1


        if metadata["sector"] == "Unknown":

            unknown += 1


        print(
            f"[{numero}/{len(universo)}] "
            f"{symbol:<7} "
            f"{str(metadata['sic']):<5} "
            f"{metadata['sector']}"
        )


        # SEC pide acceso razonable.
        # Vamos bastante por debajo de 10 req/s.
        time.sleep(0.15)


    except Exception as e:

        errores += 1

        print(
            f"ERROR {symbol}: "
            f"{e}"
        )

        # Si hay problemas, aflojamos.
        time.sleep(1)


# ============================================================
# RESUMEN
# ============================================================

print()
print("======================================")
print("              RESUMEN")
print("======================================")
print()

print(
    f"Universo:            "
    f"{len(universo)}"
)

print(
    f"Ya existentes:       "
    f"{ya_existentes}"
)

print(
    f"Nuevas clasificadas: "
    f"{guardadas}"
)

print(
    f"Sin CIK SEC:         "
    f"{sin_cik}"
)

print(
    f"Sector Unknown:      "
    f"{unknown}"
)

print(
    f"Errores:             "
    f"{errores}"
)