# analysis/thesis_engine.py


# ============================================================
# UTILIDADES
# ============================================================

def _texto(valor):
    if valor is None:
        return ""

    return str(valor).strip().upper()


def _lista_desde_db(valor):
    """
    Convierte los campos guardados como:
        A|B|C

    en:
        ["A", "B", "C"]
    """

    if not valor:
        return []

    if isinstance(valor, (list, tuple, set)):
        return [
            str(x).strip()
            for x in valor
            if x
        ]

    return [
        parte.strip()
        for parte in str(valor).split("|")
        if parte.strip()
    ]


# ============================================================
# EVALUACION TECNICA
# ============================================================

def evaluar_tecnico(tecnico):

    score = tecnico.get("score") or 0

    prioridad = _texto(
        tecnico.get("prioridad_estudio")
    )

    perfil = _texto(
        tecnico.get("perfil")
    )

    tendencia = _texto(
        tecnico.get("tendencia")
    )

    momentum = _texto(
        tecnico.get("momentum")
    )

    riesgo = _texto(
        tecnico.get("riesgo_clasificacion")
    )

    puntos = 0
    evidencias = []
    riesgos = []

    # --------------------------------------------------------
    # PRIORIDAD
    # --------------------------------------------------------

    if prioridad == "A+":
        puntos += 4
        evidencias.append(
            "Prioridad tecnica A+"
        )

    elif prioridad == "A":
        puntos += 3
        evidencias.append(
            "Prioridad tecnica A"
        )

    elif prioridad == "B":
        puntos += 1

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    if score >= 90:
        puntos += 3
        evidencias.append(
            "Score tecnico muy alto"
        )

    elif score >= 80:
        puntos += 2
        evidencias.append(
            "Score tecnico alto"
        )

    elif score >= 70:
        puntos += 1

    # --------------------------------------------------------
    # TENDENCIA
    # --------------------------------------------------------

    if tendencia in (
        "FUERTE",
        "ALCISTA",
        "MUY FUERTE"
    ):
        puntos += 2
        evidencias.append(
            "Tendencia favorable"
        )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if momentum in (
        "FUERTE",
        "POSITIVO",
        "MUY FUERTE"
    ):
        puntos += 1
        evidencias.append(
            "Momentum favorable"
        )

    # --------------------------------------------------------
    # RIESGO
    # --------------------------------------------------------

    if riesgo in (
        "ALTO",
        "MUY ALTO"
    ):
        puntos -= 2
        riesgos.append(
            "Riesgo tecnico elevado"
        )

    return {
        "puntos": puntos,
        "evidencias": evidencias,
        "riesgos": riesgos,
        "prioridad": prioridad,
        "perfil": perfil
    }


# ============================================================
# EVALUACION FUNDAMENTAL
# ============================================================

def evaluar_fundamental(fundamental):

    if not fundamental:
        return {
            "disponible": False,
            "puntos": 0,
            "evidencias": [],
            "riesgos": [
                "Sin analisis fundamental disponible"
            ]
        }

    score = (
        fundamental.get("score_fundamental")
        or 0
    )

    calidad = _texto(
        fundamental.get(
            "calidad_fundamental"
        )
    )

    crecimiento = _texto(
        fundamental.get(
            "crecimiento"
        )
    )

    rentabilidad = _texto(
        fundamental.get(
            "rentabilidad"
        )
    )

    balance = _texto(
        fundamental.get(
            "balance"
        )
    )

    cash_flow = _texto(
        fundamental.get(
            "cash_flow"
        )
    )

    valoracion = _texto(
        fundamental.get(
            "valoracion"
        )
    )

    puntos = 0
    evidencias = []
    riesgos = []

    # --------------------------------------------------------
    # SCORE FUNDAMENTAL
    # --------------------------------------------------------

    if score >= 80:
        puntos += 4
        evidencias.append(
            "Fundamentales muy fuertes"
        )

    elif score >= 65:
        puntos += 3
        evidencias.append(
            "Fundamentales solidos"
        )

    elif score >= 50:
        puntos += 1

    elif score < 35:
        puntos -= 2
        riesgos.append(
            "Score fundamental bajo"
        )

    # --------------------------------------------------------
    # CALIDAD
    # --------------------------------------------------------

    if calidad in (
        "SOLIDA",
        "MUY SOLIDA",
        "ALTA"
    ):
        puntos += 2
        evidencias.append(
            "Calidad fundamental favorable"
        )

    elif calidad in (
        "DEBIL",
        "MUY DEBIL"
    ):
        puntos -= 2
        riesgos.append(
            "Calidad fundamental debil"
        )

    # --------------------------------------------------------
    # CRECIMIENTO
    # --------------------------------------------------------

    if crecimiento in (
        "FUERTE",
        "MUY FUERTE"
    ):
        puntos += 2
        evidencias.append(
            "Crecimiento fuerte"
        )

    elif crecimiento == "MODERADO":
        puntos += 1

    elif crecimiento in (
        "NEGATIVO",
        "DEBIL"
    ):
        puntos -= 1
        riesgos.append(
            "Crecimiento debil"
        )

    # --------------------------------------------------------
    # RENTABILIDAD
    # --------------------------------------------------------

    if rentabilidad in (
        "ALTA",
        "MUY ALTA"
    ):
        puntos += 2
        evidencias.append(
            "Rentabilidad elevada"
        )

    elif rentabilidad == "NEGATIVA":
        puntos -= 2
        riesgos.append(
            "Rentabilidad negativa"
        )

    # --------------------------------------------------------
    # BALANCE
    # --------------------------------------------------------

    if balance in (
        "SOLIDO",
        "MUY SOLIDO"
    ):
        puntos += 1
        evidencias.append(
            "Balance solido"
        )

    # --------------------------------------------------------
    # CASH FLOW
    # --------------------------------------------------------

    if cash_flow == "FUERTE":
        puntos += 2
        evidencias.append(
            "Generacion de caja fuerte"
        )

    elif cash_flow == "BAJO":
        puntos -= 1
        riesgos.append(
            "Generacion de caja reducida"
        )

    # --------------------------------------------------------
    # VALORACION
    # --------------------------------------------------------

    if valoracion in (
        "FAVORABLE",
        "ATRACTIVA"
    ):
        puntos += 2
        evidencias.append(
            "Valoracion favorable"
        )

    elif valoracion == "RAZONABLE":
        puntos += 1

    elif valoracion == "EXIGENTE":
        puntos -= 1
        riesgos.append(
            "Valoracion exigente"
        )

    elif valoracion == "MUY EXIGENTE":
        puntos -= 3
        riesgos.append(
            "Valoracion muy exigente"
        )

    # Alertas ya detectadas por el classifier

    alertas = _lista_desde_db(
        fundamental.get("alertas")
    )

    for alerta in alertas:
        riesgos.append(alerta)

    return {
        "disponible": True,
        "puntos": puntos,
        "score": score,
        "calidad": calidad,
        "valoracion": valoracion,
        "evidencias": evidencias,
        "riesgos": riesgos
    }


# ============================================================
# EVALUACION NOTICIAS
# ============================================================

def evaluar_noticias(news):

    if not news:
        return {
            "disponible": False,
            "puntos": 0,
            "evidencias": [],
            "riesgos": [
                "Sin contexto reciente de noticias"
            ]
        }

    contexto = _texto(
        news.get("contexto")
    )

    movimiento = _texto(
        news.get("movimiento_explicado")
    )

    fuerza = _texto(
        news.get("fuerza_catalizador")
    )

    riesgo_narrativo = _texto(
        news.get("riesgo_narrativo")
    )

    puntos = 0
    evidencias = []
    riesgos = []

    # --------------------------------------------------------
    # CONTEXTO
    # --------------------------------------------------------

    if contexto == "POSITIVO":
        puntos += 3
        evidencias.append(
            "Noticias recientes positivas"
        )

    elif contexto == "MIXTO":
        puntos += 0
        riesgos.append(
            "Contexto de noticias mixto"
        )

    elif contexto == "NEGATIVO":
        puntos -= 3
        riesgos.append(
            "Noticias recientes negativas"
        )

    elif contexto == "SIN NOTICIAS":
        riesgos.append(
            "Movimiento sin catalizador informativo visible"
        )

    # --------------------------------------------------------
    # MOVIMIENTO EXPLICADO
    # --------------------------------------------------------

    if movimiento == "SI" or movimiento == "SÍ":
        puntos += 2
        evidencias.append(
            "Movimiento respaldado por catalizador visible"
        )

    elif movimiento == "PARCIALMENTE":
        puntos += 1

    # --------------------------------------------------------
    # FUERZA CATALIZADOR
    # --------------------------------------------------------

    if fuerza == "ALTA":
        puntos += 3
        evidencias.append(
            "Catalizador fuerte"
        )

    elif fuerza == "MEDIA":
        puntos += 2
        evidencias.append(
            "Catalizador relevante"
        )

    elif fuerza == "BAJA":
        puntos += 1

    # --------------------------------------------------------
    # RIESGO NARRATIVO
    # --------------------------------------------------------

    if riesgo_narrativo == "ALTO":
        puntos -= 2
        riesgos.append(
            "Riesgo narrativo alto"
        )

    elif riesgo_narrativo == "MEDIO":
        puntos -= 1

    # Evidencias concretas del News Analyzer

    positivas = _lista_desde_db(
        news.get("evidencias_positivas")
    )

    negativas = _lista_desde_db(
        news.get("evidencias_negativas")
    )

    riesgos_news = _lista_desde_db(
        news.get("riesgos")
    )

    for evidencia in positivas:
        evidencias.append(
            f"Noticia: {evidencia}"
        )

    for evidencia in negativas:
        riesgos.append(
            f"Noticia negativa: {evidencia}"
        )

    riesgos.extend(riesgos_news)

    return {
        "disponible": True,
        "puntos": puntos,
        "contexto": contexto,
        "movimiento_explicado": movimiento,
        "fuerza_catalizador": fuerza,
        "evidencias": evidencias,
        "riesgos": riesgos
    }


# ============================================================
# CLASIFICAR TESIS
# ============================================================

def clasificar_tesis(
    tecnico_eval,
    fundamental_eval,
    news_eval
):

    t = tecnico_eval["puntos"]

    f = fundamental_eval["puntos"]

    n = news_eval["puntos"]

    fund_disponible = (
        fundamental_eval["disponible"]
    )

    news_disponible = (
        news_eval["disponible"]
    )

    contexto_news = news_eval.get(
        "contexto",
        ""
    )

    valoracion = fundamental_eval.get(
        "valoracion",
        ""
    )

    calidad = fundamental_eval.get(
        "calidad",
        ""
    )

    # ========================================================
    # CONTRADICCION
    # ========================================================

    if (
        t >= 6
        and (
            f <= -1
            or n <= -2
        )
    ):
        return "CONTRADICTORIA"

    # ========================================================
    # CATALIZADOR
    # ========================================================

    if (
        t >= 5
        and n >= 4
    ):
        return "CATALIZADOR"

    # ========================================================
    # CALIDAD A PRECIO EXIGENTE
    # ========================================================

    if (
        t >= 5
        and fund_disponible
        and calidad in (
            "SOLIDA",
            "MUY SOLIDA",
            "ALTA"
        )
        and valoracion in (
            "EXIGENTE",
            "MUY EXIGENTE"
        )
    ):
        return "CALIDAD_A_PRECIO_EXIGENTE"

    # ========================================================
    # REPRICING
    # ========================================================

    if (
        t >= 6
        and f >= 5
        and n >= 1
    ):
        return "REPRICING"

    # ========================================================
    # DESCUBRIMIENTO
    # ========================================================

    if (
        t >= 6
        and f >= 5
        and (
            not news_disponible
            or contexto_news == "SIN NOTICIAS"
        )
    ):
        return "DESCUBRIMIENTO"

    # ========================================================
    # MOMENTUM
    # ========================================================

    if (
        t >= 6
        and (
            not fund_disponible
            or f < 5
        )
        and n <= 1
    ):
        return "MOMENTUM"

    # ========================================================
    # ESPECULATIVA
    # ========================================================

    if (
        t >= 4
        and f <= 0
    ):
        return "ESPECULATIVA"

    return "SIN_TESIS_CLARA"


# ============================================================
# CONFIANZA
# ============================================================

def calcular_confianza(
    tecnico_eval,
    fundamental_eval,
    news_eval
):

    capas = 1

    if fundamental_eval["disponible"]:
        capas += 1

    if news_eval["disponible"]:
        capas += 1

    total = (
        tecnico_eval["puntos"]
        + max(
            fundamental_eval["puntos"],
            0
        )
        + max(
            news_eval["puntos"],
            0
        )
    )

    if (
        capas == 3
        and total >= 15
    ):
        return "ALTA"

    if (
        capas >= 2
        and total >= 9
    ):
        return "MEDIA"

    return "BAJA"


# ============================================================
# GENERAR LECTURA
# ============================================================

def generar_lectura(
    tesis,
    tecnico_eval,
    fundamental_eval,
    news_eval
):

    lecturas = {

        "CATALIZADOR":
            "La fortaleza tecnica coincide con un catalizador "
            "reciente identificable. El movimiento dispone de "
            "una explicacion narrativa visible y merece estudiar "
            "si el impacto puede mantenerse.",

        "REPRICING":
            "Existe confluencia entre fortaleza tecnica, "
            "fundamentales favorables y contexto reciente. "
            "El mercado podria estar revisando al alza su "
            "valoracion de la empresa.",

        "DESCUBRIMIENTO":
            "La accion presenta fortaleza tecnica junto con "
            "fundamentales favorables, pero sin un catalizador "
            "reciente claramente identificado. Puede tratarse "
            "de un proceso de descubrimiento gradual por parte "
            "del mercado.",

        "MOMENTUM":
            "La tesis actual depende principalmente de la "
            "fortaleza tecnica. No existe suficiente respaldo "
            "fundamental o narrativo para explicar el movimiento "
            "con mayor profundidad.",

        "CALIDAD_A_PRECIO_EXIGENTE":
            "La empresa presenta caracteristicas fundamentales "
            "favorables y fortaleza tecnica, pero la valoracion "
            "actual es exigente. La calidad puede ser real sin "
            "que el precio actual ofrezca necesariamente un "
            "punto de entrada atractivo.",

        "ESPECULATIVA":
            "La fortaleza tecnica no esta respaldada actualmente "
            "por fundamentales suficientes. La oportunidad tiene "
            "un componente especulativo elevado y depende en mayor "
            "medida del comportamiento del precio.",

        "CONTRADICTORIA":
            "Existe una divergencia importante entre la fortaleza "
            "tecnica y alguna de las capas de contexto. El precio "
            "muestra fortaleza, pero fundamentales o noticias "
            "introducen riesgos que deben investigarse antes de "
            "formular una tesis positiva.",

        "SIN_TESIS_CLARA":
            "Las capas disponibles no forman todavia una tesis "
            "suficientemente coherente. Puede ser un activo "
            "interesante para seguimiento, pero falta confluencia "
            "entre tecnica, fundamentales y contexto."
    }

    return lecturas[tesis]


# ============================================================
# THESIS ENGINE
# ============================================================

def construir_tesis(
    tecnico,
    fundamental=None,
    news=None
):
    """
    Combina:

        tecnico
        fundamental
        noticias

    y genera una hipotesis de investigacion.

    NO genera una recomendacion de compra/venta.
    """

    tecnico_eval = evaluar_tecnico(
        tecnico
    )

    fundamental_eval = evaluar_fundamental(
        fundamental
    )

    news_eval = evaluar_noticias(
        news
    )

    tesis = clasificar_tesis(
        tecnico_eval,
        fundamental_eval,
        news_eval
    )

    confianza = calcular_confianza(
        tecnico_eval,
        fundamental_eval,
        news_eval
    )

    evidencias = (
        tecnico_eval["evidencias"]
        + fundamental_eval["evidencias"]
        + news_eval["evidencias"]
    )

    riesgos = (
        tecnico_eval["riesgos"]
        + fundamental_eval["riesgos"]
        + news_eval["riesgos"]
    )

    # Quitar duplicados manteniendo orden

    evidencias = list(
        dict.fromkeys(evidencias)
    )

    riesgos = list(
        dict.fromkeys(riesgos)
    )

    lectura = generar_lectura(
        tesis,
        tecnico_eval,
        fundamental_eval,
        news_eval
    )

    return {

        "symbol": tecnico.get(
            "symbol"
        ),

        "tesis": tesis,

        "confianza": confianza,

        "score_tecnico": tecnico.get(
            "score"
        ),

        "prioridad_tecnica": tecnico.get(
            "prioridad_estudio"
        ),

        "score_fundamental":
            fundamental_eval.get(
                "score"
            ),

        "contexto_noticias":
            news_eval.get(
                "contexto"
            ),

        "puntos_tecnicos":
            tecnico_eval["puntos"],

        "puntos_fundamentales":
            fundamental_eval["puntos"],

        "puntos_noticias":
            news_eval["puntos"],

        "evidencias": evidencias,

        "riesgos": riesgos,

        "lectura": lectura
    }