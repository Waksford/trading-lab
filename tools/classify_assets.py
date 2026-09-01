from database.db import (
    inicializar_tabla_company_metadata,
    asegurar_columna_asset_type,
    obtener_toda_company_metadata,
    actualizar_asset_type
)

from market.sectors import (
    obtener_ciks_bdc,
    obtener_ciks_closed_end_funds,
    normalizar_cik
)


# ============================================================
# INICIALIZAR
# ============================================================

inicializar_tabla_company_metadata()

asegurar_columna_asset_type()


print()
print("======================================")
print("       CLASIFICANDO ACTIVOS")
print("======================================")
print()


# ============================================================
# DESCARGAR LISTAS SEC
# ============================================================

print(
    "Descargando lista BDC..."
)

ciks_bdc = obtener_ciks_bdc()

print(
    f"BDCs SEC encontrados: "
    f"{len(ciks_bdc)}"
)


print(
    "\nDescargando lista Closed-End Funds..."
)

ciks_cef = obtener_ciks_closed_end_funds()

print(
    f"Closed-End Funds encontrados: "
    f"{len(ciks_cef)}"
)


# ============================================================
# METADATA LOCAL
# ============================================================

metadata = obtener_toda_company_metadata()


print(
    f"\nRegistros locales: "
    f"{len(metadata)}"
)


# ============================================================
# CONTADORES
# ============================================================

operating = 0
bdc = 0
cef = 0
spac = 0
unknown = 0


# ============================================================
# CLASIFICAR
# ============================================================

for empresa in metadata:

    symbol = empresa["symbol"]

    cik = normalizar_cik(
        empresa.get("cik")
    )

    sic = empresa.get(
        "sic"
    )

    sector = empresa.get(
        "sector"
    )


    # --------------------------------------------------------
    # BDC
    # --------------------------------------------------------

    if (
        cik
        and cik in ciks_bdc
    ):

        asset_type = "BDC"

        bdc += 1


    # --------------------------------------------------------
    # CLOSED-END FUND
    # --------------------------------------------------------

    elif (
        cik
        and cik in ciks_cef
    ):

        asset_type = "CLOSED_END_FUND"

        cef += 1


    # --------------------------------------------------------
    # SPAC / BLANK CHECK
    # --------------------------------------------------------

    elif str(sic) == "6770":

        asset_type = "SPAC"

        spac += 1


    # --------------------------------------------------------
    # EMPRESA OPERATIVA
    # --------------------------------------------------------

    elif (
        sic not in (
            None,
            "",
            0,
            "0"
        )

        and sector not in (
            None,
            "",
            "Unknown"
        )
    ):

        asset_type = "OPERATING_COMPANY"

        operating += 1


    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    else:

        asset_type = "UNKNOWN"

        unknown += 1


    actualizar_asset_type(
        symbol,
        asset_type
    )

# ============================================================
# RESUMEN
# ============================================================

print()
print("======================================")
print("              RESUMEN")
print("======================================")
print()

print(
    f"Operating companies: "
    f"{operating}"
)

print(
    f"BDCs:                "
    f"{bdc}"
)

print(
    f"Closed-End Funds:    "
    f"{cef}"
)

print(
    f"SPACs:               "
    f"{spac}"
)

print(
    f"Unknown:             "
    f"{unknown}"
)
print(
    f"Total:               "
    f"{len(metadata)}"
)