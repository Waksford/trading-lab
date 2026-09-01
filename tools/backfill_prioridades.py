import sqlite3

from pathlib import Path

from analysis.scorer import (
    clasificar_candidato,
    calcular_prioridad_estudio
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

DB_PATH = (
    BASE_DIR
    / "data"
    / "trading.db"
)


# ============================================================
# CONEXIÓN
# ============================================================

conexion = sqlite3.connect(
    DB_PATH
)

conexion.row_factory = sqlite3.Row

cursor = conexion.cursor()


# ============================================================
# OBTENER SCANS V3
# ============================================================

cursor.execute(
    """
    SELECT *

    FROM scans

    WHERE score_version = 'v3'

    ORDER BY
        market_date,
        score DESC
    """
)


filas = cursor.fetchall()


print()

print(
    "======================================"
)

print(
    "     BACKFILL CLASIFICACIÓN V3"
)

print(
    "======================================"
)

print()

print(
    f"Registros V3 encontrados: "
    f"{len(filas)}"
)


actualizados = 0
errores = 0


# ============================================================
# RECALCULAR
# ============================================================

for fila in filas:

    activo = dict(
        fila
    )

    symbol = activo[
        "symbol"
    ]


    try:

        # ====================================================
        # RECONSTRUIR SCORE
        # ====================================================

        score = {

            "version":
                activo.get(
                    "score_version"
                ),

            "total":
                activo.get(
                    "score"
                ) or 0,

            "tendencia":
                activo.get(
                    "score_tendencia"
                ) or 0,

            "momentum":
                activo.get(
                    "score_momentum"
                ) or 0,

            "fuerza_relativa":
                activo.get(
                    "score_fuerza"
                ) or 0,

            "sector":
                activo.get(
                    "score_sector"
                ) or 0,

            "riesgo":
                activo.get(
                    "score_riesgo"
                ) or 0,

            "volumen":
                activo.get(
                    "score_volumen"
                ) or 0,

            "penalizacion_relativa":
                activo.get(
                    "penalizacion_relativa"
                ) or 0
        }


        # ====================================================
        # RECONSTRUIR ANÁLISIS
        # ====================================================

        analisis = {

            "tendencia":
                activo.get(
                    "tendencia"
                ) or "NEUTRAL"
        }


        # ====================================================
        # CLASIFICACIÓN HUMANA
        # ====================================================

        clasificacion = (
            clasificar_candidato(

                score=score,

                analisis=analisis,

                fuerza_20d=(
                    activo.get(
                        "fuerza_20d"
                    ) or 0
                ),

                fuerza_60d=(
                    activo.get(
                        "fuerza_60d"
                    ) or 0
                ),

                fuerza_sector_20d=(
                    activo.get(
                        "fuerza_sector_20d"
                    )
                ),

                fuerza_sector_60d=(
                    activo.get(
                        "fuerza_sector_60d"
                    )
                )
            )
        )


        # ====================================================
        # PRIORIDAD
        # ====================================================

        prioridad = (
            calcular_prioridad_estudio(

                score=score,

                clasificacion=
                    clasificacion,

                rsi=(
                    activo.get(
                        "rsi"
                    ) or 0
                ),

                distancia_sma20=(
                    activo.get(
                        "distancia_sma20"
                    ) or 0
                ),

                distancia_sma50=(
                    activo.get(
                        "distancia_sma50"
                    ) or 0
                ),

                fuerza_sector_20d=(
                    activo.get(
                        "fuerza_sector_20d"
                    )
                ),

                fuerza_sector_60d=(
                    activo.get(
                        "fuerza_sector_60d"
                    )
                )
            )
        )


        # ====================================================
        # ALERTAS
        # ====================================================

        alertas = "|".join(
            prioridad.get(
                "alertas",
                []
            )
        )


        # ====================================================
        # ACTUALIZAR SQLITE
        # ====================================================

        cursor.execute(
            """
            UPDATE scans

            SET
                perfil = ?,
                calidad = ?,
                fortaleza_mercado = ?,
                fortaleza_sector = ?,
                riesgo_clasificacion = ?,
                volumen_clasificacion = ?,

                prioridad_estudio = ?,
                motivo_prioridad = ?,
                alertas_estudio = ?

            WHERE id = ?
            """,
            (
                clasificacion[
                    "perfil"
                ],

                clasificacion[
                    "calidad"
                ],

                clasificacion[
                    "fortaleza_mercado"
                ],

                clasificacion[
                    "fortaleza_sector"
                ],

                clasificacion[
                    "riesgo"
                ],

                clasificacion[
                    "volumen"
                ],

                prioridad[
                    "prioridad"
                ],

                prioridad[
                    "motivo_prioridad"
                ],

                alertas,

                activo[
                    "id"
                ]
            )
        )


        actualizados += 1


    except Exception as e:

        errores += 1

        print(
            f"Error {symbol}: "
            f"{e}"
        )


# ============================================================
# GUARDAR
# ============================================================

conexion.commit()


# ============================================================
# COMPROBAR RESULTADO
# ============================================================

cursor.execute(
    """
    SELECT
        prioridad_estudio,
        COUNT(*) AS cantidad

    FROM scans

    WHERE score_version = 'v3'

    GROUP BY prioridad_estudio

    ORDER BY
        CASE prioridad_estudio
            WHEN 'A+' THEN 1
            WHEN 'A' THEN 2
            WHEN 'B' THEN 3
            WHEN 'C' THEN 4
            WHEN 'D' THEN 5
            ELSE 99
        END
    """
)


resumen = cursor.fetchall()


print()

print(
    "======================================"
)

print(
    "              RESUMEN"
)

print(
    "======================================"
)

print()

print(
    f"Actualizados: {actualizados}"
)

print(
    f"Errores:      {errores}"
)

print()


for fila in resumen:

    prioridad = (
        fila[
            "prioridad_estudio"
        ]
        or "NULL"
    )

    print(
        f"{prioridad:<5} "
        f"{fila['cantidad']:>5}"
    )


conexion.close()