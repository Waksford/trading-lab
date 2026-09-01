from database.db import (
    obtener_toda_company_metadata,
    actualizar_sector_metadata
)

from market.sectors import (
    sic_a_sector
)


print()
print("======================================")
print("       RECALCULANDO SECTORES")
print("======================================")
print()


metadata = obtener_toda_company_metadata()


actualizados = 0
sin_sic = 0
cambiados = 0


for empresa in metadata:

    symbol = empresa["symbol"]

    sic = empresa.get(
        "sic"
    )

    sector_anterior = empresa.get(
        "sector"
    )


    if sic in (
        None,
        "",
        0,
        "0"
    ):

        sin_sic += 1
        continue


    sector_nuevo = sic_a_sector(
        sic
    )


    if (
        sector_nuevo
        != sector_anterior
    ):

        print(
            f"{symbol:<7} | "
            f"SIC {str(sic):<5} | "
            f"{sector_anterior:<24} "
            f"-> {sector_nuevo}"
        )

        cambiados += 1


    actualizar_sector_metadata(
        symbol,
        sector_nuevo
    )

    actualizados += 1


print()
print("======================================")
print("              RESUMEN")
print("======================================")
print()

print(
    f"Metadata total:       "
    f"{len(metadata)}"
)

print(
    f"Recalculados:         "
    f"{actualizados}"
)

print(
    f"Sector modificado:    "
    f"{cambiados}"
)

print(
    f"Sin SIC:              "
    f"{sin_sic}"
)