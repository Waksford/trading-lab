import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# RUTA BASE DE DATOS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "trading.db"


# ============================================================
# CONEXIÓN
# ============================================================

def obtener_conexion():
    """
    Abre una conexión a SQLite.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    conexion = sqlite3.connect(
        DB_PATH
    )

    conexion.row_factory = sqlite3.Row

    return conexion


# ============================================================
# CREAR TABLAS
# ============================================================

def inicializar_db():
    """
    Crea la tabla scans si todavía no existe.

    Para instalaciones nuevas crea ya el esquema completo.
    Las funciones asegurar_* siguen existiendo para migrar
    bases de datos creadas con versiones anteriores.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            scan_time TEXT NOT NULL,
            market_date TEXT,

            symbol TEXT NOT NULL,
            nombre TEXT,
            exchange TEXT,

            precio REAL,

            score INTEGER,
            score_version TEXT,

            tendencia TEXT,
            momentum TEXT,
            volatilidad TEXT,

            rsi REAL,
            volumen_relativo REAL,

            return_20d REAL,
            return_60d REAL,

            fuerza_20d REAL,
            fuerza_60d REAL,

            score_tendencia INTEGER,
            score_momentum INTEGER,
            score_fuerza INTEGER,
            score_sector INTEGER,
            score_continuacion INTEGER,
            score_riesgo INTEGER,
            score_volumen INTEGER,

            penalizacion_relativa INTEGER,

            distancia_sma20 REAL,
            distancia_sma50 REAL,

            sector TEXT,
            sector_benchmark TEXT,

            fuerza_sector_20d REAL,
            fuerza_sector_60d REAL,

            perfil TEXT,
            calidad TEXT,
            fortaleza_mercado TEXT,
            fortaleza_sector TEXT,
            riesgo_clasificacion TEXT,
            volumen_clasificacion TEXT,

            prioridad_estudio TEXT,
            motivo_prioridad TEXT,
            alertas_estudio TEXT,

            reversal_candidate INTEGER DEFAULT 0,
            reversal_version TEXT,
            reversal_priority TEXT,
            reversal_reason TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_scans_symbol
        ON scans(symbol)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_scans_scan_time
        ON scans(scan_time)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_scans_market_date
        ON scans(market_date)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_scans_score_version
        ON scans(score_version)
        """
    )

    conexion.commit()
    conexion.close()
    inicializar_tabla_fundamentales()
    inicializar_tabla_fundamental_classification()

def guardar_scan(
    ranking,
    market_date,
    scan_time_override=None
):
    """
    Guarda en SQLite todos los activos analizados
    durante una sesión bursátil.

    Persiste:
    - métricas técnicas,
    - score tecnico y version,
    - fuerza contra SPY,
    - fuerza contra sector,
    - clasificación humana,
    - prioridad de estudio y alertas.
    """

    if not ranking:
        return 0

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    scan_time = (
        scan_time_override

        if scan_time_override

        else datetime.now().isoformat(
            timespec="seconds"
        )
    )

    filas = []

    for activo in ranking:

        alertas = activo.get(
            "alertas_estudio",
            []
        )

        if isinstance(
            alertas,
            (list, tuple, set)
        ):
            alertas_texto = "|".join(
                str(alerta)
                for alerta in alertas
                if alerta
            )
        elif alertas:
            alertas_texto = str(
                alertas
            )
        else:
            alertas_texto = ""

        filas.append(
            (
                # Sesión
                scan_time,
                market_date,

                # Identidad
                activo.get("symbol"),
                activo.get("nombre"),
                activo.get("exchange"),

                # Precio / score
                activo.get("precio"),
                activo.get("score"),
                activo.get("score_version"),

                # Interpretación técnica
                activo.get("tendencia"),
                activo.get("momentum"),
                activo.get("volatilidad"),

                # Indicadores
                activo.get("rsi"),
                activo.get("volumen_relativo"),

                # Retornos
                activo.get("return_20d"),
                activo.get("return_60d"),

                # Fuerza vs SPY
                activo.get("fuerza_20d"),
                activo.get("fuerza_60d"),

                # Componentes score
                activo.get("score_tendencia"),
                activo.get("score_momentum"),
                activo.get("score_fuerza"),
                activo.get("score_sector"),
                activo.get("score_continuacion"),
                activo.get("score_riesgo"),
                activo.get("score_volumen"),

                # Penalización
                activo.get("penalizacion_relativa"),

                # Distancias
                activo.get("distancia_sma20"),
                activo.get("distancia_sma50"),

                # Sector
                activo.get("sector"),
                activo.get("sector_benchmark"),
                activo.get("fuerza_sector_20d"),
                activo.get("fuerza_sector_60d"),

                # Clasificación humana
                activo.get("perfil"),
                activo.get("calidad"),
                activo.get("fortaleza_mercado"),
                activo.get("fortaleza_sector"),
                activo.get("riesgo_clasificacion"),
                activo.get("volumen_clasificacion"),

                # Prioridad
                activo.get("prioridad_estudio"),
                activo.get("motivo_prioridad"),
                alertas_texto,

                # Reversal V1
                activo.get("reversal_candidate", 0),
                activo.get("reversal_version"),
                activo.get("reversal_priority"),
                activo.get("reversal_reason")
            )
        )

    cursor.executemany(
        """
        INSERT INTO scans (

            scan_time,
            market_date,

            symbol,
            nombre,
            exchange,

            precio,
            score,
            score_version,

            tendencia,
            momentum,
            volatilidad,

            rsi,
            volumen_relativo,

            return_20d,
            return_60d,

            fuerza_20d,
            fuerza_60d,

            score_tendencia,
            score_momentum,
            score_fuerza,
            score_sector,
            score_continuacion,
            score_riesgo,
            score_volumen,

            penalizacion_relativa,

            distancia_sma20,
            distancia_sma50,

            sector,
            sector_benchmark,
            fuerza_sector_20d,
            fuerza_sector_60d,

            perfil,
            calidad,
            fortaleza_mercado,
            fortaleza_sector,
            riesgo_clasificacion,
            volumen_clasificacion,

            prioridad_estudio,
            motivo_prioridad,
            alertas_estudio,

            reversal_candidate,
            reversal_version,
            reversal_priority,
            reversal_reason

        )
        VALUES (
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?
        )
        """,
        filas
    )

    conexion.commit()

    cantidad = len(
        filas
    )

    conexion.close()

    return cantidad


def obtener_historial_symbol(
    symbol,
    limite=30
):
    """
    Devuelve los últimos registros guardados
    para un ticker.
    """

    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE symbol = ?

        ORDER BY scan_time DESC

        LIMIT ?
        """,
        (
            symbol.upper(),
            limite
        )
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# ÚLTIMA EJECUCIÓN
# ============================================================

def obtener_ultimo_scan():
    """
    Devuelve todos los activos correspondientes
    a la última ejecución guardada.
    """

    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT MAX(scan_time)
        AS ultimo_scan
        FROM scans
        """
    )

    resultado = cursor.fetchone()

    if (
        resultado is None
        or resultado["ultimo_scan"] is None
    ):

        conexion.close()

        return []

    ultimo_scan = (
        resultado["ultimo_scan"]
    )

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE scan_time = ?

        ORDER BY score DESC
        """,
        (
            ultimo_scan,
        )
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]
def obtener_scan_times(
    limite=2
):
    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT DISTINCT scan_time

        FROM scans

        ORDER BY scan_time DESC

        LIMIT ?
        """,
        (limite,)
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        fila["scan_time"]
        for fila in filas
    ]


def obtener_scan_por_fecha(
    scan_time
):
    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE scan_time = ?

        ORDER BY score DESC
        """,
        (scan_time,)
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


def inicializar_tabla_eventos():
    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS radar_events (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            event_time TEXT NOT NULL,

            symbol TEXT NOT NULL,

            tipo TEXT NOT NULL,

            mensaje TEXT,

            score_actual INTEGER,

            score_anterior INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_time
        ON radar_events(event_time)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_symbol
        ON radar_events(symbol)
        """
    )

    conexion.commit()

    conexion.close()


def guardar_eventos(
    eventos
):
    if not eventos:
        return 0

    conexion = obtener_conexion()

    cursor = conexion.cursor()

    event_time = datetime.now().isoformat(
        timespec="seconds"
    )

    filas = []

    for evento in eventos:

        filas.append(
            (
                event_time,
                evento["symbol"],
                evento["tipo"],
                evento["mensaje"],
                evento.get("score_actual"),
                evento.get("score_anterior")
            )
        )

    cursor.executemany(
        """
        INSERT INTO radar_events (
            event_time,
            symbol,
            tipo,
            mensaje,
            score_actual,
            score_anterior
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        filas
    )

    conexion.commit()

    conexion.close()

    return len(filas)


def obtener_eventos_recientes(
    limite=50
):
    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM radar_events

        ORDER BY event_time DESC

        LIMIT ?
        """,
        (limite,)
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]
def asegurar_columna_market_date():
    """
    Añade market_date a la tabla scans
    si la base fue creada con una versión anterior.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(scans)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    if "market_date" not in columnas:

        cursor.execute(
            """
            ALTER TABLE scans
            ADD COLUMN market_date TEXT
            """
        )

        conexion.commit()

        print(
            "Migración DB: añadida columna market_date."
        )

    conexion.close()

def existe_market_date(
    market_date,
    score_version=None
):
    """
    Comprueba si una sesion bursatil ya esta guardada.

    Si score_version se indica, la comprobacion se limita
    a esa version del score. Esto permite conservar V3 y V4
    para la misma market_date sin considerarlos duplicados.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    if score_version:

        cursor.execute(
            """
            SELECT 1
            FROM scans
            WHERE market_date = ?
              AND score_version = ?
            LIMIT 1
            """,
            (
                market_date,
                score_version
            )
        )

    else:

        cursor.execute(
            """
            SELECT 1
            FROM scans
            WHERE market_date = ?
            LIMIT 1
            """,
            (
                market_date,
            )
        )

    existe = (
        cursor.fetchone()
        is not None
    )

    conexion.close()

    return existe


def inicializar_tabla_benchmark():
    """
    Guarda una fila por sesión para SPY.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_scans (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_date TEXT NOT NULL UNIQUE,

            scan_time TEXT NOT NULL,

            symbol TEXT NOT NULL,

            precio REAL NOT NULL,

            return_20d REAL,

            return_60d REAL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_benchmark_market_date
        ON benchmark_scans(market_date)
        """
    )

    conexion.commit()
    conexion.close()


def guardar_benchmark_spy(
    market_date,
    precio,
    return_20d,
    return_60d
):
    """
    Guarda SPY una única vez por sesión.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    scan_time = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO benchmark_scans (

            market_date,
            scan_time,
            symbol,
            precio,
            return_20d,
            return_60d

        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            market_date,
            scan_time,
            "SPY",
            precio,
            return_20d,
            return_60d
        )
    )

    conexion.commit()

    insertados = cursor.rowcount

    conexion.close()

    return insertados


def obtener_benchmark_por_fecha(
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
        (market_date,)
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(fila)
def inicializar_tabla_company_metadata():
    """
    Metadata fundamental de las empresas.

    Esta información no necesita descargarse
    en cada ejecución del radar.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_metadata (

            symbol TEXT PRIMARY KEY,

            cik TEXT,

            sic INTEGER,

            sic_description TEXT,

            sector TEXT,

            source TEXT,

            updated_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()
def obtener_company_metadata(symbol):
    """
    Devuelve la metadata almacenada de un ticker.
    """

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM company_metadata
        WHERE symbol = ?
        """,
        (symbol,)
    )

    fila = cursor.fetchone()

    conn.close()

    if fila is None:
        return None

    return dict(fila)


def guardar_company_metadata(
    symbol,
    cik,
    sic,
    sic_description,
    sector,
    source="SEC"
):
    """
    Guarda o actualiza metadata de una empresa.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO company_metadata (
            symbol,
            cik,
            sic,
            sic_description,
            sector,
            source,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(symbol)
        DO UPDATE SET

            cik = excluded.cik,
            sic = excluded.sic,
            sic_description = excluded.sic_description,
            sector = excluded.sector,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        (
            symbol,
            cik,
            sic,
            sic_description,
            sector,
            source,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()
def obtener_metadata_unknown():
    """
    Devuelve las empresas cuyo sector
    todavía no hemos podido clasificar.
    """

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            symbol,
            cik,
            sic,
            sic_description,
            sector,
            source
        FROM company_metadata
        WHERE sector = 'Unknown'
        ORDER BY sic, symbol
        """
    )

    filas = cursor.fetchall()

    conn.close()

    return [
        dict(fila)
        for fila in filas
    ]
def asegurar_columna_asset_type():
    """
    Añade asset_type a company_metadata
    si todavía no existe.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(company_metadata)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    if "asset_type" not in columnas:

        cursor.execute(
            """
            ALTER TABLE company_metadata
            ADD COLUMN asset_type TEXT
            """
        )

        conexion.commit()

        print(
            "Migración DB: añadida columna asset_type."
        )

    conexion.close()
def actualizar_asset_type(
    symbol,
    asset_type
):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        UPDATE company_metadata
        SET
            asset_type = ?,
            updated_at = ?
        WHERE symbol = ?
        """,
        (
            asset_type,
            datetime.now().isoformat(
                timespec="seconds"
            ),
            symbol.upper()
        )
    )

    conexion.commit()
    conexion.close()

def obtener_toda_company_metadata():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *
        FROM company_metadata
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]
def obtener_operating_company_symbols():
    """
    Devuelve los tickers clasificados como
    empresas operativas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT symbol
        FROM company_metadata
        WHERE asset_type = 'OPERATING_COMPANY'
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return {
        fila["symbol"]
        for fila in filas
    }


def obtener_resumen_asset_types():
    """
    Devuelve cuántos activos tenemos
    de cada tipo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT
            COALESCE(asset_type, 'NULL') AS asset_type,
            COUNT(*) AS cantidad
        FROM company_metadata
        GROUP BY asset_type
        ORDER BY cantidad DESC
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return {
        fila["asset_type"]: fila["cantidad"]
        for fila in filas
    }
def obtener_sectores_operating_companies():
    """
    Devuelve:

    {
        "AAPL": "Technology",
        "JPM": "Financials",
        ...
    }

    Solo incluye empresas operativas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT
            symbol,
            sector

        FROM company_metadata

        WHERE asset_type = 'OPERATING_COMPANY'

        AND sector IS NOT NULL

        AND sector != ''

        AND sector != 'Unknown'
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return {
        fila["symbol"]: fila["sector"]
        for fila in filas
    }
def asegurar_columnas_sectoriales():
    """
    Añade las columnas sectoriales a la tabla scans
    si todavía no existen.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(scans)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    nuevas_columnas = {
        "sector": "TEXT",
        "sector_benchmark": "TEXT",
        "fuerza_sector_20d": "REAL",
        "fuerza_sector_60d": "REAL"
    }

    for columna, tipo in nuevas_columnas.items():

        if columna not in columnas:

            cursor.execute(
                f"""
                ALTER TABLE scans
                ADD COLUMN {columna} {tipo}
                """
            )

            print(
                f"Migración DB: añadida columna {columna}."
            )

    conexion.commit()
    conexion.close()

def actualizar_sector_metadata(
    symbol,
    sector
):
    """
    Actualiza únicamente el sector calculado
    de una empresa ya existente.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        UPDATE company_metadata

        SET
            sector = ?,
            updated_at = ?

        WHERE symbol = ?
        """,
        (
            sector,
            datetime.now().isoformat(
                timespec="seconds"
            ),
            symbol.upper()
        )
    )

    conexion.commit()
    conexion.close()
    
def asegurar_columnas_score_v3():
    """
    Añade columnas propias del Score V3.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(scans)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    nuevas_columnas = {
        "score_version": "TEXT",
        "score_sector": "INTEGER"
    }

    for columna, tipo in nuevas_columnas.items():

        if columna not in columnas:

            cursor.execute(
                f"""
                ALTER TABLE scans
                ADD COLUMN {columna} {tipo}
                """
            )

            print(
                f"Migración DB: añadida columna "
                f"{columna}."
            )

    conexion.commit()
    conexion.close()
def asegurar_columnas_v4_reversal():
    """
    Anade las columnas introducidas por Momentum V4
    y Reversal V1 sin modificar los registros historicos V3.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(scans)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    nuevas_columnas = {
        "score_continuacion": "INTEGER",
        "reversal_candidate": "INTEGER DEFAULT 0",
        "reversal_version": "TEXT",
        "reversal_priority": "TEXT",
        "reversal_reason": "TEXT"
    }

    for columna, tipo in nuevas_columnas.items():

        if columna not in columnas:

            cursor.execute(
                f"""
                ALTER TABLE scans
                ADD COLUMN {columna} {tipo}
                """
            )

            print(
                f"Migracion DB: anadida columna "
                f"{columna}."
            )

    conexion.commit()
    conexion.close()


def asegurar_columnas_clasificacion():
    """
    Añade a scans las columnas de interpretación humana
    y prioridad de estudio.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        PRAGMA table_info(scans)
        """
    )

    columnas = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    nuevas_columnas = {
        "perfil": "TEXT",
        "calidad": "TEXT",
        "fortaleza_mercado": "TEXT",
        "fortaleza_sector": "TEXT",
        "riesgo_clasificacion": "TEXT",
        "volumen_clasificacion": "TEXT",
        "prioridad_estudio": "TEXT",
        "motivo_prioridad": "TEXT",
        "alertas_estudio": "TEXT"
    }

    for columna, tipo in nuevas_columnas.items():

        if columna not in columnas:

            cursor.execute(
                f"""
                ALTER TABLE scans
                ADD COLUMN {columna} {tipo}
                """
            )

            print(
                f"Migración DB: añadida columna "
                f"{columna}."
            )

    conexion.commit()
    conexion.close()
# ============================================================
# PAPER TRADING / SIMULACIÓN
# ============================================================

PAPER_VARIANTS_START_DATE = "2026-08-25"
PAPER_PORTFOLIO_START_DATE = "2026-08-25"
ETF_FORWARD_START_DATE = "2026-09-02"


def _migrar_variantes_paper(cursor):
    """Amplia de forma idempotente el esquema paper historico."""

    cursor.execute("PRAGMA table_info(paper_results)")
    columnas_resultados = {fila["name"] for fila in cursor.fetchall()}

    for columna, tipo in {
        "variant": "TEXT NOT NULL DEFAULT 'BASE'",
        "exit_reason": "TEXT",
        "planned_exit_date": "TEXT",
        "actual_exit_date": "TEXT",
        "holding_sessions_real": "INTEGER",
    }.items():
        if columna not in columnas_resultados:
            cursor.execute(
                f"ALTER TABLE paper_results ADD COLUMN {columna} {tipo}"
            )

    cursor.execute(
        "UPDATE paper_results SET variant = 'BASE' "
        "WHERE variant IS NULL OR variant = ''"
    )
    cursor.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'paper_signals'"
    )
    sql_normalizado = "".join(cursor.fetchone()["sql"].lower().split())

    if (
        "unique(market_date,symbol,score_version,strategy,variant)"
        in sql_normalizado
    ):
        return

    cursor.execute(
        """
        CREATE TABLE paper_signals_nueva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_date TEXT NOT NULL, scan_time TEXT,
            symbol TEXT NOT NULL, nombre TEXT, score INTEGER,
            score_version TEXT,
            strategy TEXT NOT NULL DEFAULT 'MOMENTUM',
            source_score_version TEXT,
            variant TEXT NOT NULL DEFAULT 'BASE',
            prioridad TEXT, perfil TEXT, sector TEXT,
            sector_benchmark TEXT, precio_senal REAL, alertas TEXT,
            estado TEXT NOT NULL DEFAULT 'PENDIENTE',
            created_at TEXT NOT NULL,
            UNIQUE(market_date, symbol, score_version, strategy, variant)
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO paper_signals_nueva
        SELECT id, market_date, scan_time, symbol, nombre, score,
               score_version, strategy, source_score_version,
               COALESCE(NULLIF(variant, ''), 'BASE'),
               prioridad, perfil, sector, sector_benchmark, precio_senal,
               alertas, estado, created_at
        FROM paper_signals
        """
    )
    cursor.execute("DROP TABLE paper_signals")
    cursor.execute("ALTER TABLE paper_signals_nueva RENAME TO paper_signals")

    for nombre, columna in (
        ("idx_paper_signals_date", "market_date"),
        ("idx_paper_signals_strategy", "strategy"),
        ("idx_paper_signals_symbol", "symbol"),
        ("idx_paper_signals_priority", "prioridad"),
    ):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {nombre} ON paper_signals({columna})"
        )


def inicializar_tablas_paper():
    """
    Crea las tablas utilizadas para seguir
    las señales del radar de forma virtual.

    paper_signals:
        snapshot de la señal cuando aparece.

    paper_results:
        resultado posterior a 5/20/60 sesiones.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    # ========================================================
    # SEÑALES
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_signals (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_date TEXT NOT NULL,
            scan_time TEXT,

            symbol TEXT NOT NULL,
            nombre TEXT,

            score INTEGER,
            score_version TEXT,

            strategy TEXT NOT NULL
                DEFAULT 'MOMENTUM',

            source_score_version TEXT,

            variant TEXT NOT NULL DEFAULT 'BASE',

            prioridad TEXT,
            perfil TEXT,

            sector TEXT,
            sector_benchmark TEXT,

            precio_senal REAL,

            alertas TEXT,

            estado TEXT NOT NULL
                DEFAULT 'PENDIENTE',

            created_at TEXT NOT NULL,

            UNIQUE(
                market_date,
                symbol,
                score_version,
                strategy,
                variant
            )
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_signals_date

        ON paper_signals(
            market_date
        )
        """
    )


    # Las instalaciones anteriores solo identificaban la señal
    # por score_version. Conservamos ese histórico como MOMENTUM
    # y añadimos la versión del scan que originó cada estrategia.

    cursor.execute(
        """
        PRAGMA table_info(paper_signals)
        """
    )

    columnas_paper = {
        fila["name"]
        for fila in cursor.fetchall()
    }

    nuevas_columnas_paper = {
        "strategy": "TEXT NOT NULL DEFAULT 'MOMENTUM'",
        "source_score_version": "TEXT",
        "variant": "TEXT NOT NULL DEFAULT 'BASE'"
    }

    for columna, tipo in nuevas_columnas_paper.items():

        if columna not in columnas_paper:

            cursor.execute(
                f"""
                ALTER TABLE paper_signals
                ADD COLUMN {columna} {tipo}
                """
            )

            print(
                "Migracion DB: anadida columna paper_signals."
                f"{columna}."
            )


    cursor.execute(
        """
        UPDATE paper_signals
        SET
            strategy = 'MOMENTUM',
            source_score_version = score_version
        WHERE
            strategy IS NULL
            OR strategy = ''
            OR source_score_version IS NULL
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_signals_strategy

        ON paper_signals(
            strategy
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_signals_symbol

        ON paper_signals(
            symbol
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_signals_priority

        ON paper_signals(
            prioridad
        )
        """
    )


    # ========================================================
    # RESULTADOS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_results (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            signal_id INTEGER NOT NULL,

            horizonte INTEGER NOT NULL,

            fecha_entrada TEXT NOT NULL,
            precio_entrada REAL NOT NULL,

            fecha_salida TEXT NOT NULL,
            precio_salida REAL NOT NULL,

            retorno REAL NOT NULL,

            retorno_spy REAL NOT NULL,

            exceso_spy REAL NOT NULL,

            max_subida REAL,

            max_caida REAL,

            max_drawdown REAL,

            variant TEXT NOT NULL DEFAULT 'BASE',
            exit_reason TEXT,
            planned_exit_date TEXT,
            actual_exit_date TEXT,
            holding_sessions_real INTEGER,

            created_at TEXT NOT NULL,

            UNIQUE(
                signal_id,
                horizonte
            ),

            FOREIGN KEY(
                signal_id
            )
            REFERENCES paper_signals(id)
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_results_signal

        ON paper_results(
            signal_id
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_paper_results_horizonte

        ON paper_results(
            horizonte
        )
        """
    )


    _migrar_variantes_paper(
        cursor
    )


    conexion.commit()
    conexion.close()


# ============================================================
# SINCRONIZAR SCANS -> PAPER SIGNALS
# ============================================================

def sincronizar_senales_paper(
    score_version="v3",
    prioridades=(
        "A+",
        "A",
        "B"
    ),
    strategy="MOMENTUM"
):
    """
    Copia las señales relevantes desde scans
    a paper_signals.

    INSERT OR IGNORE evita duplicados.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    strategy = str(strategy).strip().upper()

    if strategy not in (
        "MOMENTUM",
        "REVERSAL"
    ):
        conexion.close()
        raise ValueError(
            "strategy debe ser MOMENTUM o REVERSAL"
        )


    placeholders = ",".join(
        "?"
        for _ in prioridades
    )


    if strategy == "MOMENTUM":

        cursor.execute(
            f"""
        SELECT

            market_date,
            scan_time,

            symbol,
            nombre,

            score,
            score_version,

            prioridad_estudio,
            perfil,

            sector,
            sector_benchmark,

            precio,

            alertas_estudio

        FROM scans

        WHERE score_version = ?

        AND prioridad_estudio IN (
            {placeholders}
        )

        AND market_date IS NOT NULL

        ORDER BY
            market_date ASC,
            score DESC
        """,
        (
            score_version,
            *prioridades
        )
        )

    else:

        cursor.execute(
            f"""
        SELECT

            market_date,
            scan_time,

            symbol,
            nombre,

            score,
            reversal_version AS score_version,
            score_version AS source_score_version,

            reversal_priority AS prioridad_estudio,
            perfil,

            sector,
            sector_benchmark,

            precio,

            reversal_reason AS alertas_estudio

        FROM scans

        WHERE score_version = ?

        AND reversal_candidate = 1

        AND reversal_priority IN (
            {placeholders}
        )

        AND reversal_version IS NOT NULL

        AND market_date IS NOT NULL

        ORDER BY
            market_date ASC,
            score DESC
        """,
            (
                score_version,
                *prioridades
            )
        )


    scans = cursor.fetchall()


    antes = conexion.total_changes


    ahora = datetime.now().isoformat(
        timespec="seconds"
    )


    for activo in scans:

        variantes = ["BASE"]

        if activo["market_date"] >= PAPER_VARIANTS_START_DATE:

            if strategy == "MOMENTUM":
                variantes.append("TP25")

            elif strategy == "REVERSAL":
                variantes.append("TP10")

        for variante in variantes:

            cursor.execute(
            """
            INSERT OR IGNORE INTO paper_signals (

                market_date,
                scan_time,

                symbol,
                nombre,

                score,
                score_version,

                strategy,
                source_score_version,
                variant,

                prioridad,
                perfil,

                sector,
                sector_benchmark,

                precio_senal,

                alertas,

                estado,

                created_at

            )
            VALUES (
                ?, ?,
                ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?,
                ?,
                'PENDIENTE',
                ?
            )
            """,
            (
                activo[
                    "market_date"
                ],

                activo[
                    "scan_time"
                ],

                activo[
                    "symbol"
                ],

                activo[
                    "nombre"
                ],

                activo[
                    "score"
                ],

                activo[
                    "score_version"
                ],

                strategy,

                (
                    activo["source_score_version"]
                    if "source_score_version" in activo.keys()
                    else activo["score_version"]
                ),

                variante,

                activo[
                    "prioridad_estudio"
                ],

                activo[
                    "perfil"
                ],

                activo[
                    "sector"
                ],

                activo[
                    "sector_benchmark"
                ],

                activo[
                    "precio"
                ],

                activo[
                    "alertas_estudio"
                ],

                ahora
            )
        )


    insertadas = (
        conexion.total_changes
        - antes
    )


    conexion.commit()
    conexion.close()

    return insertadas


# ============================================================
# SEÑALES INCOMPLETAS
# ============================================================

def obtener_senales_paper_incompletas(
    strategy=None,
    variant=None
):
    """
    Devuelve señales que todavía no tienen
    los tres resultados:

    5D
    20D
    60D
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    filtros = []
    parametros = []

    if strategy:
        filtros.append("ps.strategy = ?")
        parametros.append(str(strategy).strip().upper())

    if variant:
        filtros.append("ps.variant = ?")
        parametros.append(str(variant).strip().upper())

    clausula_where = (
        "WHERE " + " AND ".join(filtros)
        if filtros
        else ""
    )


    cursor.execute(
        f"""
        SELECT

            ps.*,

            COUNT(
                pr.id
            ) AS resultados_guardados

        FROM paper_signals ps

        LEFT JOIN paper_results pr

        ON pr.signal_id = ps.id

        {clausula_where}

        GROUP BY ps.id

        HAVING COUNT(
            pr.id
        ) < CASE
            WHEN ps.variant = 'BASE' THEN 3
            ELSE 1
        END

        ORDER BY
            ps.market_date ASC,
            ps.score DESC
        """,
        tuple(parametros)
    )


    filas = cursor.fetchall()

    conexion.close()


    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# HORIZONTES YA CALCULADOS
# ============================================================

def obtener_horizontes_paper(
    signal_id
):
    """
    Devuelve por ejemplo:

    {5, 20}
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    cursor.execute(
        """
        SELECT horizonte

        FROM paper_results

        WHERE signal_id = ?
        """,
        (
            signal_id,
        )
    )


    filas = cursor.fetchall()

    conexion.close()


    return {
        fila[
            "horizonte"
        ]
        for fila in filas
    }


# ============================================================
# GUARDAR RESULTADO
# ============================================================

def guardar_resultado_paper(
    resultado
):
    """
    Guarda un resultado maduro.

    Después actualiza automáticamente
    el estado de la señal.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    cursor.execute(
        """
        INSERT OR IGNORE INTO paper_results (

            signal_id,

            horizonte,

            fecha_entrada,
            precio_entrada,

            fecha_salida,
            precio_salida,

            retorno,

            retorno_spy,

            exceso_spy,

            max_subida,

            max_caida,

            max_drawdown,

            variant,
            exit_reason,
            planned_exit_date,
            actual_exit_date,
            holding_sessions_real,

            created_at

        )
        VALUES (
            ?,
            ?,
            ?, ?,
            ?, ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            resultado[
                "signal_id"
            ],

            resultado[
                "horizonte"
            ],

            resultado[
                "fecha_entrada"
            ],

            resultado[
                "precio_entrada"
            ],

            resultado[
                "fecha_salida"
            ],

            resultado[
                "precio_salida"
            ],

            resultado[
                "retorno"
            ],

            resultado[
                "retorno_spy"
            ],

            resultado[
                "exceso_spy"
            ],

            resultado[
                "max_subida"
            ],

            resultado[
                "max_caida"
            ],

            resultado[
                "max_drawdown"
            ],

            resultado.get("variant", "BASE"),
            resultado.get("exit_reason", "TIME"),
            resultado.get("planned_exit_date", resultado["fecha_salida"]),
            resultado.get("actual_exit_date", resultado["fecha_salida"]),
            resultado.get("holding_sessions_real", resultado["horizonte"]),

            datetime.now().isoformat(
                timespec="seconds"
            )
        )
    )


    insertados = cursor.rowcount


    # ========================================================
    # ACTUALIZAR ESTADO
    # ========================================================

    cursor.execute(
        "SELECT variant FROM paper_signals WHERE id = ?",
        (resultado["signal_id"],)
    )
    fila_senal = cursor.fetchone()
    resultados_esperados = (
        3
        if fila_senal is None or fila_senal["variant"] == "BASE"
        else 1
    )

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM paper_results

        WHERE signal_id = ?
        """,
        (
            resultado[
                "signal_id"
            ],
        )
    )


    cantidad = cursor.fetchone()[0]


    if cantidad >= resultados_esperados:

        estado = "COMPLETA"

    elif cantidad >= 1:

        estado = "PARCIAL"

    else:

        estado = "PENDIENTE"


    cursor.execute(
        """
        UPDATE paper_signals

        SET estado = ?

        WHERE id = ?
        """,
        (
            estado,

            resultado[
                "signal_id"
            ]
        )
    )


    conexion.commit()
    conexion.close()

    return insertados


# ============================================================
# TODOS LOS RESULTADOS
# ============================================================

def obtener_resultados_paper(
    strategy=None,
    source_score_version=None,
    variant=None
):
    """
    Devuelve resultados paper junto
    con información de la señal original.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    cursor.execute(
        """
        SELECT

            pr.*,

            ps.market_date,
            ps.symbol,
            ps.nombre,

            ps.score,
            ps.score_version,
            ps.strategy,
            ps.source_score_version,

            ps.prioridad,
            ps.perfil,

            ps.sector,
            ps.sector_benchmark,

            ps.precio_senal,

            ps.alertas,

            ps.estado

        FROM paper_results pr

        INNER JOIN paper_signals ps

        ON ps.id = pr.signal_id

        WHERE (
            ? IS NULL
            OR ps.strategy = ?
        )

        AND (
            ? IS NULL
            OR ps.source_score_version = ?
        )

        AND (
            ? IS NULL
            OR ps.variant = ?
        )

        ORDER BY
            pr.fecha_salida DESC,
            ps.score DESC
        """,
        (
            (
                str(strategy).strip().upper()
                if strategy
                else None
            ),
            (
                str(strategy).strip().upper()
                if strategy
                else None
            ),
            (
                str(source_score_version).strip().lower()
                if source_score_version
                else None
            ),
            (
                str(source_score_version).strip().lower()
                if source_score_version
                else None
            ),
            (
                str(variant).strip().upper()
                if variant
                else None
            ),
            (
                str(variant).strip().upper()
                if variant
                else None
            )
        )
    )


    filas = cursor.fetchall()

    conexion.close()


    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# RESUMEN DE SEÑALES
# ============================================================

def obtener_resumen_paper(
    strategy=None,
    source_score_version=None,
    variant=None
):
    """
    Resumen para consola / weekly.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    strategy_normalizada = (
        str(strategy).strip().upper()
        if strategy
        else None
    )

    source_version_normalizada = (
        str(source_score_version).strip().lower()
        if source_score_version
        else None
    )

    variant_normalizada = (
        str(variant).strip().upper()
        if variant
        else None
    )


    cursor.execute(
        """
        SELECT

            strategy,
            variant,
            prioridad,
            estado,

            COUNT(*) AS cantidad

        FROM paper_signals

        WHERE (
            ? IS NULL
            OR strategy = ?
        )

        AND (
            ? IS NULL
            OR source_score_version = ?
        )

        AND (
            ? IS NULL
            OR variant = ?
        )

        GROUP BY
            strategy,
            variant,
            prioridad,
            estado

        ORDER BY
            prioridad,
            estado
        """,
        (
            strategy_normalizada,
            strategy_normalizada,
            source_version_normalizada,
            source_version_normalizada,
            variant_normalizada,
            variant_normalizada
        )
    )


    filas = cursor.fetchall()


    cursor.execute(
        """
        SELECT

            ps.strategy,
            ps.variant,
            horizonte,

            COUNT(*) AS cantidad

        FROM paper_results pr

        INNER JOIN paper_signals ps

        ON ps.id = pr.signal_id

        WHERE (
            ? IS NULL
            OR ps.strategy = ?
        )

        AND (
            ? IS NULL
            OR ps.source_score_version = ?
        )

        AND (
            ? IS NULL
            OR ps.variant = ?
        )

        GROUP BY
            ps.strategy,
            ps.variant,
            horizonte

        ORDER BY
            ps.strategy,
            horizonte
        """,
        (
            strategy_normalizada,
            strategy_normalizada,
            source_version_normalizada,
            source_version_normalizada,
            variant_normalizada,
            variant_normalizada
        )
    )


    resultados = (
        cursor.fetchall()
    )


    conexion.close()


    return {

        "senales": [
            dict(fila)
            for fila in filas
        ],

        "resultados": [
            dict(fila)
            for fila in resultados
        ]
    }


# ============================================================
# ANALYST CONSENSUS SNAPSHOTS
# ============================================================

def inicializar_tabla_analyst_consensus():
    """
    Crea la tabla independiente de consenso de analistas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analyst_consensus_snapshots (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_time TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            symbol TEXT NOT NULL,

            price_internal REAL,
            price_yahoo REAL,

            target_low REAL,
            target_high REAL,
            target_mean REAL,
            target_median REAL,

            upside_mean_pct REAL,
            upside_median_pct REAL,

            strong_buy INTEGER,
            buy INTEGER,
            hold INTEGER,
            sell INTEGER,
            strong_sell INTEGER,
            analyst_count INTEGER,
            consensus_score REAL,

            recommendation_period TEXT,

            eps_0q REAL,
            eps_next_q REAL,
            eps_0y REAL,
            eps_next_y REAL,
            eps_growth_0y REAL,
            eps_growth_next_y REAL,
            eps_analysts_0y INTEGER,
            eps_analysts_next_y INTEGER,

            source TEXT NOT NULL DEFAULT 'YAHOO',
            created_at TEXT,

            UNIQUE(
                snapshot_date,
                symbol,
                source
            )
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_analyst_consensus_symbol

        ON analyst_consensus_snapshots(symbol)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_analyst_consensus_date

        ON analyst_consensus_snapshots(snapshot_date)
        """
    )

    conexion.commit()
    conexion.close()


def inicializar_tablas_paper_portfolio():
    """Inicializa la persistencia de las carteras paper live."""

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS paper_portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            strategy TEXT NOT NULL,
            source_score_version TEXT,
            initial_capital REAL NOT NULL,
            current_cash REAL NOT NULL,
            start_date TEXT NOT NULL,
            benchmark_start_date TEXT,
            benchmark_start_price REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
        );

        CREATE TABLE IF NOT EXISTS paper_portfolio_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            paper_signal_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            shares REAL NOT NULL,
            capital_allocated REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            planned_exit_date TEXT,
            actual_exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            pnl REAL,
            return_pct REAL,
            last_price REAL,
            price_stale INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(portfolio_id, paper_signal_id),
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(id),
            FOREIGN KEY(paper_signal_id) REFERENCES paper_signals(id)
        );

        CREATE TABLE IF NOT EXISTS paper_portfolio_equity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            market_date TEXT NOT NULL,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            equity REAL NOT NULL,
            return_pct REAL NOT NULL,
            drawdown_pct REAL NOT NULL,
            exposure_pct REAL NOT NULL,
            spy_value REAL,
            spy_return_pct REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(portfolio_id, market_date),
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(id)
        );

        CREATE INDEX IF NOT EXISTS idx_live_positions_portfolio_status
        ON paper_portfolio_positions(portfolio_id, status);

        CREATE INDEX IF NOT EXISTS idx_live_equity_portfolio_date
        ON paper_portfolio_equity(portfolio_id, market_date);

        CREATE TABLE IF NOT EXISTS paper_portfolio_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            category TEXT,
            shares REAL NOT NULL,
            cost_basis REAL NOT NULL,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            last_price REAL,
            price_stale INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(portfolio_id, symbol),
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(id)
        );

        CREATE TABLE IF NOT EXISTS paper_portfolio_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            rebalance_id INTEGER,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            price REAL NOT NULL,
            shares REAL NOT NULL,
            gross_value REAL NOT NULL,
            fee REAL NOT NULL,
            realized_pnl REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(id)
        );

        CREATE TABLE IF NOT EXISTS paper_portfolio_rebalances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            signal_date TEXT NOT NULL,
            execution_date TEXT NOT NULL,
            ranking_json TEXT,
            selected_json TEXT,
            target_weights_json TEXT,
            cash_filter INTEGER NOT NULL DEFAULT 0,
            cash_reason TEXT,
            equity_before REAL NOT NULL,
            equity_after REAL NOT NULL,
            costs REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(portfolio_id, signal_date),
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(id)
        );

        CREATE INDEX IF NOT EXISTS idx_forward_holdings_portfolio
        ON paper_portfolio_holdings(portfolio_id);

        CREATE INDEX IF NOT EXISTS idx_forward_trades_portfolio_date
        ON paper_portfolio_trades(portfolio_id, trade_date);
        """
    )

    columnas_portfolio = {
        fila["name"]
        for fila in cursor.execute("PRAGMA table_info(paper_portfolios)").fetchall()
    }
    for nombre, definicion in (
        ("portfolio_type", "TEXT NOT NULL DEFAULT 'SIGNAL'"),
        ("activation_date", "TEXT"),
        ("version_identifier", "TEXT"),
        ("total_costs", "REAL NOT NULL DEFAULT 0.0"),
        ("last_rebalance_date", "TEXT"),
    ):
        if nombre not in columnas_portfolio:
            cursor.execute(
                f"ALTER TABLE paper_portfolios ADD COLUMN {nombre} {definicion}"
            )

    ahora = datetime.now().isoformat(timespec="seconds")
    for nombre, strategy, version in (
        ("MOMENTUM_LIVE", "MOMENTUM", "v4"),
        ("REVERSAL_LIVE", "REVERSAL", "v4"),
    ):
        cursor.execute(
            """
            INSERT OR IGNORE INTO paper_portfolios (
                name, strategy, source_score_version,
                initial_capital, current_cash, start_date,
                created_at, updated_at, status
            ) VALUES (?, ?, ?, 10000.0, 10000.0, ?, ?, ?, 'ACTIVE')
            """,
            (
                nombre,
                strategy,
                version,
                PAPER_PORTFOLIO_START_DATE,
                ahora,
                ahora
            )
        )

    for nombre, strategy, version in (
        ("ETF_TOP2_CANDIDATE", "ETF_TOP2_CANDIDATE", "candidate_frozen_v1"),
        ("DEFENSIVE_CANDIDATE", "DEFENSIVE_CANDIDATE", "DEFENSIVE_SIMPLE_CANDIDATE_V1"),
        ("SPY_BUY_HOLD", "BENCHMARK_SPY", "buy_hold_v1"),
        ("BALANCED_60_40", "BENCHMARK_60_40", "spy_ief_60_40_v1"),
        ("SHY_BUY_HOLD", "BENCHMARK_SHY", "shy_buy_hold_v1"),
    ):
        cursor.execute(
            """
            INSERT OR IGNORE INTO paper_portfolios (
                name, strategy, source_score_version,
                initial_capital, current_cash, start_date,
                created_at, updated_at, status, portfolio_type,
                activation_date, version_identifier, total_costs
            ) VALUES (?, ?, ?, 10000.0, 10000.0, ?, ?, ?, 'ACTIVE',
                      'FORWARD_ETF', ?, ?, 0.0)
            """,
            (
                nombre, strategy, version, ETF_FORWARD_START_DATE,
                ahora, ahora, ETF_FORWARD_START_DATE, version
            )
        )

    conexion.commit()
    conexion.close()


def obtener_resumen_paper_portfolios():
    """Devuelve carteras live con su ultimo equity y sus posiciones."""

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    carteras = cursor.execute(
        "SELECT * FROM paper_portfolios ORDER BY id"
    ).fetchall()
    resultado = []

    for cartera in carteras:
        item = dict(cartera)
        equity = cursor.execute(
            """
            SELECT * FROM paper_portfolio_equity
            WHERE portfolio_id = ?
            ORDER BY market_date DESC LIMIT 1
            """,
            (cartera["id"],)
        ).fetchone()
        if item.get("portfolio_type") == "FORWARD_ETF":
            abiertas = cursor.execute(
                """
                SELECT id, portfolio_id, symbol, entry_date, entry_price,
                       shares, cost_basis AS capital_allocated,
                       'OPEN' AS status, last_price, price_stale, category,
                       created_at, updated_at
                FROM paper_portfolio_holdings
                WHERE portfolio_id = ?
                ORDER BY cost_basis DESC, symbol
                """,
                (cartera["id"],)
            ).fetchall()
            cierres = cursor.execute(
                """
                SELECT id, symbol, trade_date AS actual_exit_date,
                       'REBALANCE' AS exit_reason, realized_pnl AS pnl,
                       NULL AS return_pct
                FROM paper_portfolio_trades
                WHERE portfolio_id = ? AND side = 'SELL'
                ORDER BY trade_date DESC, id DESC LIMIT 5
                """,
                (cartera["id"],)
            ).fetchall()
        else:
            abiertas = cursor.execute(
                """
                SELECT * FROM paper_portfolio_positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                ORDER BY capital_allocated DESC, symbol
                """,
                (cartera["id"],)
            ).fetchall()
            cierres = cursor.execute(
                """
                SELECT * FROM paper_portfolio_positions
                WHERE portfolio_id = ? AND status = 'CLOSED'
                ORDER BY actual_exit_date DESC, id DESC LIMIT 5
                """,
                (cartera["id"],)
            ).fetchall()
        item["equity"] = dict(equity) if equity else None
        item["max_drawdown_pct"] = cursor.execute(
            """
            SELECT MIN(drawdown_pct) FROM paper_portfolio_equity
            WHERE portfolio_id = ?
            """,
            (cartera["id"],)
        ).fetchone()[0]
        item["abiertas"] = [dict(fila) for fila in abiertas]
        item["ultimos_cierres"] = [dict(fila) for fila in cierres]
        tabla_resultados = (
            "paper_portfolio_trades" if item.get("portfolio_type") == "FORWARD_ETF"
            else "paper_portfolio_positions"
        )
        condicion = "side = 'SELL'" if tabla_resultados == "paper_portfolio_trades" else "status = 'CLOSED'"
        campo_pnl = "realized_pnl" if tabla_resultados == "paper_portfolio_trades" else "pnl"
        item["cerradas"] = cursor.execute(
            f"SELECT COUNT(*) FROM {tabla_resultados} WHERE portfolio_id = ? AND {condicion}",
            (cartera["id"],)
        ).fetchone()[0]
        item["pnl_realizado"] = cursor.execute(
            f"SELECT COALESCE(SUM({campo_pnl}), 0.0) FROM {tabla_resultados} "
            f"WHERE portfolio_id = ? AND {condicion}",
            (cartera["id"],)
        ).fetchone()[0]
        rebalanceo = cursor.execute(
            """
            SELECT * FROM paper_portfolio_rebalances
            WHERE portfolio_id = ? ORDER BY execution_date DESC, id DESC LIMIT 1
            """,
            (cartera["id"],)
        ).fetchone()
        item["ultimo_rebalanceo"] = dict(rebalanceo) if rebalanceo else None
        comunes = cursor.execute(
            """
            SELECT market_date, equity FROM paper_portfolio_equity
            WHERE portfolio_id = ? AND market_date >= ?
            ORDER BY market_date
            """,
            (cartera["id"], ETF_FORWARD_START_DATE)
        ).fetchall()
        item["common_start_date"] = None
        item["common_return_pct"] = None
        item["common_max_drawdown_pct"] = None
        if comunes and comunes[0]["market_date"] == ETF_FORWARD_START_DATE:
            inicial = float(comunes[0]["equity"])
            pico = inicial
            peor_dd = 0.0
            for punto in comunes:
                valor = float(punto["equity"])
                pico = max(pico, valor)
                peor_dd = min(peor_dd, (valor / pico - 1) * 100 if pico else 0.0)
            item["common_start_date"] = ETF_FORWARD_START_DATE
            item["common_return_pct"] = (
                (float(comunes[-1]["equity"]) / inicial - 1) * 100
                if inicial else None
            )
            item["common_max_drawdown_pct"] = peor_dd
        resultado.append(item)

    conexion.close()
    return resultado


def guardar_analyst_snapshot(
    snapshot
):
    """
    Guarda como maximo un snapshot diario por symbol y fuente.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    ahora = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO analyst_consensus_snapshots (

            snapshot_time,
            snapshot_date,
            symbol,

            price_internal,
            price_yahoo,

            target_low,
            target_high,
            target_mean,
            target_median,

            upside_mean_pct,
            upside_median_pct,

            strong_buy,
            buy,
            hold,
            sell,
            strong_sell,
            analyst_count,
            consensus_score,

            recommendation_period,

            eps_0q,
            eps_next_q,
            eps_0y,
            eps_next_y,
            eps_growth_0y,
            eps_growth_next_y,
            eps_analysts_0y,
            eps_analysts_next_y,

            source,
            created_at
        )
        VALUES (
            ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        """,
        (
            snapshot["snapshot_time"],
            snapshot["snapshot_date"],
            str(snapshot["symbol"]).strip().upper(),

            snapshot.get("price_internal"),
            snapshot.get("price_yahoo"),

            snapshot.get("target_low"),
            snapshot.get("target_high"),
            snapshot.get("target_mean"),
            snapshot.get("target_median"),

            snapshot.get("upside_mean_pct"),
            snapshot.get("upside_median_pct"),

            snapshot.get("strong_buy"),
            snapshot.get("buy"),
            snapshot.get("hold"),
            snapshot.get("sell"),
            snapshot.get("strong_sell"),
            snapshot.get("analyst_count"),
            snapshot.get("consensus_score"),

            snapshot.get("recommendation_period"),

            snapshot.get("eps_0q"),
            snapshot.get("eps_next_q"),
            snapshot.get("eps_0y"),
            snapshot.get("eps_next_y"),
            snapshot.get("eps_growth_0y"),
            snapshot.get("eps_growth_next_y"),
            snapshot.get("eps_analysts_0y"),
            snapshot.get("eps_analysts_next_y"),

            snapshot.get("source", "YAHOO"),
            snapshot.get("created_at", ahora)
        )
    )

    insertados = cursor.rowcount

    conexion.commit()
    conexion.close()

    return insertados


def obtener_ultimo_analyst_snapshot(
    symbol
):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM analyst_consensus_snapshots

        WHERE symbol = ?

        ORDER BY
            snapshot_date DESC,
            snapshot_time DESC,
            id DESC

        LIMIT 1
        """,
        (
            symbol.strip().upper(),
        )
    )

    fila = cursor.fetchone()
    conexion.close()

    if fila is None:
        return None

    return dict(fila)


def obtener_analyst_snapshots_recientes(
    limite=100,
    symbol=None
):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    if symbol:
        cursor.execute(
            """
            SELECT *

            FROM analyst_consensus_snapshots

            WHERE symbol = ?

            ORDER BY
                snapshot_date DESC,
                snapshot_time DESC,
                id DESC

            LIMIT ?
            """,
            (
                symbol.strip().upper(),
                limite
            )
        )

    else:
        cursor.execute(
            """
            SELECT *

            FROM analyst_consensus_snapshots

            ORDER BY
                snapshot_date DESC,
                snapshot_time DESC,
                id DESC

            LIMIT ?
            """,
            (
                limite,
            )
        )

    filas = cursor.fetchall()
    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


def obtener_ultimos_analyst_snapshots():
    """
    Devuelve exclusivamente el snapshot mas reciente
    disponible para cada combinacion symbol/source.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT acs.*

        FROM analyst_consensus_snapshots acs

        WHERE acs.id = (

            SELECT reciente.id

            FROM analyst_consensus_snapshots reciente

            WHERE
                reciente.symbol = acs.symbol
                AND reciente.source = acs.source

            ORDER BY
                reciente.snapshot_date DESC,
                reciente.snapshot_time DESC,
                reciente.id DESC

            LIMIT 1
        )

        ORDER BY acs.symbol ASC
        """
    )

    filas = cursor.fetchall()
    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


def obtener_analyst_snapshots_symbols(
    symbols,
    source="YAHOO"
):
    """Devuelve el historico de varios simbolos en una sola lectura."""

    symbols_normalizados = sorted({
        str(symbol).strip().upper()
        for symbol in symbols
        if symbol
    })

    if not symbols_normalizados:
        return []

    placeholders = ",".join(
        "?"
        for _ in symbols_normalizados
    )
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        f"""
        SELECT *
        FROM analyst_consensus_snapshots
        WHERE symbol IN ({placeholders})
          AND source = ?
        ORDER BY
            symbol ASC,
            snapshot_date DESC,
            snapshot_time DESC,
            id DESC
        """,
        (
            *symbols_normalizados,
            str(source).strip().upper()
        )
    )
    filas = cursor.fetchall()
    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# NEWS CONTEXT
# ============================================================

def inicializar_tablas_news():
    """
    Tablas para persistir el contexto de noticias
    asociado a cada senal tecnica.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    # ========================================================
    # CONTEXTO GENERAL DEL ACTIVO
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_context (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_date TEXT NOT NULL,
            scan_time TEXT,

            symbol TEXT NOT NULL,

            score INTEGER,
            score_version TEXT,

            prioridad_tecnica TEXT,
            perfil_tecnico TEXT,

            sector TEXT,

            num_noticias INTEGER,

            contexto TEXT,

            movimiento_explicado TEXT,

            fuerza_catalizador TEXT,

            riesgo_narrativo TEXT,

            catalizadores TEXT,

            evidencias_positivas TEXT,

            evidencias_negativas TEXT,

            riesgos TEXT,

            lectura TEXT,

            analyzed_at TEXT NOT NULL,

            UNIQUE(
                market_date,
                symbol,
                score_version
            )
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_news_context_symbol

        ON news_context(
            symbol
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_news_context_date

        ON news_context(
            market_date
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_news_context_priority

        ON news_context(
            prioridad_tecnica
        )
        """
    )


    # ========================================================
    # NOTICIAS INDIVIDUALES
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            context_id INTEGER NOT NULL,

            symbol TEXT NOT NULL,

            headline TEXT,

            summary TEXT,

            source TEXT,

            published_at TEXT,

            url TEXT,

            contexto TEXT,

            catalizadores TEXT,

            evidencias_positivas TEXT,

            evidencias_negativas TEXT,

            riesgos TEXT,

            FOREIGN KEY(
                context_id
            )
            REFERENCES news_context(id)
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_news_items_context

        ON news_items(
            context_id
        )
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_news_items_symbol

        ON news_items(
            symbol
        )
        """
    )


    conexion.commit()
    conexion.close()


# ============================================================
# CANDIDATOS NEWS PENDIENTES
# ============================================================

def obtener_candidatos_news_pendientes(
    score_version="v3",
    prioridades=(
        "A+",
        "A"
    )
):
    """
    Devuelve scans A+/A que todavia no tienen
    contexto de noticias guardado.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    placeholders = ",".join(
        "?"
        for _ in prioridades
    )


    cursor.execute(
        f"""
        SELECT

            s.market_date,
            s.scan_time,

            s.symbol,

            s.score,
            s.score_version,

            s.prioridad_estudio,
            s.perfil,

            s.sector

        FROM scans s

        LEFT JOIN news_context nc

        ON
            nc.market_date = s.market_date
            AND nc.symbol = s.symbol
            AND nc.score_version = s.score_version

        WHERE
            s.score_version = ?

            AND s.prioridad_estudio IN (
                {placeholders}
            )

            AND s.market_date IS NOT NULL

            AND nc.id IS NULL

        ORDER BY
            s.market_date ASC,
            s.score DESC
        """,
        (
            score_version,
            *prioridades
        )
    )


    filas = cursor.fetchall()

    conexion.close()


    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# GUARDAR NEWS CONTEXT
# ============================================================

def guardar_news_context(
    candidato,
    resultado
):
    """
    Guarda:
    - resumen de contexto
    - noticias individuales
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    def lista_a_texto(
        valores
    ):

        if not valores:
            return ""

        return "|".join(
            str(valor)
            for valor in valores
            if valor
        )


    ahora = datetime.now().isoformat(
        timespec="seconds"
    )


    # ========================================================
    # INSERT CONTEXTO
    # ========================================================

    cursor.execute(
        """
        INSERT OR IGNORE INTO news_context (

            market_date,
            scan_time,

            symbol,

            score,
            score_version,

            prioridad_tecnica,
            perfil_tecnico,

            sector,

            num_noticias,

            contexto,

            movimiento_explicado,

            fuerza_catalizador,

            riesgo_narrativo,

            catalizadores,

            evidencias_positivas,

            evidencias_negativas,

            riesgos,

            lectura,

            analyzed_at

        )
        VALUES (
            ?, ?,
            ?,
            ?, ?,
            ?, ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            candidato[
                "market_date"
            ],

            candidato[
                "scan_time"
            ],

            candidato[
                "symbol"
            ],

            candidato[
                "score"
            ],

            candidato[
                "score_version"
            ],

            candidato[
                "prioridad_estudio"
            ],

            candidato[
                "perfil"
            ],

            candidato[
                "sector"
            ],

            resultado[
                "num_noticias"
            ],

            resultado[
                "contexto"
            ],

            resultado[
                "movimiento_explicado"
            ],

            resultado[
                "fuerza_catalizador"
            ],

            resultado[
                "riesgo_narrativo"
            ],

            lista_a_texto(
                resultado[
                    "catalizadores"
                ]
            ),

            lista_a_texto(
                resultado[
                    "evidencias_positivas"
                ]
            ),

            lista_a_texto(
                resultado[
                    "evidencias_negativas"
                ]
            ),

            lista_a_texto(
                resultado[
                    "riesgos"
                ]
            ),

            resultado[
                "lectura"
            ],

            ahora
        )
    )


    # ========================================================
    # RECUPERAR ID
    # ========================================================

    cursor.execute(
        """
        SELECT id

        FROM news_context

        WHERE
            market_date = ?
            AND symbol = ?
            AND score_version = ?
        """,
        (
            candidato[
                "market_date"
            ],

            candidato[
                "symbol"
            ],

            candidato[
                "score_version"
            ]
        )
    )


    fila = cursor.fetchone()


    if fila is None:

        conexion.close()

        return 0


    context_id = fila[
        "id"
    ]


    # ========================================================
    # EVITAR DUPLICAR ITEMS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM news_items

        WHERE context_id = ?
        """,
        (
            context_id,
        )
    )


    ya_existen = (
        cursor.fetchone()[0]
        > 0
    )


    if not ya_existen:

        for noticia in resultado[
            "noticias"
        ]:

            cursor.execute(
                """
                INSERT INTO news_items (

                    context_id,

                    symbol,

                    headline,

                    summary,

                    source,

                    published_at,

                    url,

                    contexto,

                    catalizadores,

                    evidencias_positivas,

                    evidencias_negativas,

                    riesgos

                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    context_id,

                    candidato[
                        "symbol"
                    ],

                    noticia.get(
                        "headline"
                    ),

                    noticia.get(
                        "summary"
                    ),

                    noticia.get(
                        "source"
                    ),

                    noticia.get(
                        "created_at"
                    ),

                    noticia.get(
                        "url"
                    ),

                    noticia.get(
                        "contexto"
                    ),

                    lista_a_texto(
                        noticia.get(
                            "catalizadores",
                            []
                        )
                    ),

                    lista_a_texto(
                        noticia.get(
                            "evidencias_positivas",
                            []
                        )
                    ),

                    lista_a_texto(
                        noticia.get(
                            "evidencias_negativas",
                            []
                        )
                    ),

                    lista_a_texto(
                        noticia.get(
                            "riesgos",
                            []
                        )
                    )
                )
            )


    conexion.commit()
    conexion.close()

    return 1


# ============================================================
# NEWS CONTEXT ULTIMO SCAN
# ============================================================

def obtener_news_context_ultimo_scan():
    """
    Devuelve el contexto de noticias
    de la ultima sesion disponible.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    cursor.execute(
        """
        SELECT MAX(
            market_date
        )

        FROM news_context
        """
    )


    fila = cursor.fetchone()


    if (
        fila is None
        or fila[0] is None
    ):

        conexion.close()

        return []


    market_date = fila[0]


    cursor.execute(
        """
        SELECT *

        FROM news_context

        WHERE market_date = ?

        ORDER BY
            CASE prioridad_tecnica
                WHEN 'A+' THEN 1
                WHEN 'A' THEN 2
                ELSE 99
            END,
            score DESC
        """,
        (
            market_date,
        )
    )


    filas = cursor.fetchall()

    conexion.close()


    return [
        dict(fila)
        for fila in filas
    ]


# ============================================================
# NEWS ITEMS POR CONTEXTO
# ============================================================

def obtener_news_items(
    context_id
):
    """
    Devuelve las noticias de un contexto.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()


    cursor.execute(
        """
        SELECT *

        FROM news_items

        WHERE context_id = ?

        ORDER BY
            published_at DESC
        """,
        (
            context_id,
        )
    )


    filas = cursor.fetchall()

    conexion.close()


    return [
        dict(fila)
        for fila in filas
    ]
# ============================================================
# FUNDAMENTAL ANALYSIS
# ============================================================

def inicializar_tabla_fundamentales():
    """
    Crea la tabla que almacena snapshots del
    analisis fundamental de cada empresa.

    Cada fila representa el estado fundamental
    de un simbolo en una fecha determinada.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fundamental_analysis (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            symbol TEXT NOT NULL,
            analysis_date TEXT NOT NULL,

            company_name TEXT,
            cik TEXT,
            sic TEXT,
            sic_description TEXT,
            sector TEXT,
            model TEXT,

            fy_date TEXT,
            reference_date TEXT,
            fy_age_days INTEGER,

            revenue_fy REAL,
            revenue_yoy REAL,

            net_income_fy REAL,
            net_income_yoy REAL,

            revenue_ttm REAL,
            revenue_ttm_method TEXT,

            net_income_ttm REAL,
            net_income_ttm_method TEXT,

            operating_margin REAL,
            net_margin REAL,

            cfo_ttm REAL,
            capex_ttm REAL,
            fcf_ttm REAL,

            cash REAL,
            debt REAL,
            equity REAL,
            debt_to_equity REAL,

            price REAL,
            shares REAL,
            shares_method TEXT,
            market_cap REAL,

            pe_ttm REAL,
            ps_ttm REAL,
            pb REAL,
            fcf_yield REAL,

            roe REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(symbol, analysis_date)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_fundamental_symbol
        ON fundamental_analysis(symbol)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_fundamental_analysis_date
        ON fundamental_analysis(analysis_date)
        """
    )

    conn.commit()
    conn.close()


def guardar_analisis_fundamental(datos):
    """
    Guarda o actualiza el snapshot fundamental
    de una empresa.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    campos = [
        "symbol",
        "analysis_date",

        "company_name",
        "cik",
        "sic",
        "sic_description",
        "sector",
        "model",

        "fy_date",
        "reference_date",
        "fy_age_days",

        "revenue_fy",
        "revenue_yoy",

        "net_income_fy",
        "net_income_yoy",

        "revenue_ttm",
        "revenue_ttm_method",

        "net_income_ttm",
        "net_income_ttm_method",

        "operating_margin",
        "net_margin",

        "cfo_ttm",
        "capex_ttm",
        "fcf_ttm",

        "cash",
        "debt",
        "equity",
        "debt_to_equity",

        "price",
        "shares",
        "shares_method",
        "market_cap",

        "pe_ttm",
        "ps_ttm",
        "pb",
        "fcf_yield",

        "roe"
    ]

    valores = [
        datos.get(campo)
        for campo in campos
    ]

    placeholders = ", ".join(
        ["?"] * len(campos)
    )

    columnas = ", ".join(campos)

    updates = ", ".join(
        [
            f"{campo}=excluded.{campo}"
            for campo in campos
            if campo not in (
                "symbol",
                "analysis_date"
            )
        ]
    )

    sql = f"""
        INSERT INTO fundamental_analysis (
            {columnas}
        )
        VALUES (
            {placeholders}
        )

        ON CONFLICT(symbol, analysis_date)
        DO UPDATE SET
            {updates}
    """

    cursor.execute(
        sql,
        valores
    )

    conn.commit()
    conn.close()


def obtener_ultimo_fundamental(symbol):
    """
    Devuelve el analisis fundamental mas reciente
    disponible para un simbolo.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM fundamental_analysis
        WHERE symbol = ?
        ORDER BY analysis_date DESC
        LIMIT 1
        """,
        (
            symbol.upper(),
        )
    )

    fila = cursor.fetchone()

    conn.close()

    if fila is None:
        return None

    return dict(fila)


def obtener_fundamentales_recientes(
    limite=100
):
    """
    Devuelve los ultimos snapshots fundamentales
    almacenados.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM fundamental_analysis
        ORDER BY analysis_date DESC, id DESC
        LIMIT ?
        """,
        (
            limite,
        )
    )

    filas = cursor.fetchall()

    conn.close()

    return [
        dict(fila)
        for fila in filas
    ]
# ============================================================
# FUNDAMENTAL CLASSIFICATION
# ============================================================

def inicializar_tabla_fundamental_classification():
    """
    Guarda la interpretacion humana del snapshot fundamental.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fundamental_classification (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fundamental_id INTEGER NOT NULL,

            symbol TEXT NOT NULL,

            analysis_date TEXT NOT NULL,

            model TEXT,

            score_fundamental INTEGER,

            calidad_fundamental TEXT,

            crecimiento TEXT,

            rentabilidad TEXT,

            balance TEXT,

            cash_flow TEXT,

            valoracion TEXT,

            fortalezas TEXT,

            debilidades TEXT,

            alertas TEXT,

            lectura TEXT,

            created_at TEXT NOT NULL,

            UNIQUE(
                fundamental_id
            ),

            FOREIGN KEY(
                fundamental_id
            )
            REFERENCES fundamental_analysis(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_fund_class_symbol

        ON fundamental_classification(
            symbol
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_fund_class_date

        ON fundamental_classification(
            analysis_date
        )
        """
    )

    conexion.commit()
    conexion.close()


def guardar_clasificacion_fundamental(
    fundamental_id,
    fundamental,
    clasificacion
):
    """
    Guarda la clasificacion humana correspondiente
    a un snapshot fundamental.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    def lista_a_texto(
        valores
    ):

        if not valores:
            return ""

        return "|".join(
            str(valor)
            for valor in valores
            if valor
        )

    ahora = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO fundamental_classification (

            fundamental_id,

            symbol,

            analysis_date,

            model,

            score_fundamental,

            calidad_fundamental,

            crecimiento,

            rentabilidad,

            balance,

            cash_flow,

            valoracion,

            fortalezas,

            debilidades,

            alertas,

            lectura,

            created_at
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )

        ON CONFLICT(
            fundamental_id
        )

        DO UPDATE SET

            score_fundamental =
                excluded.score_fundamental,

            calidad_fundamental =
                excluded.calidad_fundamental,

            crecimiento =
                excluded.crecimiento,

            rentabilidad =
                excluded.rentabilidad,

            balance =
                excluded.balance,

            cash_flow =
                excluded.cash_flow,

            valoracion =
                excluded.valoracion,

            fortalezas =
                excluded.fortalezas,

            debilidades =
                excluded.debilidades,

            alertas =
                excluded.alertas,

            lectura =
                excluded.lectura,

            created_at =
                excluded.created_at
        """,
        (
            fundamental_id,

            fundamental.get(
                "symbol"
            ),

            fundamental.get(
                "analysis_date"
            ),

            fundamental.get(
                "model"
            ),

            clasificacion.get(
                "score_fundamental"
            ),

            clasificacion.get(
                "calidad_fundamental"
            ),

            clasificacion.get(
                "crecimiento"
            ),

            clasificacion.get(
                "rentabilidad"
            ),

            clasificacion.get(
                "balance"
            ),

            clasificacion.get(
                "cash_flow"
            ),

            clasificacion.get(
                "valoracion"
            ),

            lista_a_texto(
                clasificacion.get(
                    "fortalezas"
                )
            ),

            lista_a_texto(
                clasificacion.get(
                    "debilidades"
                )
            ),

            lista_a_texto(
                clasificacion.get(
                    "alertas"
                )
            ),

            clasificacion.get(
                "lectura"
            ),

            ahora
        )
    )

    conexion.commit()
    conexion.close()


def obtener_fundamentales_sin_clasificar():
    """
    Devuelve snapshots fundamentales que todavia
    no tienen clasificacion asociada.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT
            fa.*

        FROM fundamental_analysis fa

        LEFT JOIN fundamental_classification fc

        ON fc.fundamental_id = fa.id

        WHERE fc.id IS NULL

        ORDER BY
            fa.analysis_date ASC,
            fa.symbol ASC
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]


def obtener_ultima_clasificacion_fundamental(
    symbol
):
    """
    Devuelve la ultima clasificacion fundamental
    disponible para un simbolo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT

            fc.*,

            fa.price,
            fa.market_cap,
            fa.pe_ttm,
            fa.ps_ttm,
            fa.pb,
            fa.fcf_yield,
            fa.roe,

            fa.revenue_ttm,
            fa.net_income_ttm,
            fa.fcf_ttm

        FROM fundamental_classification fc

        INNER JOIN fundamental_analysis fa

        ON fa.id = fc.fundamental_id

        WHERE fc.symbol = ?

        ORDER BY
            fc.analysis_date DESC,
            fc.id DESC

        LIMIT 1
        """,
        (
            symbol.upper(),
        )
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(
        fila
    )
# ============================================================
# ULTIMAS CLASIFICACIONES FUNDAMENTALES
# ============================================================

def obtener_ultimas_clasificaciones_fundamentales():
    """
    Devuelve la clasificacion fundamental mas reciente
    disponible para cada simbolo.

    Incluye tambien los principales ratios del snapshot
    fundamental correspondiente.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT

            fc.*,

            fa.company_name,
            fa.sic,
            fa.sic_description,
            fa.sector,

            fa.fy_date,
            fa.reference_date,

            fa.revenue_yoy,
            fa.net_income_yoy,

            fa.revenue_ttm,
            fa.net_income_ttm,

            fa.operating_margin,
            fa.net_margin,

            fa.cfo_ttm,
            fa.fcf_ttm,

            fa.cash,
            fa.debt,
            fa.equity,
            fa.debt_to_equity,

            fa.price,
            fa.market_cap,

            fa.pe_ttm,
            fa.ps_ttm,
            fa.pb,
            fa.fcf_yield,

            fa.roe

        FROM fundamental_classification fc

        INNER JOIN fundamental_analysis fa

        ON fa.id = fc.fundamental_id

        INNER JOIN (

            SELECT
                symbol,
                MAX(analysis_date) AS max_date

            FROM fundamental_classification

            GROUP BY symbol

        ) ultimos

        ON
            ultimos.symbol = fc.symbol
            AND ultimos.max_date = fc.analysis_date

        ORDER BY
            fc.score_fundamental DESC,
            fc.symbol ASC
        """
    )

    filas = cursor.fetchall()

    conexion.close()

    return [
        dict(fila)
        for fila in filas
    ]

def obtener_ultimo_tecnico(
    symbol
):
    """
    Devuelve el registro tecnico mas reciente
    disponible para un simbolo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE symbol = ?

        ORDER BY scan_time DESC

        LIMIT 1
        """,
        (
            symbol.upper(),
        )
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(fila)
# ============================================================
# ULTIMO CONTEXTO DE NOTICIAS POR SIMBOLO
# ============================================================

def obtener_ultimo_news_context(
    symbol
):
    """
    Devuelve el contexto de noticias mas reciente
    disponible para un simbolo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM news_context

        WHERE symbol = ?

        ORDER BY
            market_date DESC,
            analyzed_at DESC

        LIMIT 1
        """,
        (
            symbol.upper(),
        )
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(fila)


# ============================================================
# ULTIMO TECNICO POR SIMBOLO
# ============================================================

def obtener_ultimo_tecnico(
    symbol
):
    """
    Devuelve el registro tecnico mas reciente
    disponible para un simbolo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT *

        FROM scans

        WHERE symbol = ?

        ORDER BY scan_time DESC

        LIMIT 1
        """,
        (
            symbol.upper(),
        )
    )

    fila = cursor.fetchone()

    conexion.close()

    if fila is None:
        return None

    return dict(fila)
