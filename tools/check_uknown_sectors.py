from database.db import obtener_toda_company_metadata


metadata = obtener_toda_company_metadata()


unknowns = [
    empresa
    for empresa in metadata
    if empresa.get("asset_type") == "UNKNOWN"
]


print()
print("======================================")
print("         ACTIVOS UNKNOWN")
print("======================================")
print()


for empresa in unknowns:

    print(
        f"{empresa['symbol']:<7} | "
        f"CIK {str(empresa['cik']):<10} | "
        f"SIC {str(empresa['sic']):<5} | "
        f"{empresa['sic_description']}"
    )


print()
print(
    f"Total Unknown: "
    f"{len(unknowns)}"
)