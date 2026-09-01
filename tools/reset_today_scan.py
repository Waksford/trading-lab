from database.db import (
    obtener_conexion,
    DB_PATH
)


print()
print("======================================")
print("       RESET TABLAS DE RADAR")
print("======================================")
print()

print(
    "Base de datos:",
    DB_PATH.resolve()
)


conexion = obtener_conexion()
cursor = conexion.cursor()


# ============================================================
# CONTAR ANTES
# ============================================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM scans
    """
)

scans_antes = cursor.fetchone()[0]


cursor.execute(
    """
    SELECT COUNT(*)
    FROM radar_events
    """
)

eventos_antes = cursor.fetchone()[0]


print(
    f"Scans actuales:   {scans_antes}"
)

print(
    f"Eventos actuales: {eventos_antes}"
)


# ============================================================
# BORRAR SOLO HISTÓRICO DEL RADAR
# ============================================================

cursor.execute(
    """
    DELETE FROM scans
    """
)

cursor.execute(
    """
    DELETE FROM radar_events
    """
)


# También podemos reiniciar IDs
cursor.execute(
    """
    DELETE FROM sqlite_sequence
    WHERE name IN (
        'scans',
        'radar_events'
    )
    """
)


conexion.commit()


# ============================================================
# COMPROBAR
# ============================================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM scans
    """
)

scans_despues = cursor.fetchone()[0]


cursor.execute(
    """
    SELECT COUNT(*)
    FROM radar_events
    """
)

eventos_despues = cursor.fetchone()[0]


conexion.close()


print()
print(
    f"Scans después:   {scans_despues}"
)

print(
    f"Eventos después: {eventos_despues}"
)

print()
print(
    "company_metadata NO se ha modificado."
)

print(
    "Ya puedes ejecutar main.py."
)