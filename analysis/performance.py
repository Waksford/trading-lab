import sqlite3

from pathlib import Path
from statistics import mean, median


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


DB_PATH = (
    BASE_DIR
    / "data"
    / "trading.db"
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

SCORE_VERSION = "v3"


# ============================================================
# DB
# ============================================================

def obtener_conexion():

    conexion = sqlite3.connect(
        DB_PATH
    )

    conexion.row_factory = (
        sqlite3.Row
    )

    return conexion


# ============================================================
# SESIONES V3
# ============================================================

def obtener_market_dates(
    score_version=SCORE_VERSION
):
    """
    Solo devuelve sesiones que contienen
    datos de la versión solicitada.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT DISTINCT market_date

        FROM scans

        WHERE market_date IS NOT NULL

        AND score_version = ?

        ORDER BY market_date ASC
        """,
        (
            score_version,
        )
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        fila["market_date"]
        for fila in filas
    ]


# ============================================================
# ACTIVOS
# ============================================================

def obtener_activos_market_date(
    market_date,
    score_version=SCORE_VERSION
):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE market_date = ?

        AND score_version = ?
        """,
        (
            market_date,
            score_version
        )
    )

    filas = cursor.fetchall()

    conexion.close()

    return {
        fila["symbol"]: dict(fila)
        for fila in filas
    }


# ============================================================
# SPY
# ============================================================

def obtener_spy_market_date(
    market_date
):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM benchmark_scans

        WHERE market_date = ?
        """,
        (
            market_date,
        )
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(fila)


# ============================================================
# RETORNO
# ============================================================

def calcular_retorno(
    precio_inicial,
    precio_final
):

    if (
        precio_inicial is None
        or precio_final is None
        or precio_inicial <= 0
    ):
        return None

    return (
        (
            precio_final
            / precio_inicial
        )
        - 1
    ) * 100


# ============================================================
# EVALUAR
# ============================================================

def evaluar_horizonte(
    score_minimo=85,
    sesiones_futuras=5,
    exigir_rs20_positivo=False,
    exigir_rs60_positivo=False,
    exigir_sector_positivo=False,
    score_version=SCORE_VERSION
):

    fechas = obtener_market_dates(
        score_version
    )


    if len(fechas) <= sesiones_futuras:

        return {
            "casos": 0,

            "motivo": (
                f"Solo hay {len(fechas)} sesiones "
                f"de {score_version}. "
                f"Se necesitan al menos "
                f"{sesiones_futuras + 1}."
            )
        }


    resultados = []


    for indice in range(
        len(fechas)
        - sesiones_futuras
    ):

        fecha_inicio = (
            fechas[indice]
        )

        fecha_final = (
            fechas[
                indice
                + sesiones_futuras
            ]
        )


        activos_inicio = (
            obtener_activos_market_date(
                fecha_inicio,
                score_version
            )
        )

        activos_final = (
            obtener_activos_market_date(
                fecha_final,
                score_version
            )
        )


        spy_inicio = (
            obtener_spy_market_date(
                fecha_inicio
            )
        )

        spy_final = (
            obtener_spy_market_date(
                fecha_final
            )
        )


        if (
            spy_inicio is None
            or spy_final is None
        ):
            continue


        retorno_spy = calcular_retorno(
            spy_inicio["precio"],
            spy_final["precio"]
        )


        if retorno_spy is None:
            continue


        for (
            symbol,
            activo_inicio
        ) in activos_inicio.items():


            score = activo_inicio.get(
                "score"
            )


            if (
                score is None
                or score < score_minimo
            ):
                continue


            rs20 = activo_inicio.get(
                "fuerza_20d"
            )

            rs60 = activo_inicio.get(
                "fuerza_60d"
            )


            sector20 = activo_inicio.get(
                "fuerza_sector_20d"
            )

            sector60 = activo_inicio.get(
                "fuerza_sector_60d"
            )


            if (
                exigir_rs20_positivo
                and (
                    rs20 is None
                    or rs20 <= 0
                )
            ):
                continue


            if (
                exigir_rs60_positivo
                and (
                    rs60 is None
                    or rs60 <= 0
                )
            ):
                continue


            if exigir_sector_positivo:

                if (
                    sector20 is None
                    or sector60 is None
                    or sector20 <= 0
                    or sector60 <= 0
                ):
                    continue


            activo_final = (
                activos_final.get(
                    symbol
                )
            )


            if activo_final is None:
                continue


            retorno_activo = calcular_retorno(

                activo_inicio.get(
                    "precio"
                ),

                activo_final.get(
                    "precio"
                )
            )


            if retorno_activo is None:
                continue


            exceso_spy = (
                retorno_activo
                - retorno_spy
            )


            resultados.append(
                {
                    "symbol":
                        symbol,

                    "fecha_inicio":
                        fecha_inicio,

                    "fecha_final":
                        fecha_final,

                    "score":
                        score,

                    "retorno":
                        retorno_activo,

                    "retorno_spy":
                        retorno_spy,

                    "exceso_spy":
                        exceso_spy,

                    "rs20":
                        rs20,

                    "rs60":
                        rs60,

                    "sector20":
                        sector20,

                    "sector60":
                        sector60
                }
            )


    if not resultados:

        return {
            "casos": 0,

            "motivo": (
                "Todavía no existen señales maduras "
                "que cumplan los criterios."
            )
        }


    retornos = [
        resultado["retorno"]
        for resultado in resultados
    ]


    excesos = [
        resultado["exceso_spy"]
        for resultado in resultados
    ]


    positivos = [
        retorno
        for retorno in retornos
        if retorno > 0
    ]


    baten_spy = [
        exceso
        for exceso in excesos
        if exceso > 0
    ]


    return {

        "casos":
            len(resultados),

        "retorno_medio":
            mean(retornos),

        "retorno_mediana":
            median(retornos),

        "porcentaje_positivos":
            (
                len(positivos)
                / len(retornos)
                * 100
            ),

        "retorno_spy_medio":
            mean(
                [
                    resultado[
                        "retorno_spy"
                    ]
                    for resultado
                    in resultados
                ]
            ),

        "exceso_spy_medio":
            mean(excesos),

        "exceso_spy_mediana":
            median(excesos),

        "porcentaje_bate_spy":
            (
                len(baten_spy)
                / len(excesos)
                * 100
            ),

        "mejor_resultado":
            max(retornos),

        "peor_resultado":
            min(retornos),

        "mejor_exceso_spy":
            max(excesos),

        "peor_exceso_spy":
            min(excesos),

        "resultados":
            resultados
    }


# ============================================================
# IMPRIMIR
# ============================================================

def imprimir_resultado(
    titulo,
    resultado
):

    print()

    print(
        "=" * 70
    )

    print(
        titulo
    )

    print(
        "=" * 70
    )


    if resultado["casos"] == 0:

        print(
            resultado.get(
                "motivo",
                "Sin datos."
            )
        )

        return


    print(
        f"Casos:                  "
        f"{resultado['casos']}"
    )


    print()


    print(
        f"Retorno medio:          "
        f"{resultado['retorno_medio']:+.2f}%"
    )


    print(
        f"Mediana:                "
        f"{resultado['retorno_mediana']:+.2f}%"
    )


    print(
        f"% señales positivas:    "
        f"{resultado['porcentaje_positivos']:.1f}%"
    )


    print()


    print(
        f"SPY medio:              "
        f"{resultado['retorno_spy_medio']:+.2f}%"
    )


    print(
        f"Exceso medio vs SPY:    "
        f"{resultado['exceso_spy_medio']:+.2f}pp"
    )


    print(
        f"Mediana exceso vs SPY:  "
        f"{resultado['exceso_spy_mediana']:+.2f}pp"
    )


    print(
        f"% que baten SPY:        "
        f"{resultado['porcentaje_bate_spy']:.1f}%"
    )


    print()


    print(
        f"Mejor señal:            "
        f"{resultado['mejor_resultado']:+.2f}%"
    )


    print(
        f"Peor señal:             "
        f"{resultado['peor_resultado']:+.2f}%"
    )


    print(
        f"Mejor exceso vs SPY:    "
        f"{resultado['mejor_exceso_spy']:+.2f}pp"
    )


    print(
        f"Peor exceso vs SPY:     "
        f"{resultado['peor_exceso_spy']:+.2f}pp"
    )


# ============================================================
# MAIN
# ============================================================

def ejecutar_analisis():

    fechas = obtener_market_dates(
        SCORE_VERSION
    )


    print()

    print(
        "=" * 70
    )

    print(
        "       PERFORMANCE DEL TRADING RADAR"
    )

    print(
        "=" * 70
    )


    print(
        f"Score analizado:       "
        f"{SCORE_VERSION}"
    )


    print(
        f"Sesiones disponibles:  "
        f"{len(fechas)}"
    )


    # --------------------------------------------------------
    # SCORE 85
    # --------------------------------------------------------

    resultado = evaluar_horizonte(
        score_minimo=85,
        sesiones_futuras=5
    )

    imprimir_resultado(
        "SCORE >= 85 | +5 SESIONES",
        resultado
    )


    # --------------------------------------------------------
    # SCORE + FUERZA SPY
    # --------------------------------------------------------

    resultado = evaluar_horizonte(
        score_minimo=85,
        sesiones_futuras=5,
        exigir_rs20_positivo=True,
        exigir_rs60_positivo=True
    )

    imprimir_resultado(
        "SCORE >=85 + RS20/RS60 > 0 | +5 SESIONES",
        resultado
    )


    # --------------------------------------------------------
    # SCORE + SPY + SECTOR
    # --------------------------------------------------------

    resultado = evaluar_horizonte(
        score_minimo=85,
        sesiones_futuras=5,
        exigir_rs20_positivo=True,
        exigir_rs60_positivo=True,
        exigir_sector_positivo=True
    )

    imprimir_resultado(
        "SCORE >=85 + SPY + SECTOR POSITIVOS | +5 SESIONES",
        resultado
    )


    # --------------------------------------------------------
    # 20 SESIONES
    # --------------------------------------------------------

    resultado = evaluar_horizonte(
        score_minimo=85,
        sesiones_futuras=20,
        exigir_rs20_positivo=True,
        exigir_rs60_positivo=True,
        exigir_sector_positivo=True
    )

    imprimir_resultado(
        "SCORE >=85 + SPY + SECTOR POSITIVOS | +20 SESIONES",
        resultado
    )


    # --------------------------------------------------------
    # 60 SESIONES
    # --------------------------------------------------------

    resultado = evaluar_horizonte(
        score_minimo=85,
        sesiones_futuras=60,
        exigir_rs20_positivo=True,
        exigir_rs60_positivo=True,
        exigir_sector_positivo=True
    )

    imprimir_resultado(
        "SCORE >=85 + SPY + SECTOR POSITIVOS | +60 SESIONES",
        resultado
    )


if __name__ == "__main__":

    ejecutar_analisis()