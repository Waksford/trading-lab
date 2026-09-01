import os
import re
import requests

from datetime import (
    datetime,
    timedelta,
    timezone
)

from dotenv import load_dotenv


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()


API_KEY = os.getenv(
    "ALPACA_API_KEY"
)

SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY"
)


if not API_KEY or not SECRET_KEY:

    raise ValueError(
        "No se han encontrado las claves "
        "de Alpaca en .env"
    )


NEWS_URL = (
    "https://data.alpaca.markets/"
    "v1beta1/news"
)


HEADERS = {

    "APCA-API-KEY-ID":
        API_KEY,

    "APCA-API-SECRET-KEY":
        SECRET_KEY
}


DIAS_NOTICIAS = 14

MAX_NOTICIAS = 20


# ============================================================
# CATALIZADORES GENERALES
#
# Detectan DE QUÉ trata la noticia.
# No determinan por sí solos si es positiva.
# ============================================================

CATALIZADORES = {

    "RESULTADOS": [
        "earnings",
        "quarter results",
        "quarterly results",
        "revenue",
        "sales",
        "eps",
        "net income"
    ],

    "GUIDANCE": [
        "guidance",
        "outlook",
        "forecast",
        "raises forecast",
        "raises guidance",
        "reaffirms guidance"
    ],

    "CONTRATO": [
        "contract",
        "agreement",
        "partnership",
        "deal",
        "awarded",
        "selected by",
        "strategic partnership"
    ],

    "ADQUISICION": [
        "acquisition",
        "acquire",
        "acquires",
        "merger",
        "buyout",
        "takeover"
    ],

    "FDA_REGULATORIO": [
        "fda",
        "regulatory approval",
        "clinical trial",
        "phase 1",
        "phase 2",
        "phase 3"
    ],

    "ANALISTAS": [
        "upgrade",
        "downgrade",
        "price target",
        "initiates coverage",
        "outperform",
        "underperform",
        "buy rating",
        "sell rating"
    ],

    "PRODUCTO": [
        "launch",
        "new product",
        "product launch",
        "release",
        "unveils",
        "introduces"
    ],

    "EXPANSION": [
        "expansion",
        "new facility",
        "new market",
        "expands",
        "international expansion"
    ],

    "CAPITAL": [
        "offering",
        "share offering",
        "stock offering",
        "secondary offering",
        "registered direct offering",
        "at-the-market offering"
    ]
}


# ============================================================
# EVIDENCIAS POSITIVAS
#
# Estas sí intentan determinar dirección.
# ============================================================

EVIDENCIAS_POSITIVAS = {

    "RESULTADOS_SUPERIORES": [
        "beats estimate",
        "beats estimates",
        "beat estimate",
        "beat estimates",
        "tops estimate",
        "tops estimates",
        "above estimate",
        "above estimates",
        "exceeds estimate",
        "exceeds estimates"
    ],

    "GUIDANCE_AL_ALZA": [
        "raises guidance",
        "raises forecast",
        "boosts outlook",
        "increases outlook",
        "raises outlook"
    ],

    "APROBACION": [
        "fda approval",
        "fda approves",
        "approved by the fda",
        "regulatory approval"
    ],

    "ENSAYO_POSITIVO": [
        "positive trial",
        "positive results",
        "met primary endpoint",
        "meets primary endpoint",
        "successful trial"
    ],

    "CONTRATO_POSITIVO": [
        "awarded contract",
        "wins contract",
        "won contract",
        "selected by",
        "strategic partnership"
    ],

    "ANALISTA_POSITIVO": [
        "upgrade",
        "raises price target",
        "price target raised",
        "maintains buy",
        "maintains outperform",
        "initiates with buy",
        "initiates coverage with buy"
    ],

    "CRECIMIENTO": [
        "record revenue",
        "record sales",
        "record earnings",
        "revenue growth",
        "sales growth"
    ]
}


# ============================================================
# EVIDENCIAS NEGATIVAS
# ============================================================

EVIDENCIAS_NEGATIVAS = {

    "RESULTADOS_INFERIORES": [
        "misses estimate",
        "misses estimates",
        "miss estimate",
        "miss estimates",
        "below estimate",
        "below estimates",
        "falls short of estimate",
        "falls short of estimates"
    ],

    "GUIDANCE_A_LA_BAJA": [
        "cuts guidance",
        "lowers guidance",
        "reduces forecast",
        "weak outlook",
        "lowers outlook",
        "cuts forecast"
    ],

    "DILUCION": [
        "public offering",
        "secondary offering",
        "stock offering",
        "share offering",
        "registered direct offering",
        "at-the-market offering",
        "atm offering"
    ],

    "REGULATORIO_NEGATIVO": [
        "fda rejection",
        "fda rejects",
        "clinical hold",
        "sec investigation",
        "doj investigation",
        "regulatory probe"
    ],

    "ENSAYO_NEGATIVO": [
        "trial failure",
        "failed trial",
        "missed endpoint",
        "fails primary endpoint",
        "did not meet primary endpoint"
    ],

    "LEGAL": [
        "lawsuit",
        "litigation",
        "class action",
        "subpoena"
    ],

    "ANALISTA_NEGATIVO": [
        "downgrade",
        "price target cut",
        "cuts price target",
        "sell rating",
        "underperform"
    ],

    "DESPIDOS": [
        "layoffs",
        "layoff",
        "job cuts",
        "workforce reduction"
    ]
}


# ============================================================
# RIESGOS GENERALES
#
# Se usan para estimar riesgo narrativo.
# ============================================================

RIESGOS = {

    "RESULTADOS_DEBILES": [
        "misses estimate",
        "misses estimates",
        "earnings miss",
        "revenue miss",
        "sales miss",
        "profit warning"
    ],

    "GUIDANCE_NEGATIVO": [
        "cuts guidance",
        "lowers guidance",
        "weak outlook",
        "lower forecast",
        "reduces forecast"
    ],

    "DILUCION": [
        "public offering",
        "stock offering",
        "share offering",
        "secondary offering",
        "registered direct offering",
        "at-the-market offering",
        "atm offering"
    ],

    "REGULATORIO": [
        "investigation",
        "regulatory probe",
        "sec investigation",
        "doj investigation",
        "subpoena",
        "regulatory action"
    ],

    "LEGAL": [
        "lawsuit",
        "litigation",
        "class action",
        "legal action"
    ],

    "FDA_NEGATIVO": [
        "fda rejection",
        "fda rejects",
        "clinical hold",
        "trial failure",
        "failed trial",
        "missed endpoint"
    ],

    "DOWNGRADE": [
        "downgrade",
        "sell rating",
        "underperform",
        "price target cut"
    ],

    "DESPIDOS": [
        "layoffs",
        "layoff",
        "job cuts",
        "workforce reduction"
    ]
}


# ============================================================
# FUERZA DE CATALIZADORES
# ============================================================

PESO_CATALIZADOR = {

    "APROBACION": 3,
    "ENSAYO_POSITIVO": 3,

    "RESULTADOS_SUPERIORES": 2,
    "GUIDANCE_AL_ALZA": 3,
    "CONTRATO_POSITIVO": 2,

    "CRECIMIENTO": 2,

    "ANALISTA_POSITIVO": 1
}


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(
    texto
):

    if not texto:
        return ""

    texto = str(
        texto
    ).lower()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# DESCARGAR NOTICIAS
# ============================================================

def obtener_noticias(
    symbol,
    dias=DIAS_NOTICIAS,
    limite=MAX_NOTICIAS
):
    """
    Descarga noticias recientes desde Alpaca.
    """

    ahora = datetime.now(
        timezone.utc
    )

    inicio = (
        ahora
        - timedelta(
            days=dias
        )
    )


    parametros = {

        "symbols":
            symbol.upper(),

        "start":
            inicio.isoformat(),

        "end":
            ahora.isoformat(),

        "sort":
            "desc",

        "limit":
            min(
                limite,
                50
            ),

        "include_content":
            "false"
    }


    response = requests.get(

        NEWS_URL,

        headers=HEADERS,

        params=parametros,

        timeout=30
    )


    response.raise_for_status()


    datos = response.json()


    return datos.get(
        "news",
        []
    )


# ============================================================
# DETECTAR CATEGORÍAS
# ============================================================

def detectar_categorias(
    texto,
    diccionario
):

    encontradas = []


    for categoria, palabras in (
        diccionario.items()
    ):

        for palabra in palabras:

            if palabra in texto:

                encontradas.append(
                    categoria
                )

                break


    return encontradas

def detectar_evidencias_resultados(
    texto
):
    """
    Detecta beats/misses aunque existan cifras,
    monedas o palabras intermedias.

    Ejemplos:
        "EPS $2.52 Misses $2.92 Estimate"
        "Sales $405M Beat $327M Estimate"
    """

    positivas = []
    negativas = []


    patrones_positivos = [

        r"\bbeat(?:s)?\b.{0,40}\bestimate(?:s)?\b",

        r"\btop(?:s|ped)?\b.{0,40}\bestimate(?:s)?\b",

        r"\bexceed(?:s|ed)?\b.{0,40}\bestimate(?:s)?\b",

        r"\babove\b.{0,40}\bestimate(?:s)?\b"
    ]


    patrones_negativos = [

        r"\bmiss(?:es|ed)?\b.{0,40}\bestimate(?:s)?\b",

        r"\bbelow\b.{0,40}\bestimate(?:s)?\b",

        r"\bfalls? short\b.{0,40}\bestimate(?:s)?\b"
    ]


    for patron in patrones_positivos:

        if re.search(
            patron,
            texto,
            flags=re.IGNORECASE
        ):

            positivas.append(
                "RESULTADOS_SUPERIORES"
            )

            break


    for patron in patrones_negativos:

        if re.search(
            patron,
            texto,
            flags=re.IGNORECASE
        ):

            negativas.append(
                "RESULTADOS_INFERIORES"
            )

            break


    return (
        positivas,
        negativas
    )
# ============================================================
# ANALIZAR NOTICIAS
# ============================================================

def analizar_noticias(
    noticias
):

    catalizadores = set()

    riesgos = set()

    evidencias_positivas = set()

    evidencias_negativas = set()

    noticias_analizadas = []


    for noticia in noticias:

        headline = (
            noticia.get(
                "headline"
            )
            or ""
        )

        summary = (
            noticia.get(
                "summary"
            )
            or ""
        )


        texto_completo = (
            normalizar_texto(
                headline
                + " "
                + summary
            )
        )


        # ====================================================
        # TIPO DE NOTICIA
        # ====================================================

        cats = detectar_categorias(

            texto_completo,

            CATALIZADORES
        )


        # ====================================================
        # RIESGOS
        # ====================================================

        risks = detectar_categorias(

            texto_completo,

            RIESGOS
        )


        # ====================================================
        # EVIDENCIAS
        # ====================================================

        positivas = detectar_categorias(

            texto_completo,

            EVIDENCIAS_POSITIVAS
        )


        negativas = detectar_categorias(

            texto_completo,

            EVIDENCIAS_NEGATIVAS
        )

        positivas_resultados, negativas_resultados = (
            detectar_evidencias_resultados(
                texto_completo
            )
        )


        positivas = list(
            set(
                positivas
                + positivas_resultados
            )
        )


        negativas = list(
            set(
                negativas
                + negativas_resultados
            )
        )
        if (
            "RESULTADOS_INFERIORES"
            in negativas_resultados
        ):

            if (
                "RESULTADOS_DEBILES"
                not in risks
            ):

                risks.append(
                    "RESULTADOS_DEBILES"
                )
        catalizadores.update(
            cats
        )

        riesgos.update(
            risks
        )

        evidencias_positivas.update(
            positivas
        )

        evidencias_negativas.update(
            negativas
        )


        # ====================================================
        # CONTEXTO INDIVIDUAL DE LA NOTICIA
        # ====================================================

        if positivas and negativas:

            contexto_noticia = (
                "MIXTO"
            )

        elif positivas:

            contexto_noticia = (
                "POSITIVO"
            )

        elif negativas:

            contexto_noticia = (
                "NEGATIVO"
            )

        else:

            contexto_noticia = (
                "NEUTRO"
            )


        noticias_analizadas.append(
            {

                "headline":
                    headline,

                "summary":
                    summary,

                "created_at":
                    noticia.get(
                        "created_at"
                    ),

                "source":
                    noticia.get(
                        "source"
                    ),

                "url":
                    noticia.get(
                        "url"
                    ),

                "catalizadores":
                    cats,

                "riesgos":
                    risks,

                "evidencias_positivas":
                    positivas,

                "evidencias_negativas":
                    negativas,

                "contexto":
                    contexto_noticia
            }
        )


    return {

        "catalizadores":
            sorted(
                catalizadores
            ),

        "riesgos":
            sorted(
                riesgos
            ),

        "evidencias_positivas":
            sorted(
                evidencias_positivas
            ),

        "evidencias_negativas":
            sorted(
                evidencias_negativas
            ),

        "noticias":
            noticias_analizadas
    }


# ============================================================
# FUERZA DEL CATALIZADOR
# ============================================================

def calcular_fuerza_catalizador(
    evidencias_positivas
):
    """
    Clasifica la fuerza del catalizador positivo.

    ALTA:
        aprobación, guidance al alza, etc.

    MEDIA:
        resultados superiores, contratos, crecimiento.

    BAJA:
        analistas / price target.

    NINGUNA:
        no se identifica evidencia positiva.
    """

    if not evidencias_positivas:

        return "NINGUNA"


    peso_maximo = max(

        PESO_CATALIZADOR.get(
            evidencia,
            1
        )

        for evidencia in evidencias_positivas
    )


    if peso_maximo >= 3:

        return "ALTA"

    if peso_maximo >= 2:

        return "MEDIA"

    return "BAJA"


# ============================================================
# CLASIFICAR CONTEXTO
# ============================================================

def clasificar_contexto(
    analisis,
    prioridad_tecnica=None
):

    noticias = analisis[
        "noticias"
    ]

    catalizadores = analisis[
        "catalizadores"
    ]

    riesgos = analisis[
        "riesgos"
    ]

    positivas = analisis[
        "evidencias_positivas"
    ]

    negativas = analisis[
        "evidencias_negativas"
    ]


    # ========================================================
    # SIN NOTICIAS
    # ========================================================

    if not noticias:

        return {

            "contexto":
                "SIN NOTICIAS",

            "movimiento_explicado":
                "NO",

            "fuerza_catalizador":
                "NINGUNA",

            "riesgo_narrativo":
                "MEDIO",

            "lectura":
                (
                    "No se han encontrado noticias recientes "
                    "en la fuente consultada. La fortaleza "
                    "técnica no tiene un catalizador visible "
                    "identificado por esta capa."
                )
        }


    # ========================================================
    # CONTEXTO GENERAL
    # ========================================================

    if (
        positivas
        and negativas
    ):

        contexto = "MIXTO"

    elif positivas:

        contexto = "POSITIVO"

    elif negativas:

        contexto = "NEGATIVO"

    elif riesgos:

        contexto = "NEGATIVO"

    else:

        contexto = "NEUTRO"


    # ========================================================
    # MOVIMIENTO EXPLICADO
    # ========================================================

    if (
        positivas
        and not negativas
    ):

        movimiento_explicado = (
            "SÍ"
        )

    elif (
        positivas
        and negativas
    ):

        movimiento_explicado = (
            "PARCIALMENTE"
        )

    elif catalizadores:

        movimiento_explicado = (
            "POSIBLEMENTE"
        )

    else:

        movimiento_explicado = (
            "NO"
        )


    # ========================================================
    # FUERZA DEL CATALIZADOR
    # ========================================================

    fuerza_catalizador = (
        calcular_fuerza_catalizador(
            positivas
        )
    )


    # ========================================================
    # RIESGO NARRATIVO
    # ========================================================

    if len(
        riesgos
    ) >= 2:

        riesgo_narrativo = (
            "ALTO"
        )

    elif (
        negativas
        and not positivas
    ):

        riesgo_narrativo = (
            "ALTO"
        )

    elif (
        negativas
        or riesgos
    ):

        riesgo_narrativo = (
            "MEDIO"
        )

    elif (
        prioridad_tecnica
        in [
            "A+",
            "A"
        ]
        and not positivas
    ):

        riesgo_narrativo = (
            "MEDIO"
        )

    else:

        riesgo_narrativo = (
            "BAJO"
        )


    # ========================================================
    # LECTURA
    # ========================================================

    if (
        positivas
        and not negativas
    ):

        lectura = (
            "La fortaleza técnica coincide con evidencias "
            "positivas identificables en noticias recientes. "
            "El movimiento dispone de un catalizador visible, "
            "aunque esto no implica que la acción esté barata "
            "ni garantiza continuidad de la tendencia."
        )


    elif (
        positivas
        and negativas
    ):

        lectura = (
            "Las noticias recientes contienen señales positivas "
            "y negativas. Existe contexto que puede explicar "
            "parte del movimiento, pero la lectura es mixta y "
            "requiere revisar los detalles antes de extraer "
            "conclusiones."
        )


    elif (
        negativas
        and not positivas
    ):

        lectura = (
            "Las noticias recientes contienen evidencias "
            "negativas y no se identifica un catalizador "
            "positivo claro. La fortaleza técnica debe "
            "interpretarse con especial cautela."
        )


    elif catalizadores:

        lectura = (
            "Existen noticias relacionadas con eventos "
            "empresariales recientes, pero esta capa no puede "
            "determinar todavía que sean claramente positivas "
            "o negativas. El movimiento podría estar relacionado "
            "con ellas, pero necesita análisis adicional."
        )


    else:

        lectura = (
            "Existen noticias recientes, pero esta capa no "
            "identifica un catalizador empresarial suficientemente "
            "claro que explique la fortaleza técnica."
        )


    return {

        "contexto":
            contexto,

        "movimiento_explicado":
            movimiento_explicado,

        "fuerza_catalizador":
            fuerza_catalizador,

        "riesgo_narrativo":
            riesgo_narrativo,

        "lectura":
            lectura
    }


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def analizar_contexto_noticias(
    symbol,
    prioridad_tecnica=None,
    dias=DIAS_NOTICIAS,
    limite=MAX_NOTICIAS
):

    noticias = obtener_noticias(

        symbol,

        dias=dias,

        limite=limite
    )


    analisis = analizar_noticias(
        noticias
    )


    contexto = clasificar_contexto(

        analisis,

        prioridad_tecnica=
            prioridad_tecnica
    )


    return {

        "symbol":
            symbol.upper(),

        "num_noticias":
            len(
                noticias
            ),

        "catalizadores":
            analisis[
                "catalizadores"
            ],

        "evidencias_positivas":
            analisis[
                "evidencias_positivas"
            ],

        "evidencias_negativas":
            analisis[
                "evidencias_negativas"
            ],

        "riesgos":
            analisis[
                "riesgos"
            ],

        "contexto":
            contexto[
                "contexto"
            ],

        "movimiento_explicado":
            contexto[
                "movimiento_explicado"
            ],

        "fuerza_catalizador":
            contexto[
                "fuerza_catalizador"
            ],

        "riesgo_narrativo":
            contexto[
                "riesgo_narrativo"
            ],

        "lectura":
            contexto[
                "lectura"
            ],

        "noticias":
            analisis[
                "noticias"
            ]
    }