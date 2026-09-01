# ============================================================
# CONFIGURACIÓN DE EVENTOS
# ============================================================

SCORE_ZONA_FUERTE = 85
SCORE_WATCHLIST = 70

SUBIDA_SCORE_RELEVANTE = 8
CAIDA_SCORE_RELEVANTE = 8

MEJORA_RS20_RELEVANTE = 5
MEJORA_RS60_RELEVANTE = 8


# ============================================================
# HELPERS
# ============================================================

def crear_mapa_scan(scan):
    """
    Convierte una lista de registros de un scan en:

    {
        "AAPL": {...},
        "MSFT": {...}
    }
    """

    return {
        activo["symbol"]: activo
        for activo in scan
        if activo.get("symbol")
    }


def obtener_version_scan(scan):
    """
    Obtiene la versión de score utilizada por un scan.

    Si el scan antiguo no tiene score_version,
    devuelve None.
    """

    versiones = {
        activo.get("score_version")
        for activo in scan
        if activo.get("score_version")
    }

    if not versiones:
        return None

    if len(versiones) == 1:
        return next(iter(versiones))

    # No debería ocurrir, pero si una sesión tiene
    # varias versiones no queremos compararla.
    return "MIXED"


def numero(valor, defecto=0):
    """
    Convierte valores None a un número seguro.
    """

    if valor is None:
        return defecto

    return valor


# ============================================================
# DETECTAR EVENTOS
# ============================================================

def detectar_eventos(
    scan_actual,
    scan_anterior
):
    """
    Compara dos sesiones consecutivas.

    Reglas importantes:

    1. No compara scores de versiones distintas.
    2. Genera como máximo UN evento por ticker.
    3. Consolida score + fuerza relativa en un mensaje.
    4. Solo registra cambios suficientemente relevantes.
    """

    if not scan_actual or not scan_anterior:
        return []


    # ========================================================
    # CONTROL DE VERSIONES
    # ========================================================

    version_actual = obtener_version_scan(
        scan_actual
    )

    version_anterior = obtener_version_scan(
        scan_anterior
    )


    if (
        version_actual != version_anterior
        or version_actual is None
        or version_anterior is None
        or version_actual == "MIXED"
        or version_anterior == "MIXED"
    ):

        print(
            "\nEventos omitidos: "
            f"score {version_anterior or 'sin versión'} "
            f"-> {version_actual or 'sin versión'}."
        )

        print(
            "No se comparan sesiones calculadas "
            "con algoritmos distintos."
        )

        return []


    # ========================================================
    # MAPAS
    # ========================================================

    actual = crear_mapa_scan(
        scan_actual
    )

    anterior = crear_mapa_scan(
        scan_anterior
    )


    eventos = []


    # ========================================================
    # COMPARAR TICKERS PRESENTES EN AMBOS SCANS
    # ========================================================

    for symbol, activo_actual in actual.items():

        activo_anterior = anterior.get(
            symbol
        )

        if activo_anterior is None:
            continue


        score_actual = numero(
            activo_actual.get("score")
        )

        score_anterior = numero(
            activo_anterior.get("score")
        )

        diferencia_score = (
            score_actual
            - score_anterior
        )


        rs20_actual = numero(
            activo_actual.get("fuerza_20d")
        )

        rs20_anterior = numero(
            activo_anterior.get("fuerza_20d")
        )

        rs60_actual = numero(
            activo_actual.get("fuerza_60d")
        )

        rs60_anterior = numero(
            activo_anterior.get("fuerza_60d")
        )


        cambio_rs20 = (
            rs20_actual
            - rs20_anterior
        )

        cambio_rs60 = (
            rs60_actual
            - rs60_anterior
        )


        # ====================================================
        # FLAGS
        # ====================================================

        entra_zona_fuerte = (
            score_actual >= SCORE_ZONA_FUERTE
            and score_anterior < SCORE_ZONA_FUERTE
        )


        pierde_zona_watchlist = (
            score_actual < SCORE_WATCHLIST
            and score_anterior >= SCORE_WATCHLIST
        )


        acelerando = (
            diferencia_score
            >= SUBIDA_SCORE_RELEVANTE
        )


        deterioro_fuerte = (
            diferencia_score
            <= -CAIDA_SCORE_RELEVANTE
        )


        fuerza_creciente = (
            cambio_rs20
            >= MEJORA_RS20_RELEVANTE

            or cambio_rs60
            >= MEJORA_RS60_RELEVANTE
        )


        # ====================================================
        # SI NO HAY NADA RELEVANTE, IGNORAMOS
        # ====================================================

        if not (
            entra_zona_fuerte
            or pierde_zona_watchlist
            or acelerando
            or deterioro_fuerte
            or fuerza_creciente
        ):
            continue


        # ====================================================
        # CONSTRUIR MENSAJE ÚNICO
        # ====================================================

        partes = []


        if entra_zona_fuerte:

            partes.append(
                f"NUEVO FUERTE: entra en >= "
                f"{SCORE_ZONA_FUERTE}"
            )


        if pierde_zona_watchlist:

            partes.append(
                "SALE WATCHLIST"
            )


        if diferencia_score != 0:

            partes.append(
                f"score {score_anterior}"
                f"->{score_actual} "
                f"({diferencia_score:+d})"
            )


        if fuerza_creciente:

            partes.append(
                f"RS20 {rs20_actual:+.1f}pp "
                f"({cambio_rs20:+.1f})"
            )

            partes.append(
                f"RS60 {rs60_actual:+.1f}pp "
                f"({cambio_rs60:+.1f})"
            )


        sector = activo_actual.get(
            "sector"
        )

        fuerza_sector_20 = activo_actual.get(
            "fuerza_sector_20d"
        )

        fuerza_sector_60 = activo_actual.get(
            "fuerza_sector_60d"
        )


        if (
            sector
            and fuerza_sector_20 is not None
            and fuerza_sector_60 is not None
        ):

            partes.append(
                f"{sector}: "
                f"S20 {fuerza_sector_20:+.1f}pp, "
                f"S60 {fuerza_sector_60:+.1f}pp"
            )


        # ====================================================
        # TIPO PRINCIPAL
        # ====================================================

        if pierde_zona_watchlist or deterioro_fuerte:

            tipo = "DETERIORO"

        elif entra_zona_fuerte:

            tipo = "NUEVO_CANDIDATO"

        elif acelerando:

            tipo = "ACELERANDO"

        else:

            tipo = "FUERZA_CRECIENTE"


        mensaje = (
            f"{symbol} | "
            + " | ".join(partes)
        )


        eventos.append(
            {
                "symbol":
                    symbol,

                "tipo":
                    tipo,

                "mensaje":
                    mensaje,

                "score_actual":
                    score_actual,

                "score_anterior":
                    score_anterior
            }
        )


    # ========================================================
    # PRIORIZACIÓN
    # ========================================================

    prioridad = {
        "DETERIORO": 0,
        "NUEVO_CANDIDATO": 1,
        "ACELERANDO": 2,
        "FUERZA_CRECIENTE": 3
    }


    eventos = sorted(
        eventos,
        key=lambda evento: (
            prioridad.get(
                evento["tipo"],
                99
            ),
            -abs(
                numero(
                    evento.get(
                        "score_actual"
                    )
                )
            )
        )
    )


    return eventos