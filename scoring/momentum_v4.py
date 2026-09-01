# scoring_v4.py


SCORE_VERSION = "v4_exp"


# ============================================================
# HELPERS
# ============================================================

def _numero(
    valor,
    default=0.0
):

    try:

        if valor is None:
            return default

        return float(
            valor
        )

    except (
        TypeError,
        ValueError
    ):

        return default


def _texto(
    valor
):

    if valor is None:
        return ""

    return (
        str(
            valor
        )
        .strip()
        .upper()
    )


# ============================================================
# TENDENCIA
# MAXIMO 20
# ============================================================

def score_tendencia_v4(
    tendencia
):

    tendencia = _texto(
        tendencia
    )


    if tendencia == "FUERTE ALCISTA":

        return 20


    if tendencia == "ALCISTA":

        return 16


    if tendencia == "MIXTA":

        return 9


    if tendencia == "BAJISTA":

        return 3


    return 1


# ============================================================
# MOMENTUM / RSI
# MAXIMO 20
# ============================================================

def score_momentum_v4(
    rsi
):
    """
    V3 favorecia especialmente RSI 55-65.

    El historico muestra mejor continuidad
    principalmente entre 60-70.

    No convertimos un bucket concreto en una
    regla absoluta; hacemos una curva gradual.
    """

    rsi = _numero(
        rsi,
        None
    )


    if rsi is None:

        return 0


    if 65 <= rsi < 70:

        return 20


    if 60 <= rsi < 65:

        return 18


    if 70 <= rsi < 75:

        return 16


    if 55 <= rsi < 60:

        return 13


    if 50 <= rsi < 55:

        return 10


    if 75 <= rsi < 80:

        return 9


    if 45 <= rsi < 50:

        return 6


    if rsi >= 80:

        return 5


    return 3


# ============================================================
# FUERZA RELATIVA VS SPY
# MAXIMO 20
# ============================================================

def score_fuerza_v4(
    fuerza_20d,
    fuerza_60d
):

    f20 = _numero(
        fuerza_20d
    )

    f60 = _numero(
        fuerza_60d
    )


    # ========================================================
    # 20D - MAX 10
    # ========================================================

    if f20 >= 15:

        s20 = 10

    elif f20 >= 10:

        s20 = 9

    elif f20 >= 5:

        s20 = 7

    elif f20 >= 2:

        s20 = 5

    elif f20 >= 0:

        s20 = 3

    elif f20 >= -3:

        s20 = 1

    else:

        s20 = 0


    # ========================================================
    # 60D - MAX 10
    # ========================================================

    if f60 >= 30:

        s60 = 10

    elif f60 >= 20:

        s60 = 9

    elif f60 >= 10:

        s60 = 7

    elif f60 >= 5:

        s60 = 5

    elif f60 >= 0:

        s60 = 3

    elif f60 >= -5:

        s60 = 1

    else:

        s60 = 0


    return (
        s20
        +
        s60
    )


# ============================================================
# FUERZA SECTOR
# MAXIMO 10
# ============================================================

def score_sector_v4(
    fuerza_sector_20d,
    fuerza_sector_60d
):

    if (
        fuerza_sector_20d is None
        or
        fuerza_sector_60d is None
    ):

        # Neutral si no hay benchmark sectorial.
        return 5


    f20 = _numero(
        fuerza_sector_20d
    )

    f60 = _numero(
        fuerza_sector_60d
    )


    # ========================================================
    # 20D - MAX 5
    # ========================================================

    if f20 >= 10:

        s20 = 5

    elif f20 >= 5:

        s20 = 4

    elif f20 >= 0:

        s20 = 3

    elif f20 >= -5:

        s20 = 1

    else:

        s20 = 0


    # ========================================================
    # 60D - MAX 5
    # ========================================================

    if f60 >= 20:

        s60 = 5

    elif f60 >= 10:

        s60 = 4

    elif f60 >= 0:

        s60 = 3

    elif f60 >= -5:

        s60 = 1

    else:

        s60 = 0


    return (
        s20
        +
        s60
    )


# ============================================================
# CONTINUACION / DISTANCIA SMA20
# MAXIMO 20
# ============================================================

def score_continuacion_v4(
    distancia_sma20
):
    """
    Esta es la principal novedad de V4.

    El historico mostro:

        B + SMA20 10-15%
        262 casos
        17 sesiones
        +1.91pp trimmed
        95/100 temporal

    Pero evitamos convertir exactamente ese
    bucket en una regla binaria.

    Se utiliza una curva gradual de momentum.
    """

    distancia = _numero(
        distancia_sma20,
        None
    )


    if distancia is None:

        return 0


    # Liderazgo fuerte pero no extremo.

    if 10 <= distancia < 15:

        return 20


    # Muy buena continuacion.

    if 6 <= distancia < 10:

        return 17


    # Momentum sano.

    if 3 <= distancia < 6:

        return 13


    # Cerca de SMA20:
    # no es malo, pero el historico no
    # justifica premiarlo especialmente.

    if 0 <= distancia < 3:

        return 8


    # >15 sigue siendo momentum,
    # pero aumenta riesgo de extension.

    if 15 <= distancia < 20:

        return 12


    if 20 <= distancia < 30:

        return 8


    if distancia >= 30:

        return 4


    # Debajo de SMA20.

    if -3 <= distancia < 0:

        return 5


    if -6 <= distancia < -3:

        return 2


    return 0


# ============================================================
# VOLUMEN
# MAXIMO 10
# ============================================================

def score_volumen_v4(
    volumen_relativo
):

    volumen = _numero(
        volumen_relativo,
        None
    )


    if volumen is None:

        return 0


    if volumen >= 2.0:

        return 10


    if volumen >= 1.5:

        return 9


    if volumen >= 1.0:

        return 7


    if volumen >= 0.75:

        return 5


    if volumen >= 0.5:

        return 3


    return 1


# ============================================================
# ALERTA DE RIESGO
# NO PUNTUA
# ============================================================

def clasificar_riesgo_v4(
    volatilidad
):
    """
    La volatilidad deja de dar puntos.

    V4 separa:

        fuerza tecnica
        de
        riesgo de precio

    porque el paper historico demostro que
    penalizar fuertemente la volatilidad
    estaba degradando el ranking.
    """

    volatilidad = _numero(
        volatilidad,
        None
    )


    if volatilidad is None:

        return "SIN DATOS"


    if volatilidad < 15:

        return "BAJO"


    if volatilidad < 25:

        return "MEDIO"


    if volatilidad < 40:

        return "ALTO"


    return "MUY ALTO"


# ============================================================
# SCORE V4
# ============================================================

def calcular_score_v4(
    tendencia,
    rsi,
    fuerza_20d,
    fuerza_60d,
    fuerza_sector_20d,
    fuerza_sector_60d,
    distancia_sma20,
    volumen_relativo,
    volatilidad=None
):


    tendencia_score = (
        score_tendencia_v4(
            tendencia
        )
    )


    momentum_score = (
        score_momentum_v4(
            rsi
        )
    )


    fuerza_score = (
        score_fuerza_v4(
            fuerza_20d,
            fuerza_60d
        )
    )


    sector_score = (
        score_sector_v4(
            fuerza_sector_20d,
            fuerza_sector_60d
        )
    )


    continuacion_score = (
        score_continuacion_v4(
            distancia_sma20
        )
    )


    volumen_score = (
        score_volumen_v4(
            volumen_relativo
        )
    )


    total = (

        tendencia_score
        +
        momentum_score
        +
        fuerza_score
        +
        sector_score
        +
        continuacion_score
        +
        volumen_score
    )


    total = max(
        0,
        min(
            100,
            int(
                round(
                    total
                )
            )
        )
    )


    riesgo = (
        clasificar_riesgo_v4(
            volatilidad
        )
    )


    return {

        "version":
            SCORE_VERSION,

        "total":
            total,

        "tendencia":
            tendencia_score,

        "momentum":
            momentum_score,

        "fuerza_relativa":
            fuerza_score,

        "sector":
            sector_score,

        "continuacion":
            continuacion_score,

        "volumen":
            volumen_score,

        "riesgo":
            riesgo,
    }


# ============================================================
# PRIORIDAD EXPERIMENTAL
# ============================================================

def clasificar_prioridad_v4(
    score
):
    """
    Primera calibracion.

    Todavia NO se utiliza en produccion.

    Queremos comprobar primero como se distribuyen
    las señales historicas.
    """

    if score >= 96:

        return "A+"


    if score >= 94:

        return "A"


    if score >= 90:

        return "B"


    if score >= 84:

        return "C"


    return "D"