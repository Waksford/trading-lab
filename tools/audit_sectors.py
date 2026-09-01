from database.db import (
    obtener_toda_company_metadata
)


# ============================================================
# CARGAR METADATA
# ============================================================

metadata = (
    obtener_toda_company_metadata()
)


# ============================================================
# SOLO EMPRESAS OPERATIVAS
# ============================================================

operativas = [

    empresa

    for empresa in metadata

    if empresa.get(
        "asset_type"
    ) == "OPERATING_COMPANY"
]


# ============================================================
# AUDITORÍA DE SECTORES
# ============================================================

sectores = {}


for empresa in operativas:

    sector = empresa.get(
        "sector"
    )

    if not sector:
        sector = "Unknown"

    sectores[sector] = (
        sectores.get(
            sector,
            0
        )
        + 1
    )


ranking = sorted(
    sectores.items(),
    key=lambda x: x[1],
    reverse=True
)


print()

print(
    "======================================"
)

print(
    "       AUDITORÍA DE SECTORES"
)

print(
    "======================================"
)

print()


for sector, cantidad in ranking:

    porcentaje = (
        cantidad
        / len(operativas)
        * 100
    )

    print(
        f"{sector:<28} "
        f"{cantidad:>5} "
        f"({porcentaje:>5.1f}%)"
    )


print()

print(
    f"Total empresas operativas: "
    f"{len(operativas)}"
)


# ============================================================
# SIC MÁS FRECUENTES
# ============================================================

print()

print(
    "======================================"
)

print(
    "       SIC MÁS FRECUENTES"
)

print(
    "======================================"
)

print()


sic_counts = {}


for empresa in operativas:

    sic = empresa.get(
        "sic"
    )

    descripcion = empresa.get(
        "sic_description"
    )

    sector = empresa.get(
        "sector"
    )


    clave = (
        sic,
        descripcion,
        sector
    )


    sic_counts[clave] = (
        sic_counts.get(
            clave,
            0
        )
        + 1
    )


ranking_sic = sorted(
    sic_counts.items(),
    key=lambda x: x[1],
    reverse=True
)


for (
    sic,
    descripcion,
    sector
), cantidad in ranking_sic[:30]:

    if descripcion is None:
        descripcion = ""

    if sector is None:
        sector = "Unknown"

    print(
        f"SIC {str(sic):<5} | "
        f"{cantidad:>4} | "
        f"{sector:<24} | "
        f"{descripcion}"
    )