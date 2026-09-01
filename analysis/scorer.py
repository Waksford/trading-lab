def interpretar_activo(ultimo):
    """
    Interpreta los indicadores de la última sesión.

    No genera recomendaciones de compra o venta.
    """

    precio = ultimo["close"]
    sma20 = ultimo["sma_20"]
    sma50 = ultimo["sma_50"]
    rsi = ultimo["rsi_14"]
    volatilidad = ultimo["volatility_20"]
    volumen_relativo = ultimo["relative_volume"]

    distancia_sma20 = ultimo[
        "distance_sma20"
    ]

    distancia_sma50 = ultimo[
        "distance_sma50"
    ]


    resultado = {

        "tendencia": "NEUTRAL",

        "momentum": "NEUTRAL",

        "volumen": "NORMAL",

        "volatilidad": "MEDIA",

        "observaciones": []
    }


    # ========================================================
    # TENDENCIA
    # ========================================================

    if (
        precio > sma20
        and precio > sma50
        and sma20 > sma50
    ):

        resultado[
            "tendencia"
        ] = "FUERTE ALCISTA"

        resultado[
            "observaciones"
        ].append(
            "Precio por encima de SMA20 y SMA50, "
            "con SMA20 por encima de SMA50."
        )


    elif (
        precio > sma20
        and precio > sma50
    ):

        resultado[
            "tendencia"
        ] = "ALCISTA"

        resultado[
            "observaciones"
        ].append(
            "Precio por encima de SMA20 y SMA50."
        )


    elif (
        precio < sma20
        and precio < sma50
        and sma20 < sma50
    ):

        resultado[
            "tendencia"
        ] = "FUERTE BAJISTA"

        resultado[
            "observaciones"
        ].append(
            "Precio por debajo de SMA20 y SMA50, "
            "con SMA20 por debajo de SMA50."
        )


    elif (
        precio < sma20
        and precio < sma50
    ):

        resultado[
            "tendencia"
        ] = "BAJISTA"

        resultado[
            "observaciones"
        ].append(
            "Precio por debajo de SMA20 y SMA50."
        )


    else:

        resultado[
            "tendencia"
        ] = "MIXTA"

        resultado[
            "observaciones"
        ].append(
            "Las medias móviles no muestran "
            "una tendencia clara."
        )


    # ========================================================
    # MOMENTUM / RSI
    # ========================================================

    if rsi >= 70:

        resultado[
            "momentum"
        ] = "MUY ALTO"

        resultado[
            "observaciones"
        ].append(
            "RSI por encima de 70: momentum elevado."
        )


    elif rsi >= 55:

        resultado[
            "momentum"
        ] = "POSITIVO"


    elif rsi <= 30:

        resultado[
            "momentum"
        ] = "MUY BAJO"

        resultado[
            "observaciones"
        ].append(
            "RSI por debajo de 30: momentum muy débil."
        )


    elif rsi <= 45:

        resultado[
            "momentum"
        ] = "NEGATIVO"


    else:

        resultado[
            "momentum"
        ] = "NEUTRAL"


    # ========================================================
    # VOLUMEN
    # ========================================================

    if volumen_relativo >= 2:

        resultado[
            "volumen"
        ] = "MUY ALTO"

        resultado[
            "observaciones"
        ].append(
            f"Volumen {volumen_relativo:.2f}x "
            "superior a la media reciente."
        )


    elif volumen_relativo >= 1.5:

        resultado[
            "volumen"
        ] = "ALTO"

        resultado[
            "observaciones"
        ].append(
            f"Volumen elevado: "
            f"{volumen_relativo:.2f}x la media."
        )


    elif volumen_relativo <= 0.6:

        resultado[
            "volumen"
        ] = "BAJO"


    # ========================================================
    # VOLATILIDAD
    # ========================================================

    if volatilidad >= 50:

        resultado[
            "volatilidad"
        ] = "MUY ALTA"


    elif volatilidad >= 30:

        resultado[
            "volatilidad"
        ] = "ALTA"


    elif volatilidad >= 15:

        resultado[
            "volatilidad"
        ] = "MEDIA"


    else:

        resultado[
            "volatilidad"
        ] = "BAJA"


    # ========================================================
    # DISTANCIA MEDIAS
    # ========================================================

    if distancia_sma20 >= 10:

        resultado[
            "observaciones"
        ].append(
            f"Precio {distancia_sma20:.1f}% "
            "por encima de SMA20."
        )


    elif distancia_sma20 <= -10:

        resultado[
            "observaciones"
        ].append(
            f"Precio {abs(distancia_sma20):.1f}% "
            "por debajo de SMA20."
        )


    if abs(
        distancia_sma50
    ) >= 15:

        resultado[
            "observaciones"
        ].append(
            "Distancia elevada respecto a SMA50: "
            f"{distancia_sma50:+.1f}%."
        )


    return resultado


# ============================================================
# SCORE V3
# ============================================================

def calcular_score(
    ultimo,
    analisis,
    fuerza_20d=0,
    fuerza_60d=0,
    fuerza_sector_20d=None,
    fuerza_sector_60d=None
):
    """
    Score técnico V3.

    Máximo: 100 puntos.

    No representa una recomendación de compra.
    Mide interés técnico para investigar el activo.
    """

    SCORE_VERSION = "v3"


    # ========================================================
    # TENDENCIA - máximo 25
    # ========================================================

    tendencia = analisis[
        "tendencia"
    ]


    if tendencia == "FUERTE ALCISTA":

        score_tendencia = 25


    elif tendencia == "ALCISTA":

        score_tendencia = 20


    elif tendencia == "MIXTA":

        score_tendencia = 12


    elif tendencia == "BAJISTA":

        score_tendencia = 5


    else:

        score_tendencia = 2


    # ========================================================
    # MOMENTUM - máximo 15
    # ========================================================

    rsi = ultimo[
        "rsi_14"
    ]


    if 55 <= rsi < 65:

        score_momentum = 15


    elif 50 <= rsi < 55:

        score_momentum = 12


    elif 65 <= rsi < 70:

        score_momentum = 13


    elif 45 <= rsi < 50:

        score_momentum = 8


    elif 70 <= rsi < 75:

        score_momentum = 8


    elif rsi >= 75:

        score_momentum = 4


    elif 30 <= rsi < 45:

        score_momentum = 5


    else:

        score_momentum = 2


    # ========================================================
    # FUERZA VS SPY - máximo 20
    # ========================================================

    score_fuerza = 0


    # 20 sesiones - máximo 8

    if fuerza_20d >= 10:

        score_fuerza += 8


    elif fuerza_20d >= 5:

        score_fuerza += 7


    elif fuerza_20d >= 2:

        score_fuerza += 5


    elif fuerza_20d >= 0:

        score_fuerza += 3


    elif fuerza_20d >= -3:

        score_fuerza += 1


    # 60 sesiones - máximo 12

    if fuerza_60d >= 20:

        score_fuerza += 12


    elif fuerza_60d >= 10:

        score_fuerza += 10


    elif fuerza_60d >= 5:

        score_fuerza += 7


    elif fuerza_60d >= 0:

        score_fuerza += 5


    elif fuerza_60d >= -5:

        score_fuerza += 2


    # ========================================================
    # FUERZA VS SECTOR - máximo 15
    # ========================================================

    score_sector = 0


    # Si no tenemos benchmark sectorial,
    # no inventamos puntos.

    if (
        fuerza_sector_20d is not None
        and fuerza_sector_60d is not None
    ):

        # 20 sesiones - máximo 6

        if fuerza_sector_20d >= 10:

            score_sector += 6


        elif fuerza_sector_20d >= 5:

            score_sector += 5


        elif fuerza_sector_20d >= 2:

            score_sector += 4


        elif fuerza_sector_20d >= 0:

            score_sector += 2


        elif fuerza_sector_20d >= -3:

            score_sector += 1


        # 60 sesiones - máximo 9

        if fuerza_sector_60d >= 20:

            score_sector += 9


        elif fuerza_sector_60d >= 10:

            score_sector += 8


        elif fuerza_sector_60d >= 5:

            score_sector += 6


        elif fuerza_sector_60d >= 0:

            score_sector += 4


        elif fuerza_sector_60d >= -5:

            score_sector += 2


    # ========================================================
    # PENALIZACIÓN RELATIVA
    # ========================================================

    penalizacion_relativa = 0


    # Pierde contra SPY en ambos periodos

    if (
        fuerza_20d < 0
        and fuerza_60d < 0
    ):

        penalizacion_relativa += 6


    # Debilidad fuerte contra SPY

    if (
        fuerza_20d <= -3
        and fuerza_60d <= -3
    ):

        penalizacion_relativa += 4


    # Pierde también contra su sector

    if (
        fuerza_sector_20d is not None
        and fuerza_sector_60d is not None
        and fuerza_sector_20d < 0
        and fuerza_sector_60d < 0
    ):

        penalizacion_relativa += 4


    # ========================================================
    # RIESGO - máximo 15
    # ========================================================

    volatilidad = ultimo[
        "volatility_20"
    ]


    if volatilidad < 15:

        score_riesgo = 15


    elif volatilidad < 25:

        score_riesgo = 13


    elif volatilidad < 40:

        score_riesgo = 10


    elif volatilidad < 60:

        score_riesgo = 6


    else:

        score_riesgo = 3


    # ========================================================
    # VOLUMEN - máximo 10
    # ========================================================

    volumen = ultimo[
        "relative_volume"
    ]


    if volumen >= 1.5:

        score_volumen = 10


    elif volumen >= 1.0:

        score_volumen = 8


    elif volumen >= 0.7:

        score_volumen = 6


    elif volumen >= 0.4:

        score_volumen = 4


    else:

        score_volumen = 2


    # ========================================================
    # TOTAL
    # ========================================================

    total = (

        score_tendencia

        + score_momentum

        + score_fuerza

        + score_sector

        + score_riesgo

        + score_volumen

        - penalizacion_relativa
    )


    total = max(
        0,
        min(
            100,
            total
        )
    )


    return {

        "version":
            SCORE_VERSION,

        "total":
            total,

        "tendencia":
            score_tendencia,

        "momentum":
            score_momentum,

        "fuerza_relativa":
            score_fuerza,

        "sector":
            score_sector,

        "riesgo":
            score_riesgo,

        "volumen":
            score_volumen,

        "penalizacion_relativa":
            penalizacion_relativa
    }
def clasificar_candidato(
    score,
    analisis,
    fuerza_20d,
    fuerza_60d,
    fuerza_sector_20d=None,
    fuerza_sector_60d=None
):
    """
    Genera una interpretación humana del candidato.

    No modifica el Score V3.
    No constituye una recomendación de compra/venta.

    Devuelve:
        perfil
        fortaleza_mercado
        fortaleza_sector
        riesgo
        volumen
        calidad
    """

    total = score["total"]

    score_spy = score["fuerza_relativa"]
    score_sector = score["sector"]
    score_riesgo = score["riesgo"]
    score_volumen = score["volumen"]

    tendencia = analisis["tendencia"]


    # ========================================================
    # FORTALEZA FRENTE AL MERCADO
    # ========================================================

    if (
        fuerza_20d >= 5
        and fuerza_60d >= 10
    ):
        fortaleza_mercado = "MUY FUERTE"

    elif (
        fuerza_20d >= 0
        and fuerza_60d >= 0
    ):
        fortaleza_mercado = "FUERTE"

    elif (
        fuerza_20d < 0
        and fuerza_60d >= 5
    ):
        fortaleza_mercado = "FORTALEZA DE MEDIO PLAZO"

    elif (
        fuerza_20d >= 0
        and fuerza_60d < 0
    ):
        fortaleza_mercado = "MEJORANDO"

    else:
        fortaleza_mercado = "DÉBIL"


    # ========================================================
    # FORTALEZA FRENTE AL SECTOR
    # ========================================================

    if (
        fuerza_sector_20d is None
        or fuerza_sector_60d is None
    ):
        fortaleza_sector = "SIN DATOS"

    elif (
        fuerza_sector_20d >= 5
        and fuerza_sector_60d >= 10
    ):
        fortaleza_sector = "LÍDER"

    elif (
        fuerza_sector_20d >= 0
        and fuerza_sector_60d >= 0
    ):
        fortaleza_sector = "FUERTE"

    elif (
        fuerza_sector_20d < 0
        and fuerza_sector_60d >= 5
    ):
        fortaleza_sector = "FUERTE A MEDIO PLAZO"

    elif (
        fuerza_sector_20d >= 0
        and fuerza_sector_60d < 0
    ):
        fortaleza_sector = "MEJORANDO"

    else:
        fortaleza_sector = "DÉBIL"


    # ========================================================
    # RIESGO
    # ========================================================

    if score_riesgo >= 13:
        riesgo = "BAJO"

    elif score_riesgo >= 10:
        riesgo = "MEDIO"

    elif score_riesgo >= 6:
        riesgo = "ALTO"

    else:
        riesgo = "MUY ALTO"


    # ========================================================
    # VOLUMEN
    # ========================================================

    if score_volumen >= 10:
        volumen = "MUY ALTO"

    elif score_volumen >= 8:
        volumen = "ALTO"

    elif score_volumen >= 6:
        volumen = "NORMAL"

    elif score_volumen >= 4:
        volumen = "BAJO"

    else:
        volumen = "MUY BAJO"


    # ========================================================
    # PERFIL GENERAL
    # ========================================================

    if (
        total >= 85
        and score_spy >= 17
        and score_sector >= 11
        and score_riesgo >= 10
    ):
        perfil = "FUERTE Y EQUILIBRADO"

    elif (
        total >= 85
        and score_spy >= 18
        and score_sector >= 13
        and score_riesgo < 10
    ):
        perfil = "FUERTE PERO VOLÁTIL"

    elif (
        score_sector >= 13
        and score_spy < 17
    ):
        perfil = "LÍDER DE SU SECTOR"

    elif (
        score_spy >= 18
        and score_sector < 10
    ):
        perfil = "FUERTE CONTRA EL MERCADO"

    elif (
        fuerza_20d < 0
        and fuerza_60d >= 10
    ):
        perfil = "CONSOLIDANDO TENDENCIA"

    elif (
        fuerza_20d >= 5
        and fuerza_60d < 5
    ):
        perfil = "ACELERANDO"

    elif (
        tendencia == "FUERTE ALCISTA"
        and total >= 75
    ):
        perfil = "ALCISTA"

    else:
        perfil = "EN OBSERVACIÓN"


    # ========================================================
    # CALIDAD GENERAL
    # ========================================================

    if total >= 90:
        calidad = "EXCEPCIONAL"

    elif total >= 85:
        calidad = "MUY ALTA"

    elif total >= 80:
        calidad = "ALTA"

    elif total >= 75:
        calidad = "INTERESANTE"

    else:
        calidad = "NORMAL"


    return {
        "perfil": perfil,
        "calidad": calidad,
        "fortaleza_mercado": fortaleza_mercado,
        "fortaleza_sector": fortaleza_sector,
        "riesgo": riesgo,
        "volumen": volumen
    }
def calcular_prioridad_estudio(
    score,
    clasificacion,
    rsi,
    distancia_sma20,
    distancia_sma50,
    fuerza_sector_20d=None,
    fuerza_sector_60d=None
):
    """
    Calcula una prioridad de ESTUDIO.

    No es recomendación de compra.

    Combina:
    - Score V3
    - Perfil
    - Riesgo
    - Volumen
    - RSI
    - Extensión respecto a medias
    - Fuerza sectorial

    Devuelve:
        prioridad
        motivo
        alertas
    """

    total = score["total"]

    perfil = clasificacion["perfil"]

    riesgo = clasificacion["riesgo"]

    volumen = clasificacion["volumen"]

    fortaleza_mercado = (
        clasificacion[
            "fortaleza_mercado"
        ]
    )

    fortaleza_sector = (
        clasificacion[
            "fortaleza_sector"
        ]
    )


    # ========================================================
    # ALERTAS
    # ========================================================

    alertas = []


    # --------------------------------------------------------
    # RSI elevado
    # --------------------------------------------------------

    if rsi >= 75:

        alertas.append(
            "RSI MUY ALTO"
        )

    elif rsi >= 70:

        alertas.append(
            "RSI ELEVADO"
        )


    # --------------------------------------------------------
    # Precio extendido
    # --------------------------------------------------------

    if distancia_sma20 >= 15:

        alertas.append(
            "MUY ALEJADO SMA20"
        )

    elif distancia_sma20 >= 10:

        alertas.append(
            "ALEJADO SMA20"
        )


    if distancia_sma50 >= 25:

        alertas.append(
            "MUY ALEJADO SMA50"
        )


    # --------------------------------------------------------
    # Riesgo
    # --------------------------------------------------------

    if riesgo == "MUY ALTO":

        alertas.append(
            "RIESGO MUY ALTO"
        )

    elif riesgo == "ALTO":

        alertas.append(
            "RIESGO ALTO"
        )


    # --------------------------------------------------------
    # Volumen
    # --------------------------------------------------------

    if volumen == "MUY BAJO":

        alertas.append(
            "VOLUMEN MUY BAJO"
        )

    elif volumen == "BAJO":

        alertas.append(
            "VOLUMEN BAJO"
        )


    # --------------------------------------------------------
    # Sector
    # --------------------------------------------------------

    if fortaleza_sector == "DÉBIL":

        alertas.append(
            "DÉBIL VS SECTOR"
        )


    # ========================================================
    # PRIORIDAD BASE
    # ========================================================

    prioridad = "D"


    # ========================================================
    # A+
    #
    # Muy completo y sin señales de extensión/riesgo serio.
    # ========================================================

    if (
        total >= 90

        and perfil
        == "FUERTE Y EQUILIBRADO"

        and riesgo
        in [
            "BAJO",
            "MEDIO"
        ]

        and fortaleza_mercado
        == "MUY FUERTE"

        and fortaleza_sector
        in [
            "LÍDER",
            "FUERTE"
        ]

        and rsi < 70

        and distancia_sma20 < 10

        and volumen
        not in [
            "MUY BAJO"
        ]
    ):

        prioridad = "A+"


    # ========================================================
    # A
    # ========================================================

    elif (
        total >= 85

        and perfil
        in [
            "FUERTE Y EQUILIBRADO",
            "LÍDER DE SU SECTOR"
        ]

        and riesgo
        not in [
            "MUY ALTO"
        ]

        and rsi < 75
    ):

        prioridad = "A"


    # ========================================================
    # B
    # ========================================================

    elif (
        total >= 80

        and perfil
        in [
            "FUERTE Y EQUILIBRADO",
            "FUERTE PERO VOLÁTIL",
            "LÍDER DE SU SECTOR",
            "FUERTE CONTRA EL MERCADO"
        ]
    ):

        prioridad = "B"


    # ========================================================
    # C
    # ========================================================

    elif total >= 75:

        prioridad = "C"


    # ========================================================
    # DEGRADACIONES POR ALERTAS SERIAS
    # ========================================================

    alertas_serias = 0


    for alerta in alertas:

        if alerta in [
            "RSI MUY ALTO",
            "MUY ALEJADO SMA20",
            "MUY ALEJADO SMA50",
            "RIESGO MUY ALTO",
            "VOLUMEN MUY BAJO",
            "DÉBIL VS SECTOR"
        ]:

            alertas_serias += 1


    # A+ con una alerta seria baja a A

    if (
        prioridad == "A+"
        and alertas_serias >= 1
    ):

        prioridad = "A"


    # A con dos alertas serias baja a B

    elif (
        prioridad == "A"
        and alertas_serias >= 2
    ):

        prioridad = "B"


    # ========================================================
    # MOTIVO
    # ========================================================

    if prioridad == "A+":

        motivo = (
            "Candidato muy completo: "
            "fuerte contra mercado y sector, "
            "riesgo contenido y sin señales "
            "claras de extensión."
        )


    elif prioridad == "A":

        motivo = (
            "Candidato de alta calidad técnica "
            "que merece revisión prioritaria."
        )


    elif prioridad == "B":

        motivo = (
            "Candidato interesante, pero presenta "
            "algún factor que requiere revisión."
        )


    elif prioridad == "C":

        motivo = (
            "Interesante para seguimiento, "
            "pero todavía no destaca suficientemente."
        )


    else:

        motivo = (
            "Baja prioridad de estudio actualmente."
        )


    return {
        "prioridad": prioridad,
        "motivo_prioridad": motivo,
        "alertas": alertas
    }