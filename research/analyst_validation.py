import sqlite3

import pandas as pd

from database.db import (
    obtener_historial_symbol,
    obtener_ultimas_clasificaciones_fundamentales,
    obtener_ultimos_analyst_snapshots,
)


COLUMNAS_TARGET = [
    "symbol", "price_internal", "target_mean",
    "upside_mean_pct", "consensus_score", "analyst_count",
    "eps_growth_0y", "eps_growth_next_y",
]

COLUMNAS_CONSENSO = [
    "symbol", "consensus_score", "strong_buy", "buy", "hold",
    "sell", "strong_sell", "analyst_count", "upside_mean_pct",
]

COLUMNAS_EPS = [
    "symbol", "eps_0y", "eps_next_y", "eps_growth_0y",
    "eps_growth_next_y", "eps_analysts_next_y", "upside_mean_pct",
]

COLUMNAS_DISCREPANCIA = [
    "symbol", "prioridad_momentum_v4", "score_momentum_v4",
    "score_fundamental", "upside_mean_pct", "consensus_score",
    "analyst_count", "eps_growth_next_y",
]

NUMERICAS = [
    "price_internal", "target_mean", "target_median",
    "upside_mean_pct", "upside_median_pct", "consensus_score",
    "analyst_count", "eps_0y", "eps_next_y", "eps_growth_0y",
    "eps_growth_next_y", "eps_analysts_0y", "eps_analysts_next_y",
]


def porcentaje(valor):
    if pd.isna(valor):
        return "N/A"
    return f"{valor:+.2f}%"


def growth_pct(valor):
    if pd.isna(valor):
        return "N/A"
    return f"{valor * 100:+.2f}%"


def decimal(valor):
    if pd.isna(valor):
        return "N/A"
    return f"{valor:+.3f}"


def numero(valor):
    if pd.isna(valor):
        return "N/A"
    return f"{valor:.2f}"


def imprimir_titulo(titulo, caracter="="):
    print()
    print(titulo)
    print(caracter * 110)


def imprimir_tabla(datos, columnas, limite=None):
    tabla = datos[
        [columna for columna in columnas if columna in datos.columns]
    ].copy()

    if limite is not None:
        tabla = tabla.head(limite)

    if tabla.empty:
        print("SIN DATOS")
        return

    formatters = {}

    for columna in ("upside_mean_pct", "upside_median_pct"):
        if columna in tabla.columns:
            formatters[columna] = porcentaje

    for columna in ("eps_growth_0y", "eps_growth_next_y"):
        if columna in tabla.columns:
            formatters[columna] = growth_pct

    if "consensus_score" in tabla.columns:
        formatters["consensus_score"] = decimal

    for columna in (
        "price_internal", "target_mean", "target_median",
        "eps_0y", "eps_next_y", "score_fundamental",
        "score_momentum_v4",
    ):
        if columna in tabla.columns:
            formatters[columna] = numero

    with pd.option_context(
        "display.max_columns", None,
        "display.width", 220,
    ):
        print(
            tabla.to_string(
                index=False,
                formatters=formatters,
                na_rep="N/A",
            )
        )


def cargar_snapshots():
    datos = pd.DataFrame(
        obtener_ultimos_analyst_snapshots()
    )

    if datos.empty:
        return datos

    for columna in NUMERICAS:
        if columna in datos.columns:
            datos[columna] = pd.to_numeric(
                datos[columna],
                errors="coerce",
            )

    datos["symbol"] = (
        datos["symbol"].astype(str).str.strip().str.upper()
    )
    return datos


def cargar_tecnicos_v4(symbols):
    tecnicos = []

    for symbol in symbols:
        historial = obtener_historial_symbol(
            symbol,
            limite=1000,
        )
        ultimo_v4 = next(
            (
                fila
                for fila in historial
                if fila.get("score_version") == "v4"
            ),
            None,
        )

        if ultimo_v4 is None:
            continue

        tecnicos.append(
            {
                "symbol": symbol,
                "prioridad_momentum_v4": ultimo_v4.get(
                    "prioridad_estudio"
                ),
                "score_momentum_v4": ultimo_v4.get("score"),
                "reversal_candidate": ultimo_v4.get(
                    "reversal_candidate"
                ),
                "reversal_version": ultimo_v4.get(
                    "reversal_version"
                ),
                "reversal_priority": ultimo_v4.get(
                    "reversal_priority"
                ),
            }
        )

    return pd.DataFrame(
        tecnicos,
        columns=[
            "symbol", "prioridad_momentum_v4", "score_momentum_v4",
            "reversal_candidate", "reversal_version", "reversal_priority",
        ],
    )


def cargar_fundamentales():
    fundamentales = pd.DataFrame(
        obtener_ultimas_clasificaciones_fundamentales()
    )

    if fundamentales.empty:
        return pd.DataFrame(
            columns=["symbol", "score_fundamental"]
        )

    fundamentales["symbol"] = (
        fundamentales["symbol"].astype(str).str.strip().str.upper()
    )
    fundamentales["score_fundamental"] = pd.to_numeric(
        fundamentales["score_fundamental"],
        errors="coerce",
    )

    return fundamentales[
        ["symbol", "score_fundamental"]
    ].drop_duplicates(
        subset="symbol",
        keep="first",
    )


def metricas_grupo(datos):
    n = len(datos)
    upside = datos["upside_mean_pct"].dropna()
    consensus = datos["consensus_score"].dropna()
    analysts = datos["analyst_count"].dropna()

    return {
        "n": n,
        "upside_medio": upside.mean(),
        "upside_mediano": upside.median(),
        "consensus_medio": consensus.mean(),
        "analyst_count_mediano": analysts.median(),
        "upside_positivo_pct": (
            (upside > 0).mean() * 100
            if not upside.empty else None
        ),
        "consensus_positivo_pct": (
            (consensus > 0).mean() * 100
            if not consensus.empty else None
        ),
    }


def imprimir_metricas_cruce(titulo, filas):
    imprimir_titulo(titulo)
    datos = pd.DataFrame(filas)

    if datos.empty:
        print("SIN DATOS")
        return

    print(
        datos.to_string(
            index=False,
            formatters={
                "upside_medio": porcentaje,
                "upside_mediano": porcentaje,
                "consensus_medio": decimal,
                "upside_positivo_pct": porcentaje,
                "consensus_positivo_pct": porcentaje,
            },
            na_rep="N/A",
        )
    )


def banda_fundamental(valor):
    if pd.isna(valor):
        return None
    if valor >= 80:
        return ">= 80"
    if valor >= 70:
        return "70-79"
    if valor >= 60:
        return "60-69"
    return "< 60"


def banda_analistas(valor):
    if pd.isna(valor) or valor < 1:
        return None
    if valor <= 2:
        return "1-2"
    if valor <= 5:
        return "3-5"
    if valor <= 10:
        return "6-10"
    if valor <= 20:
        return "11-20"
    return "> 20"


def main():
    try:
        snapshots = cargar_snapshots()
    except sqlite3.OperationalError as exc:
        print(
            "No se puede leer analyst_consensus_snapshots: "
            f"{exc}"
        )
        return

    if snapshots.empty:
        print("No existen snapshots de analyst consensus.")
        return

    imprimir_titulo("ANALYST CONSENSUS VALIDATION")

    con_target_mean = snapshots["target_mean"].notna().sum()
    con_target_median = snapshots["target_median"].notna().sum()
    con_recomendaciones = (
        snapshots["analyst_count"].fillna(0).gt(0).sum()
    )
    con_eps_anual = (
        snapshots["eps_0y"].notna()
        | snapshots["eps_next_y"].notna()
    ).sum()
    sin_target = (
        snapshots["target_mean"].isna()
        & snapshots["target_median"].isna()
    ).sum()
    analyst_count = snapshots["analyst_count"].dropna()

    print(f"Simbolos analizados:       {len(snapshots)}")
    print(f"Con target mean:           {con_target_mean}")
    print(f"Con target median:         {con_target_median}")
    print(f"Con recomendaciones:       {con_recomendaciones}")
    print(f"Con estimaciones EPS año:  {con_eps_anual}")
    print(f"Sin target:                {sin_target}")
    print(f"Analyst count medio:       {analyst_count.mean():.2f}")
    print(f"Analyst count mediano:     {analyst_count.median():.2f}")

    imprimir_titulo("TARGETS")
    upside = snapshots["upside_mean_pct"].dropna()

    if upside.empty:
        print("SIN DATOS")
    else:
        print(f"Media:                  {porcentaje(upside.mean())}")
        print(f"Mediana:                {porcentaje(upside.median())}")
        print(f"Percentil 25:           {porcentaje(upside.quantile(0.25))}")
        print(f"Percentil 75:           {porcentaje(upside.quantile(0.75))}")
        print(f"Upside > 0:            {porcentaje((upside > 0).mean() * 100)}")
        print(f"Upside >= +10%:        {porcentaje((upside >= 10).mean() * 100)}")
        print(f"Upside >= +20%:        {porcentaje((upside >= 20).mean() * 100)}")
        print(f"Downside < 0:          {porcentaje((upside < 0).mean() * 100)}")
        print(f"Downside <= -10%:      {porcentaje((upside <= -10).mean() * 100)}")

    imprimir_titulo("TOP 20 UPSIDE")
    targets = snapshots.dropna(
        subset=["upside_mean_pct"]
    )
    imprimir_tabla(
        targets.sort_values("upside_mean_pct", ascending=False),
        COLUMNAS_TARGET,
        20,
    )

    imprimir_titulo("TOP 20 DOWNSIDE")
    imprimir_tabla(
        targets.sort_values("upside_mean_pct", ascending=True),
        COLUMNAS_TARGET,
        20,
    )

    imprimir_titulo("CONSENSO ANALISTAS")
    consensus = snapshots["consensus_score"].dropna()
    print(
        consensus.describe(
            percentiles=[0.25, 0.5, 0.75]
        ).to_string()
        if not consensus.empty else "SIN DATOS"
    )

    imprimir_titulo("TOP 20 CONSENSO MAS POSITIVO")
    con_consensus = snapshots.dropna(
        subset=["consensus_score"]
    )
    imprimir_tabla(
        con_consensus.sort_values("consensus_score", ascending=False),
        COLUMNAS_CONSENSO,
        20,
    )

    imprimir_titulo("TOP 20 CONSENSO MAS NEGATIVO")
    imprimir_tabla(
        con_consensus.sort_values("consensus_score", ascending=True),
        COLUMNAS_CONSENSO,
        20,
    )

    imprimir_titulo("TOP 20 CRECIMIENTO EPS NEXT YEAR")
    imprimir_tabla(
        snapshots.dropna(
            subset=["eps_growth_next_y"]
        ).sort_values(
            "eps_growth_next_y",
            ascending=False,
        ),
        COLUMNAS_EPS,
        20,
    )

    tecnicos = cargar_tecnicos_v4(
        snapshots["symbol"].tolist()
    )
    fundamentales = cargar_fundamentales()
    analisis = snapshots.merge(
        tecnicos,
        on="symbol",
        how="left",
        validate="one_to_one",
    ).merge(
        fundamentales,
        on="symbol",
        how="left",
        validate="one_to_one",
    )

    filas_momentum = []
    for prioridad in ("A+", "A", "B"):
        grupo = analisis[
            analisis["prioridad_momentum_v4"] == prioridad
        ]
        filas_momentum.append(
            {
                "prioridad": prioridad,
                **metricas_grupo(grupo),
            }
        )

    imprimir_metricas_cruce(
        "CRUCE CON MOMENTUM V4",
        filas_momentum,
    )

    reversal_a = analisis[
        analisis["reversal_candidate"].fillna(0).eq(1)
        & analisis["reversal_version"].eq("reversal_v1")
        & analisis["reversal_priority"].eq("A")
    ]
    imprimir_metricas_cruce(
        "CRUCE CON REVERSAL V1",
        [
            {
                "prioridad": "A",
                **metricas_grupo(reversal_a),
            }
        ],
    )

    analisis["banda_fundamental"] = analisis[
        "score_fundamental"
    ].apply(banda_fundamental)
    filas_fundamental = []

    for banda in (">= 80", "70-79", "60-69", "< 60"):
        grupo = analisis[
            analisis["banda_fundamental"] == banda
        ]
        upside_grupo = grupo["upside_mean_pct"].dropna()
        filas_fundamental.append(
            {
                "banda": banda,
                "n": len(grupo),
                "score_fundamental_medio": grupo[
                    "score_fundamental"
                ].mean(),
                "upside_medio": upside_grupo.mean(),
                "consensus_medio": grupo[
                    "consensus_score"
                ].mean(),
                "eps_growth_next_y_medio": grupo[
                    "eps_growth_next_y"
                ].mean(),
                "upside_positivo_pct": (
                    (upside_grupo > 0).mean() * 100
                    if not upside_grupo.empty else None
                ),
            }
        )

    imprimir_titulo("CRUCE CON FUNDAMENTAL PROPIO")
    print(
        pd.DataFrame(filas_fundamental).to_string(
            index=False,
            formatters={
                "score_fundamental_medio": numero,
                "upside_medio": porcentaje,
                "consensus_medio": decimal,
                "eps_growth_next_y_medio": growth_pct,
                "upside_positivo_pct": porcentaje,
            },
            na_rep="N/A",
        )
    )

    sistema_positivo = analisis[
        analisis["prioridad_momentum_v4"].isin(["A+", "A"])
        & (
            analisis["upside_mean_pct"].lt(0)
            | analisis["consensus_score"].le(0)
        )
    ].sort_values(
        ["prioridad_momentum_v4", "score_momentum_v4"],
        ascending=[True, False],
    )
    imprimir_titulo(
        "DISCREPANCIA A: SISTEMA POSITIVO / ANALISTAS NEGATIVOS"
    )
    imprimir_tabla(
        sistema_positivo,
        COLUMNAS_DISCREPANCIA,
        20,
    )

    analistas_positivos = analisis[
        analisis["upside_mean_pct"].ge(20)
        & analisis["consensus_score"].ge(0.5)
        & ~analisis["prioridad_momentum_v4"].isin(["A+", "A"])
    ].sort_values(
        ["upside_mean_pct", "consensus_score"],
        ascending=[False, False],
    )
    imprimir_titulo(
        "DISCREPANCIA B: ANALISTAS POSITIVOS / SISTEMA NO PRIORITARIO"
    )
    imprimir_tabla(
        analistas_positivos,
        COLUMNAS_DISCREPANCIA,
        20,
    )

    analisis["banda_analistas"] = analisis[
        "analyst_count"
    ].apply(banda_analistas)
    filas_evidencia = []

    for banda in ("1-2", "3-5", "6-10", "11-20", "> 20"):
        grupo = analisis[
            analisis["banda_analistas"] == banda
        ]
        filas_evidencia.append(
            {
                "analyst_count": banda,
                "n": len(grupo),
                "upside_medio": grupo["upside_mean_pct"].mean(),
                "consensus_medio": grupo["consensus_score"].mean(),
            }
        )

    imprimir_titulo("CALIDAD DE LA EVIDENCIA")
    print(
        pd.DataFrame(filas_evidencia).to_string(
            index=False,
            formatters={
                "upside_medio": porcentaje,
                "consensus_medio": decimal,
            },
            na_rep="N/A",
        )
    )


if __name__ == "__main__":
    main()
