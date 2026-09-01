import pandas as pd

from research.paper_analysis import (
    cargar_dataset,
    crear_buckets,
    crear_configuraciones,
)


# ============================================================
# CONFIGURACION
# ============================================================

HORIZONTE = 5

MIN_CASOS = 20
MIN_SESIONES = 5
MIN_SIMBOLOS = 10

TRIM_PERCENT = 0.05


# ============================================================
# HELPERS
# ============================================================

def pct_positivos(serie):

    if serie.empty:
        return 0.0

    return (
        (serie > 0).mean()
        * 100
    )


def calcular_trimmed_mean(
    serie,
    porcentaje=TRIM_PERCENT
):
    """
    Calcula la media eliminando los extremos
    superior e inferior.

    Por defecto elimina:
        5% inferior
        5% superior
    """

    serie = (
        serie
        .dropna()
        .sort_values()
    )

    n = len(serie)

    if n == 0:
        return None

    cortar = int(
        n * porcentaje
    )

    if cortar == 0:
        return serie.mean()

    if (
        cortar * 2
        >= n
    ):
        return serie.mean()

    serie_trimmed = serie.iloc[
        cortar:
        n - cortar
    ]

    return serie_trimmed.mean()


# ============================================================
# ANALISIS POR SESION
# ============================================================

def analizar_sesiones(
    grupo
):
    """
    Calcula primero el resultado medio de cada
    fecha de señal.

    Esto evita que un día con 100 señales tenga
    mucho más peso que otro con 10 señales.
    """

    sesiones = (
        grupo
        .groupby(
            "market_date",
            observed=True
        )
        .agg(
            casos=("symbol", "size"),
            simbolos=("symbol", "nunique"),
            retorno=("retorno", "mean"),
            exceso_spy=("exceso_spy", "mean"),
            drawdown=("max_drawdown", "mean"),
        )
        .reset_index()
    )

    return sesiones


# ============================================================
# ROBUSTEZ
# ============================================================

def calcular_robustez(
    grupo
):

    casos = len(grupo)

    simbolos = (
        grupo[
            "symbol"
        ].nunique()
    )

    num_sesiones = (
        grupo[
            "market_date"
        ].nunique()
    )

    sesiones = analizar_sesiones(
        grupo
    )

    if sesiones.empty:

        return None

    # --------------------------------------------------------
    # RESULTADOS GENERALES
    # --------------------------------------------------------

    retorno_medio = (
        grupo[
            "retorno"
        ].mean()
    )

    retorno_mediana = (
        grupo[
            "retorno"
        ].median()
    )

    exceso_medio = (
        grupo[
            "exceso_spy"
        ].mean()
    )

    exceso_mediana = (
        grupo[
            "exceso_spy"
        ].median()
    )

    positivas = pct_positivos(
        grupo[
            "retorno"
        ]
    )

    bate_spy = pct_positivos(
        grupo[
            "exceso_spy"
        ]
    )

    drawdown = (
        grupo[
            "max_drawdown"
        ].mean()
    )

    # --------------------------------------------------------
    # CONSISTENCIA TEMPORAL
    # --------------------------------------------------------

    sesiones_positivas = pct_positivos(
        sesiones[
            "retorno"
        ]
    )

    sesiones_baten_spy = pct_positivos(
        sesiones[
            "exceso_spy"
        ]
    )

    retorno_sesion_mediana = (
        sesiones[
            "retorno"
        ].median()
    )

    exceso_sesion_mediana = (
        sesiones[
            "exceso_spy"
        ].median()
    )

    # --------------------------------------------------------
    # SIN OUTLIERS
    # --------------------------------------------------------

    retorno_trimmed = calcular_trimmed_mean(
        grupo[
            "retorno"
        ]
    )

    exceso_trimmed = calcular_trimmed_mean(
        grupo[
            "exceso_spy"
        ]
    )

    # --------------------------------------------------------
    # DEPENDENCIA DE OUTLIERS
    # --------------------------------------------------------

    diferencia_outlier = abs(
        exceso_medio
        -
        exceso_trimmed
    )

    if diferencia_outlier <= 0.50:

        dependencia_outliers = "BAJA"

    elif diferencia_outlier <= 1.50:

        dependencia_outliers = "MEDIA"

    else:

        dependencia_outliers = "ALTA"

    # --------------------------------------------------------
    # DIVERSIDAD
    # --------------------------------------------------------

    ratio_diversidad = (
        simbolos
        /
        casos
    )

    if (
        simbolos >= 50
        and
        ratio_diversidad >= 0.30
    ):

        diversidad = "ALTA"

    elif (
        simbolos >= 20
        and
        ratio_diversidad >= 0.20
    ):

        diversidad = "MEDIA"

    else:

        diversidad = "BAJA"

    # --------------------------------------------------------
    # SCORE ROBUSTEZ
    # --------------------------------------------------------

    score = 0

    # Tamaño muestra: max 20

    if casos >= 300:
        score += 20

    elif casos >= 150:
        score += 17

    elif casos >= 75:
        score += 14

    elif casos >= 40:
        score += 10

    else:
        score += 6

    # Sesiones: max 20

    if num_sesiones >= 20:
        score += 20

    elif num_sesiones >= 15:
        score += 18

    elif num_sesiones >= 10:
        score += 14

    elif num_sesiones >= 7:
        score += 10

    else:
        score += 6

    # Consistencia vs SPY: max 20

    if sesiones_baten_spy >= 70:
        score += 20

    elif sesiones_baten_spy >= 60:
        score += 16

    elif sesiones_baten_spy >= 55:
        score += 12

    elif sesiones_baten_spy >= 50:
        score += 8

    else:
        score += 2

    # Exceso trimmed: max 20

    if exceso_trimmed >= 2:
        score += 20

    elif exceso_trimmed >= 1:
        score += 16

    elif exceso_trimmed >= 0.5:
        score += 12

    elif exceso_trimmed > 0:
        score += 8

    else:
        score += 0

    # Dependencia outliers: max 10

    if dependencia_outliers == "BAJA":
        score += 10

    elif dependencia_outliers == "MEDIA":
        score += 5

    # Diversidad: max 10

    if diversidad == "ALTA":
        score += 10

    elif diversidad == "MEDIA":
        score += 6

    else:
        score += 2

    # --------------------------------------------------------
    # CLASIFICACION
    # --------------------------------------------------------

    if (
        score >= 80
        and
        exceso_trimmed > 0
        and
        sesiones_baten_spy >= 60
    ):

        clasificacion = "ROBUSTO"

    elif (
        score >= 65
        and
        exceso_trimmed > 0
    ):

        clasificacion = "PROMETEDOR"

    elif (
        score >= 50
    ):

        clasificacion = "INCIERTO"

    else:

        clasificacion = "DEBIL"

    return {

        "casos":
            casos,

        "simbolos":
            simbolos,

        "sesiones":
            num_sesiones,

        "retorno_medio":
            retorno_medio,

        "retorno_mediana":
            retorno_mediana,

        "exceso_medio":
            exceso_medio,

        "exceso_mediana":
            exceso_mediana,

        "positivas":
            positivas,

        "bate_spy":
            bate_spy,

        "drawdown":
            drawdown,

        "sesiones_positivas":
            sesiones_positivas,

        "sesiones_baten_spy":
            sesiones_baten_spy,

        "retorno_sesion_mediana":
            retorno_sesion_mediana,

        "exceso_sesion_mediana":
            exceso_sesion_mediana,

        "retorno_trimmed":
            retorno_trimmed,

        "exceso_trimmed":
            exceso_trimmed,

        "dependencia_outliers":
            dependencia_outliers,

        "diversidad":
            diversidad,

        "score_robustez":
            score,

        "clasificacion":
            clasificacion,
    }


# ============================================================
# VALIDACION DE GRUPO
# ============================================================

def grupo_valido(
    grupo
):

    if len(grupo) < MIN_CASOS:

        return False

    if (
        grupo[
            "market_date"
        ].nunique()
        < MIN_SESIONES
    ):

        return False

    if (
        grupo[
            "symbol"
        ].nunique()
        < MIN_SIMBOLOS
    ):

        return False

    return True


# ============================================================
# IMPRIMIR PATRON
# ============================================================

def imprimir_patron(
    nombre,
    resultado
):

    print()

    print(
        "=" * 100
    )

    print(
        nombre
    )

    print(
        "=" * 100
    )

    print()

    print(
        f"Casos:                   "
        f"{resultado['casos']}"
    )

    print(
        f"Simbolos:                "
        f"{resultado['simbolos']}"
    )

    print(
        f"Sesiones:                "
        f"{resultado['sesiones']}"
    )

    print()

    print(
        f"Retorno medio:           "
        f"{resultado['retorno_medio']:+.2f}%"
    )

    print(
        f"Retorno mediana:         "
        f"{resultado['retorno_mediana']:+.2f}%"
    )

    print()

    print(
        f"Exceso medio vs SPY:     "
        f"{resultado['exceso_medio']:+.2f}pp"
    )

    print(
        f"Mediana exceso vs SPY:   "
        f"{resultado['exceso_mediana']:+.2f}pp"
    )

    print()

    print(
        f"% resultados positivos: "
        f"{resultado['positivas']:.1f}%"
    )

    print(
        f"% resultados baten SPY: "
        f"{resultado['bate_spy']:.1f}%"
    )

    print(
        f"Drawdown medio:          "
        f"{resultado['drawdown']:+.2f}%"
    )

    print()

    print(
        "--------------------------------------"
    )

    print(
        "CONSISTENCIA TEMPORAL"
    )

    print(
        "--------------------------------------"
    )

    print()

    print(
        f"% sesiones positivas:    "
        f"{resultado['sesiones_positivas']:.1f}%"
    )

    print(
        f"% sesiones baten SPY:    "
        f"{resultado['sesiones_baten_spy']:.1f}%"
    )

    print()

    print(
        f"Mediana retorno/sesion:  "
        f"{resultado['retorno_sesion_mediana']:+.2f}%"
    )

    print(
        f"Mediana exceso/sesion:   "
        f"{resultado['exceso_sesion_mediana']:+.2f}pp"
    )

    print()

    print(
        "--------------------------------------"
    )

    print(
        "SIN OUTLIERS"
    )

    print(
        "--------------------------------------"
    )

    print()

    print(
        f"Retorno trimmed:         "
        f"{resultado['retorno_trimmed']:+.2f}%"
    )

    print(
        f"Exceso trimmed:          "
        f"{resultado['exceso_trimmed']:+.2f}pp"
    )

    print()

    print(
        "--------------------------------------"
    )

    print(
        "ROBUSTEZ"
    )

    print(
        "--------------------------------------"
    )

    print()

    print(
        f"Diversidad simbolos:     "
        f"{resultado['diversidad']}"
    )

    print(
        f"Dependencia outliers:    "
        f"{resultado['dependencia_outliers']}"
    )

    print()

    print(
        f"Score robustez:          "
        f"{resultado['score_robustez']}/100"
    )

    print(
        f"Clasificacion:           "
        f"{resultado['clasificacion']}"
    )


# ============================================================
# ANALISIS GENERICO DE PATRONES
# ============================================================

def analizar_patrones(
    df,
    columnas,
    titulo
):

    resultados = []

    grupos = (
        df
        .groupby(
            columnas,
            observed=True
        )
    )

    for claves, grupo in grupos:

        if not grupo_valido(
            grupo
        ):

            continue

        resultado = calcular_robustez(
            grupo
        )

        if resultado is None:

            continue

        if not isinstance(
            claves,
            tuple
        ):

            claves = (
                claves,
            )

        nombre_partes = []

        for columna, valor in zip(
            columnas,
            claves
        ):

            nombre_partes.append(
                f"{columna}={valor}"
            )

        nombre = (
            " | ".join(
                nombre_partes
            )
        )

        resultados.append(
            (
                nombre,
                resultado
            )
        )

    resultados = sorted(
        resultados,
        key=lambda x:
            x[1][
                "score_robustez"
            ],
        reverse=True
    )

    print()

    print(
        "#" * 100
    )

    print(
        titulo
    )

    print(
        "#" * 100
    )

    if not resultados:

        print()

        print(
            "No existen patrones con muestra suficiente."
        )

        return []

    for nombre, resultado in resultados:

        imprimir_patron(
            nombre,
            resultado
        )

    return resultados


# ============================================================
# RANKING GENERAL
# ============================================================

def crear_ranking_general(
    bloques
):

    todos = []

    for categoria, resultados in bloques:

        for nombre, resultado in resultados:

            todos.append(
                (
                    categoria,
                    nombre,
                    resultado
                )
            )

    todos = sorted(
        todos,
        key=lambda x:
            x[2][
                "score_robustez"
            ],
        reverse=True
    )

    print()

    print(
        "=" * 120
    )

    print(
        "        TOP PATRONES ROBUSTOS"
    )

    print(
        "=" * 120
    )

    print()

    if not todos:

        print(
            "No existen patrones validos."
        )

        return

    for (
        categoria,
        nombre,
        resultado
    ) in todos[:20]:

        print(
            f"{resultado['score_robustez']:>3}/100 | "
            f"{resultado['clasificacion']:<10} | "
            f"ExcTrim "
            f"{resultado['exceso_trimmed']:+6.2f}pp | "
            f"DiasBeat "
            f"{resultado['sesiones_baten_spy']:>5.1f}% | "
            f"n={resultado['casos']:>4} | "
            f"dias={resultado['sesiones']:>3} | "
            f"sym={resultado['simbolos']:>3} | "
            f"{categoria} | "
            f"{nombre}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "======================================"
    )

    print(
        "       PATTERN ANALYSIS V1"
    )

    print(
        "======================================"
    )

    print()

    # --------------------------------------------------------
    # CARGAR
    # --------------------------------------------------------

    df = cargar_dataset()

    if df.empty:

        print(
            "No existen resultados paper maduros."
        )

        return

    # --------------------------------------------------------
    # PREPARAR
    # --------------------------------------------------------

    df = crear_buckets(
        df
    )

    df = crear_configuraciones(
        df
    )

    df = df[
        df[
            "horizonte"
        ]
        == HORIZONTE
    ].copy()

    print(
        f"Horizonte analizado:     "
        f"{HORIZONTE} sesiones"
    )

    print(
        f"Resultados:              "
        f"{len(df)}"
    )

    print(
        f"Simbolos:                "
        f"{df['symbol'].nunique()}"
    )

    print(
        f"Sesiones:                "
        f"{df['market_date'].nunique()}"
    )

    print()

    print(
        f"Filtro minimo:           "
        f"{MIN_CASOS} casos | "
        f"{MIN_SESIONES} sesiones | "
        f"{MIN_SIMBOLOS} simbolos"
    )

    # --------------------------------------------------------
    # ANALISIS
    # --------------------------------------------------------

    bloques = []

    configuraciones = [

        (
            "PRIORIDAD",
            [
                "prioridad"
            ]
        ),

        (
            "RIESGO",
            [
                "riesgo_clasificacion"
            ]
        ),

        (
            "VOLUMEN",
            [
                "volumen_clasificacion"
            ]
        ),

        (
            "PRIORIDAD + RIESGO",
            [
                "prioridad",
                "riesgo_clasificacion"
            ]
        ),

        (
            "PRIORIDAD + VOLUMEN",
            [
                "prioridad",
                "volumen_clasificacion"
            ]
        ),

        (
            "PRIORIDAD + RSI",
            [
                "prioridad",
                "bucket_rsi"
            ]
        ),

        (
            "PRIORIDAD + SMA20",
            [
                "prioridad",
                "bucket_sma20"
            ]
        ),

        (
            "PRIORIDAD + RSI + SMA20",
            [
                "prioridad",
                "bucket_rsi",
                "bucket_sma20"
            ]
        ),

        (
            "CONFIGURACION COMPLETA",
            [
                "prioridad",
                "bucket_rsi",
                "bucket_sma20",
                "riesgo_clasificacion",
                "volumen_clasificacion"
            ]
        ),
    ]

    for titulo, columnas in configuraciones:

        resultados = analizar_patrones(
            df,
            columnas,
            titulo
        )

        bloques.append(
            (
                titulo,
                resultados
            )
        )

    # --------------------------------------------------------
    # RANKING FINAL
    # --------------------------------------------------------

    crear_ranking_general(
        bloques
    )


if __name__ == "__main__":

    main()