import csv
from pathlib import Path

from database.db import (
    obtener_ultimo_tecnico,
    obtener_ultimas_clasificaciones_fundamentales,
)


BASE_DIR = Path(__file__).resolve().parent.parent

CSV_PATH = (
    BASE_DIR
    / "data"
    / "morningstar_validation.csv"
)

COLUMNAS_MORNINGSTAR = [
    "symbol",
    "stars",
    "fair_value",
    "moat",
    "uncertainty",
    "updated_at",
]


def asegurar_plantilla_csv():
    """
    Crea exclusivamente la plantilla CSV si no existe.

    Devuelve True cuando se ha creado y el análisis debe terminar.
    """

    if CSV_PATH.exists():
        return False

    CSV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as archivo:
        escritor = csv.writer(
            archivo
        )
        escritor.writerow(
            COLUMNAS_MORNINGSTAR
        )

    print(
        "Plantilla Morningstar creada en: "
        f"{CSV_PATH}"
    )
    print(
        "Completa el CSV y vuelve a ejecutar el script."
    )

    return True


def csv_tiene_datos():
    with CSV_PATH.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as archivo:
        lector = csv.DictReader(
            archivo
        )

        return next(
            lector,
            None,
        ) is not None


def cargar_morningstar():
    datos = pd.read_csv(
        CSV_PATH
    )

    faltantes = [
        columna
        for columna in COLUMNAS_MORNINGSTAR
        if columna not in datos.columns
    ]

    if faltantes:
        raise ValueError(
            "Faltan columnas Morningstar: "
            + ", ".join(faltantes)
        )

    datos = datos[
        COLUMNAS_MORNINGSTAR
    ].copy()

    datos["symbol"] = (
        datos["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    datos = datos[
        datos["symbol"] != ""
    ].copy()

    for columna in (
        "stars",
        "fair_value",
    ):
        datos[columna] = pd.to_numeric(
            datos[columna],
            errors="coerce",
        )

    datos["moat"] = (
        datos["moat"]
        .fillna("SIN DATO")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    datos["uncertainty"] = (
        datos["uncertainty"]
        .fillna("SIN DATO")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    datos["updated_at"] = (
        datos["updated_at"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    stars_invalidas = datos[
        datos["stars"].notna()
        & ~datos["stars"].between(
            1,
            5,
            inclusive="both",
        )
    ]

    if not stars_invalidas.empty:
        symbols = ", ".join(
            stars_invalidas["symbol"].tolist()
        )
        raise ValueError(
            "stars debe estar entre 1 y 5. "
            f"Symbols invalidos: {symbols}"
        )

    duplicados = datos["symbol"].duplicated(
        keep=False
    ).sum()

    if duplicados:
        print(
            "Filas Morningstar con symbol duplicado: "
            f"{duplicados}. Se conserva la ultima."
        )
        datos = datos.drop_duplicates(
            subset="symbol",
            keep="last",
        )

    return datos


def cargar_fundamentales_propios():
    datos = pd.DataFrame(
        obtener_ultimas_clasificaciones_fundamentales()
    )

    if datos.empty:
        return datos

    columnas = [
        "symbol",
        "score_fundamental",
        "calidad_fundamental",
        "analysis_date",
    ]

    datos = datos[
        [
            columna
            for columna in columnas
            if columna in datos.columns
        ]
    ].copy()

    datos["symbol"] = (
        datos["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    datos["score_fundamental"] = pd.to_numeric(
        datos["score_fundamental"],
        errors="coerce",
    )

    return datos


def obtener_precios_recientes(
    symbols,
):
    precios = []

    for symbol in symbols:
        tecnico = obtener_ultimo_tecnico(
            symbol
        )

        precios.append(
            {
                "symbol": symbol,
                "precio": (
                    tecnico.get("precio")
                    if tecnico
                    else None
                ),
            }
        )

    datos = pd.DataFrame(
        precios,
        columns=[
            "symbol",
            "precio",
        ],
    )

    if not datos.empty:
        datos["precio"] = pd.to_numeric(
            datos["precio"],
            errors="coerce",
        )

    return datos


def mostrar_correlacion(
    datos,
    columna,
    etiqueta,
):
    pares = datos[
        [
            "score_fundamental",
            columna,
        ]
    ].dropna()

    if len(pares) < 2:
        print(
            f"{etiqueta}: SIN DATOS SUFICIENTES"
        )
        return

    correlacion = pares[
        "score_fundamental"
    ].corr(
        pares[columna]
    )

    print(
        f"{etiqueta}: {correlacion:+.4f} "
        f"(n={len(pares)})"
    )


def main():
    if asegurar_plantilla_csv():
        return

    if not csv_tiene_datos():
        print(
            "El CSV de Morningstar no contiene datos."
        )
        return

    global pd
    import pandas as pd

    morningstar = cargar_morningstar()

    if morningstar.empty:
        print(
            "El CSV de Morningstar no contiene datos."
        )
        return

    propios = cargar_fundamentales_propios()

    if propios.empty:
        print(
            "No existen clasificaciones fundamentales propias."
        )
        return

    symbols_propios = set(
        propios["symbol"]
    )
    symbols_morningstar = set(
        morningstar["symbol"]
    )

    faltan_morningstar = sorted(
        symbols_propios
        - symbols_morningstar
    )
    faltan_propios = sorted(
        symbols_morningstar
        - symbols_propios
    )

    comparacion = propios.merge(
        morningstar,
        on="symbol",
        how="inner",
        validate="one_to_one",
    )

    precios = obtener_precios_recientes(
        comparacion["symbol"].tolist()
    )

    comparacion = comparacion.merge(
        precios,
        on="symbol",
        how="left",
        validate="one_to_one",
    )

    valores_validos = (
        comparacion["precio"].gt(0)
        & comparacion["fair_value"].gt(0)
    )

    comparacion["price_fair_value"] = float("nan")
    comparacion["discount_to_fair_value_pct"] = float("nan")

    comparacion.loc[
        valores_validos,
        "price_fair_value",
    ] = (
        comparacion.loc[
            valores_validos,
            "precio",
        ]
        / comparacion.loc[
            valores_validos,
            "fair_value",
        ]
    )

    # Descuento positivo significa que el precio esta por debajo
    # del fair value. Se define como (1 - precio / fair_value) * 100.
    comparacion.loc[
        valores_validos,
        "discount_to_fair_value_pct",
    ] = (
        1
        - (
            comparacion.loc[
                valores_validos,
                "precio",
            ]
            / comparacion.loc[
                valores_validos,
                "fair_value",
            ]
        )
    ) * 100

    comparacion = comparacion.sort_values(
        [
            "score_fundamental",
            "symbol",
        ],
        ascending=[
            False,
            True,
        ],
    )

    print()
    print("MORNINGSTAR VALIDATION")
    print("=" * 100)
    print(
        f"Fundamentales propios: {len(propios)}"
    )
    print(
        f"Filas Morningstar: {len(morningstar)}"
    )
    print(
        f"Matches: {len(comparacion)}"
    )
    print(
        "Sin Morningstar: "
        f"{len(faltan_morningstar)}"
    )
    print(
        "Sin fundamental propio: "
        f"{len(faltan_propios)}"
    )

    if faltan_morningstar:
        print(
            "Symbols sin Morningstar: "
            + ", ".join(faltan_morningstar)
        )

    if faltan_propios:
        print(
            "Symbols sin fundamental propio: "
            + ", ".join(faltan_propios)
        )

    if comparacion.empty:
        print(
            "No existen symbols coincidentes para comparar."
        )
        return

    columnas_tabla = [
        "symbol",
        "score_fundamental",
        "calidad_fundamental",
        "stars",
        "precio",
        "fair_value",
        "price_fair_value",
        "discount_to_fair_value_pct",
        "moat",
        "uncertainty",
        "updated_at",
    ]

    print()
    print("TABLA COMPARATIVA")
    print("-" * 100)
    print(
        comparacion[columnas_tabla].to_string(
            index=False
        )
    )

    print()
    print("CORRELACIONES")
    print("-" * 100)
    mostrar_correlacion(
        comparacion,
        "stars",
        "Score propio vs estrellas",
    )
    mostrar_correlacion(
        comparacion,
        "price_fair_value",
        "Score propio vs P/FV (menor implica mas infravaloracion)",
    )
    mostrar_correlacion(
        comparacion,
        "discount_to_fair_value_pct",
        "Score propio vs descuento a fair value",
    )

    print()
    print("SCORE PROPIO MEDIO POR ESTRELLAS")
    print("-" * 100)
    print(
        comparacion.dropna(
            subset=["stars"]
        ).groupby(
            "stars"
        )["score_fundamental"].agg(
            ["mean", "count"]
        ).to_string()
    )

    print()
    print("SCORE PROPIO MEDIO POR MOAT")
    print("-" * 100)
    print(
        comparacion.groupby(
            "moat"
        )["score_fundamental"].agg(
            ["mean", "count"]
        ).sort_values(
            "mean",
            ascending=False,
        ).to_string()
    )

    # Estrellas se llevan a escala 0-100 para poder medir
    # una discrepancia descriptiva con el score propio.
    comparacion["morningstar_0_100"] = (
        comparacion["stars"]
        / 5.0
        * 100.0
    )
    comparacion["discrepancia"] = (
        comparacion["score_fundamental"]
        - comparacion["morningstar_0_100"]
    )
    comparacion["discrepancia_abs"] = (
        comparacion["discrepancia"].abs()
    )

    discrepancias = comparacion.dropna(
        subset=[
            "score_fundamental",
            "stars",
        ]
    ).sort_values(
        "discrepancia_abs",
        ascending=False,
    )

    print()
    print("MAYORES DISCREPANCIAS")
    print("-" * 100)

    if discrepancias.empty:
        print("SIN DATOS SUFICIENTES")
    else:
        print(
            discrepancias[
                [
                    "symbol",
                    "score_fundamental",
                    "stars",
                    "precio",
                    "fair_value",
                    "price_fair_value",
                    "discount_to_fair_value_pct",
                    "moat",
                    "discrepancia",
                ]
            ].head(20).to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
