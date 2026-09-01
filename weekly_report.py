from datetime import datetime
import re

import pandas as pd

from analysis.analyst_revisions import (
    calcular_revisiones_symbols
)

from database.db import (
    # ========================================================
    # CORE
    # ========================================================
    inicializar_db,
    inicializar_tabla_eventos,

    asegurar_columna_market_date,
    asegurar_columnas_sectoriales,
    asegurar_columnas_score_v3,
    asegurar_columnas_v4_reversal,
    asegurar_columnas_clasificacion,

    obtener_scan_times,
    obtener_scan_por_fecha,
    obtener_eventos_recientes,

    # ========================================================
    # ANALYST CONSENSUS
    # ========================================================
    obtener_ultimos_analyst_snapshots,

    # ========================================================
    # FUNDAMENTALS
    # ========================================================
    obtener_ultimas_clasificaciones_fundamentales,

    # ========================================================
    # PAPER
    # ========================================================
    inicializar_tablas_paper,
    inicializar_tablas_paper_portfolio,
    obtener_resultados_paper,
    obtener_resumen_paper,
    obtener_resumen_paper_portfolios,

    # ========================================================
    # NEWS
    # ========================================================
    inicializar_tablas_news,
    obtener_news_context_ultimo_scan,
    obtener_news_items
)

from notifications.emailer import (
    enviar_email
)


# ============================================================
# CONFIGURACION
# ============================================================

NUM_SCANS = 7

TOP_COMPLETO = 20

TOP_PERSISTENTES = 10

TOP_MEJORANDO = 10

MAX_EVENTOS = 20

TOP_NEWS = 15


# ============================================================
# HELPERS GENERALES
# ============================================================

def texto(
    valor,
    defecto="N/A"
):

    if valor is None:
        return defecto

    valor = str(
        valor
    ).strip()

    return (
        valor
        if valor
        else defecto
    )


def generar_lineas_paper_portfolio_live(cartera):
    """Genera el resumen visual de una cartera paper continua."""

    equity = cartera.get("equity") or {}
    nombre = "Momentum V4" if cartera.get("strategy") == "MOMENTUM" else "Reversal V1"
    retorno = numero(equity.get("return_pct"))
    spy_retorno = numero(equity.get("spy_return_pct"))
    abiertas = []
    for posicion in cartera.get("abiertas", []):
        capital = numero(posicion.get("capital_allocated"))
        valor_actual = numero(posicion.get("shares")) * numero(posicion.get("last_price"))
        retorno_abierto = (
            (valor_actual / capital - 1) * 100
            if capital > 0 else numero(posicion.get("return_pct"))
        )
        abiertas.append((posicion, capital, valor_actual, retorno_abierto))

    pnl_no_realizado = sum(valor - capital for _, capital, valor, _ in abiertas)
    capital_invertido = sum(capital for _, capital, _, _ in abiertas)

    def pnl_moneda(valor, mostrar_mas=False):
        valor = numero(valor)
        if valor < 0:
            return f"-${abs(valor):,.2f}"
        prefijo = "+" if mostrar_mas and valor > 0 else ""
        return f"{prefijo}${valor:,.2f}"

    mejores = sorted(abiertas, key=lambda item: item[3], reverse=True)[:3]
    simbolos_mejores = {texto(item[0].get("symbol")) for item in mejores}
    peores = [
        item for item in sorted(abiertas, key=lambda item: item[3])
        if texto(item[0].get("symbol")) not in simbolos_mejores
    ][:3]
    cierres = sorted(
        cartera.get("ultimos_cierres", []),
        key=lambda item: texto(item.get("actual_exit_date"), ""),
        reverse=True
    )[:5]

    lineas = [
        "",
        f"{nombre}:",
        (
            f"Capital ${numero(equity.get('equity'), cartera.get('current_cash')):,.2f} | "
            f"{retorno:+.2f}% | SPY {spy_retorno:+.2f}% | "
            f"Exc {retorno - spy_retorno:+.2f}pp | "
            f"DD {numero(cartera.get('max_drawdown_pct')):+.2f}%"
        ),
        (
            f"Cash: ${numero(cartera.get('current_cash')):,.2f} | "
            f"Invertido: ${capital_invertido:,.2f} | "
            f"Exposicion: {numero(equity.get('exposure_pct')):.1f}%"
        ),
        (
            f"P&L realizado: {pnl_moneda(cartera.get('pnl_realizado'))} | "
            f"P&L no realizado: {pnl_moneda(pnl_no_realizado)}"
        ),
        f"Abiertas: {len(abiertas)} | Cerradas: {entero(cartera.get('cerradas'))}"
    ]

    for titulo, posiciones in (("Mejores abiertas:", mejores), ("Peores abiertas:", peores)):
        if posiciones:
            lineas.append(titulo)
            for posicion, capital, _, retorno_abierto in posiciones:
                lineas.append(
                    f"  {texto(posicion.get('symbol')):<7} | "
                    f"{retorno_abierto:+.1f}% | ${capital:,.0f}"
                )

    if cierres:
        lineas.append("Ultimos cierres:")
        for posicion in cierres:
            lineas.append(
                f"  {texto(posicion.get('symbol')):<7} | "
                f"{numero(posicion.get('return_pct')):+.1f}% | "
                f"{texto(posicion.get('exit_reason'))} | "
                f"{pnl_moneda(posicion.get('pnl'), mostrar_mas=True)}"
            )
    return lineas


def numero(
    valor,
    defecto=0.0
):

    if valor is None:
        return defecto

    try:

        return float(
            valor
        )

    except (
        TypeError,
        ValueError
    ):

        return defecto


def entero(
    valor,
    defecto=0
):

    if valor is None:
        return defecto

    try:

        return int(
            valor
        )

    except (
        TypeError,
        ValueError
    ):

        return defecto


def formatear_alertas(
    alertas
):

    if not alertas:
        return "NINGUNA"

    alertas = str(
        alertas
    ).strip()

    if not alertas:
        return "NINGUNA"

    return alertas.replace(
        "|",
        ", "
    )


def formatear_lista_db(
    valor,
    defecto="NINGUNA"
):
    """
    Convierte:
        RESULTADOS|GUIDANCE

    en:
        RESULTADOS, GUIDANCE
    """

    if not valor:
        return defecto

    valor = str(
        valor
    ).strip()

    if not valor:
        return defecto

    return valor.replace(
        "|",
        ", "
    )


def prioridad_orden(
    prioridad
):

    return {
        "A+": 0,
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4
    }.get(
        prioridad,
        99
    )


def obtener_version_scan(
    scan
):

    versiones = {

        activo.get(
            "score_version"
        )

        for activo in scan

        if activo.get(
            "score_version"
        )
    }

    if len(
        versiones
    ) == 1:

        return next(
            iter(
                versiones
            )
        )

    if not versiones:

        return None

    return "MIXED"


def safe_pp(
    valor
):

    if valor is None:
        return "N/A"

    return (
        f"{numero(valor):+.1f}pp"
    )


def safe_precio(
    valor
):

    if valor is None:
        return "N/A"

    return (
        f"${numero(valor):.2f}"
    )


def safe_rsi(
    valor
):

    if valor is None:
        return "N/A"

    return (
        f"{numero(valor):.1f}"
    )


def safe_pct(
    valor
):

    if valor is None:
        return "N/A"

    return (
        f"{numero(valor):+.2f}%"
    )


def decimal_consenso(
    valor
):
    if valor is None:
        return "N/A"

    return f"{numero(valor):+.2f}"


# ============================================================
# FUNDAMENTAL HELPERS
# ============================================================

def construir_mapa_fundamentales(
    fundamentales
):

    return {

        fila[
            "symbol"
        ]:
            fila

        for fila in fundamentales
    }


def lista_db_a_texto(
    valor,
    defecto="NINGUNA"
):
    """
    Convierte listas persistidas como:

        Balance solido|Generacion de caja fuerte

    en:

        Balance solido, Generacion de caja fuerte
    """

    if not valor:

        return defecto

    valor = str(
        valor
    ).strip()

    if not valor:

        return defecto

    return valor.replace(
        "|",
        ", "
    )


def formatear_ratio(
    valor
):

    if valor is None:

        return "N/A"

    try:

        return (
            f"{float(valor):.2f}x"
        )

    except (
        TypeError,
        ValueError
    ):

        return "N/A"


def formatear_pct_fund(
    valor
):

    if valor is None:

        return "N/A"

    try:

        return (
            f"{float(valor):+.2f}%"
        )

    except (
        TypeError,
        ValueError
    ):

        return "N/A"


def formatear_dinero_fund(
    valor
):

    if valor is None:

        return "N/A"

    try:

        valor = float(
            valor
        )

    except (
        TypeError,
        ValueError
    ):

        return "N/A"

    absoluto = abs(
        valor
    )

    if absoluto >= 1_000_000_000:

        return (
            f"${valor / 1_000_000_000:.2f}B"
        )

    if absoluto >= 1_000_000:

        return (
            f"${valor / 1_000_000:.2f}M"
        )

    if absoluto >= 1_000:

        return (
            f"${valor / 1_000:.2f}K"
        )

    return (
        f"${valor:,.2f}"
    )


def generar_bloque_fundamental(
    symbol,
    mapa_fundamentales
):
    """
    Genera la seccion fundamental humana
    de una empresa.
    """

    fundamental = mapa_fundamentales.get(
        symbol
    )

    if fundamental is None:

        return [
            (
                "      Fundamentales: "
                "SIN ANALISIS DISPONIBLE"
            )
        ]

    lineas = []

    # ========================================================
    # RESUMEN
    # ========================================================

    lineas.append(
        (
            "      Fundamental: "
            f"{entero(fundamental.get('score_fundamental'))}/100 | "
            f"{texto(fundamental.get('calidad_fundamental'))} | "
            f"Modelo: {texto(fundamental.get('model'))}"
        )
    )

    lineas.append(
        (
            "      Crecimiento: "
            f"{texto(fundamental.get('crecimiento'))} | "
            "Rentabilidad: "
            f"{texto(fundamental.get('rentabilidad'))} | "
            "Balance: "
            f"{texto(fundamental.get('balance'))}"
        )
    )

    lineas.append(
        (
            "      Cash Flow: "
            f"{texto(fundamental.get('cash_flow'))} | "
            "Valoracion: "
            f"{texto(fundamental.get('valoracion'))}"
        )
    )

    # ========================================================
    # RATIOS SEGUN MODELO
    # ========================================================

    modelo = fundamental.get(
        "model"
    )

    if modelo in [
        "BANK",
        "FINANCIAL"
    ]:

        lineas.append(
            (
                "      Ratios: "
                f"P/E {formatear_ratio(fundamental.get('pe_ttm'))} | "
                f"P/B {formatear_ratio(fundamental.get('pb'))} | "
                f"ROE {formatear_pct_fund(fundamental.get('roe'))}"
            )
        )

    elif modelo == "BIOTECH_PRE_REVENUE":

        lineas.append(
            (
                "      Ratios tradicionales: "
                "NO APLICABLES / LIMITADOS"
            )
        )

        lineas.append(
            (
                "      Caja: "
                f"{formatear_dinero_fund(fundamental.get('cash'))} | "
                "Market Cap: "
                f"{formatear_dinero_fund(fundamental.get('market_cap'))}"
            )
        )

    elif modelo == "REIT":

        lineas.append(
            (
                "      Valoracion REIT: "
                "PENDIENTE FFO/AFFO"
            )
        )

    else:

        lineas.append(
            (
                "      Ratios: "
                f"P/E {formatear_ratio(fundamental.get('pe_ttm'))} | "
                f"P/S {formatear_ratio(fundamental.get('ps_ttm'))} | "
                f"P/B {formatear_ratio(fundamental.get('pb'))} | "
                f"FCF Yield "
                f"{formatear_pct_fund(fundamental.get('fcf_yield'))}"
            )
        )

        lineas.append(
            (
                "      TTM: "
                "Revenue "
                f"{formatear_dinero_fund(fundamental.get('revenue_ttm'))} | "
                "Net Income "
                f"{formatear_dinero_fund(fundamental.get('net_income_ttm'))} | "
                "FCF "
                f"{formatear_dinero_fund(fundamental.get('fcf_ttm'))}"
            )
        )

    # ========================================================
    # FORTALEZAS
    # ========================================================

    lineas.append(
        (
            "      Fortalezas fundamentales: "
            f"{lista_db_a_texto(fundamental.get('fortalezas'))}"
        )
    )

    # ========================================================
    # DEBILIDADES
    # ========================================================

    lineas.append(
        (
            "      Debilidades fundamentales: "
            f"{lista_db_a_texto(fundamental.get('debilidades'))}"
        )
    )

    # ========================================================
    # ALERTAS
    # ========================================================

    lineas.append(
        (
            "      Alertas fundamentales: "
            f"{lista_db_a_texto(fundamental.get('alertas'))}"
        )
    )

    lectura = fundamental.get(
        "lectura"
    )

    if lectura:

        lineas.append(
            (
                "      Lectura fundamental: "
                f"{lectura}"
            )
        )

    return lineas


# ============================================================
# LECTURA HUMANA DE PRIORIDAD
# ============================================================

def generar_lectura_prioridad(
    activo
):
    """
    Explicacion prudente de la prioridad tecnica.

    No interpreta A+ como recomendacion de compra.
    """

    prioridad = texto(
        activo.get(
            "prioridad_estudio"
        )
    )

    alertas = formatear_alertas(
        activo.get(
            "alertas_estudio"
        )
    )

    if prioridad == "A+":

        if alertas != "NINGUNA":

            return (
                "Configuracion tecnica especialmente solida segun el modelo, "
                "aunque presenta factores tecnicos que conviene revisar "
                f"antes de profundizar: {alertas}. "
                "Prioridad maxima para analisis adicional."
            )

        return (
            "Configuracion tecnica especialmente solida segun el modelo. "
            "No se detectan alertas tecnicas relevantes entre las metricas "
            "analizadas actualmente. Prioridad maxima para analisis adicional."
        )

    if prioridad == "A":

        if alertas != "NINGUNA":

            return (
                "Configuracion tecnica solida y de alta prioridad, "
                "aunque presenta factores tecnicos que conviene revisar "
                f"antes de profundizar: {alertas}."
            )

        return (
            "Configuracion tecnica solida. Presenta una buena combinacion "
            "de tendencia, fortaleza relativa y control de riesgo. "
            "Merece analisis adicional antes de valorar una posible inversion."
        )

    if prioridad == "B":

        if alertas != "NINGUNA":

            return (
                "Configuracion tecnicamente interesante, pero presenta "
                "factores que requieren una revision mas detallada: "
                f"{alertas}."
            )

        return (
            "Configuracion tecnicamente interesante, aunque todavia "
            "presenta algun desequilibrio frente a los candidatos "
            "de mayor prioridad."
        )

    if prioridad == "C":

        return (
            "Configuracion mixta. Existen senales tecnicas positivas, "
            "pero todavia no destaca lo suficiente para considerarla "
            "una prioridad de analisis."
        )

    if prioridad == "D":

        return (
            "Configuracion de baja prioridad segun las metricas tecnicas "
            "analizadas actualmente."
        )

    return (
        "Todavia no existe suficiente informacion tecnica clasificada "
        "para generar una lectura completa."
    )


# ============================================================
# NEWS HELPERS
# ============================================================

def construir_mapa_news(
    news_context
):

    return {

        fila[
            "symbol"
        ]:
            fila

        for fila in news_context
    }


def generar_bloque_news(
    symbol,
    mapa_news
):
    """
    Devuelve lineas de contexto de noticias
    para incluir dentro de una ficha tecnica.
    """

    contexto = mapa_news.get(
        symbol
    )

    if contexto is None:

        return [
            (
                "      Noticias: "
                "SIN ANALISIS DISPONIBLE"
            )
        ]

    lineas = []

    lineas.append(
        (
            "      Noticias: "
            f"{texto(contexto.get('contexto'))} | "
            "Movimiento: "
            f"{texto(contexto.get('movimiento_explicado'))} | "
            "Catalizador: "
            f"{texto(contexto.get('fuerza_catalizador'))} | "
            "Riesgo narrativo: "
            f"{texto(contexto.get('riesgo_narrativo'))}"
        )
    )

    lineas.append(
        (
            "      Catalizadores: "
            f"{formatear_lista_db(contexto.get('catalizadores'))}"
        )
    )

    positivas = formatear_lista_db(
        contexto.get(
            "evidencias_positivas"
        )
    )

    negativas = formatear_lista_db(
        contexto.get(
            "evidencias_negativas"
        )
    )

    riesgos = formatear_lista_db(
        contexto.get(
            "riesgos"
        )
    )

    lineas.append(
        (
            "      Evidencias +: "
            f"{positivas}"
        )
    )

    lineas.append(
        (
            "      Evidencias -: "
            f"{negativas}"
        )
    )

    lineas.append(
        (
            "      Riesgos noticias: "
            f"{riesgos}"
        )
    )

    lectura = contexto.get(
        "lectura"
    )

    if lectura:

        lineas.append(
            (
                "      Lectura noticias: "
                f"{lectura}"
            )
        )

    # ========================================================
    # ULTIMA NOTICIA
    # ========================================================

    try:

        items = obtener_news_items(
            contexto[
                "id"
            ]
        )

    except Exception:

        items = []

    if items:

        ultima = items[0]

        lineas.append(
            (
                "      Ultima noticia: "
                f"{texto(ultima.get('headline'))}"
            )
        )

    return lineas


# ============================================================
# FICHA COMPLETA
# ============================================================

def generar_ficha_activo(
    activo,
    posicion=None,
    mapa_news=None,
    mapa_fundamentales=None
):

    if mapa_news is None:

        mapa_news = {}

    if mapa_fundamentales is None:

        mapa_fundamentales = {}

    prefijo = ""

    if posicion is not None:

        prefijo = (
            f"{posicion:>2}. "
        )

    symbol = texto(
        activo.get(
            "symbol"
        )
    )

    nombre = texto(
        activo.get(
            "nombre"
        ),
        symbol
    )

    score = entero(
        activo.get(
            "score"
        )
    )

    tendencia = texto(
        activo.get(
            "tendencia"
        )
    )

    prioridad = texto(
        activo.get(
            "prioridad_estudio"
        )
    )

    alertas = formatear_alertas(
        activo.get(
            "alertas_estudio"
        )
    )

    lineas = []

    # ========================================================
    # CABECERA
    # ========================================================

    lineas.append(
        (
            f"{prefijo}"
            f"{symbol:<7} | "
            f"{score:>3}/100 | "
            f"{tendencia:<15} | "
            f"RSI {safe_rsi(activo.get('rsi'))} | "
            f"RS20 {safe_pp(activo.get('fuerza_20d'))} | "
            f"RS60 {safe_pp(activo.get('fuerza_60d'))} | "
            f"{safe_precio(activo.get('precio'))} | "
            f"{nombre}"
        )
    )

    # ========================================================
    # SECTOR
    # ========================================================

    lineas.append(
        (
            "      Sector: "
            f"{texto(activo.get('sector'), 'Unknown')} "
            f"({texto(activo.get('sector_benchmark'))}) | "
            f"S20 {safe_pp(activo.get('fuerza_sector_20d'))} | "
            f"S60 {safe_pp(activo.get('fuerza_sector_60d'))}"
        )
    )

    # ========================================================
    # SCORE
    # ========================================================

    if activo.get(
        "score_version"
    ) == "v4":

        lineas.append(
            (
                "      Score v4: "
                f"T {entero(activo.get('score_tendencia'))}/20 | "
                f"M {entero(activo.get('score_momentum'))}/20 | "
                f"SPY {entero(activo.get('score_fuerza'))}/20 | "
                f"SEC {entero(activo.get('score_sector'))}/10 | "
                f"CONT {entero(activo.get('score_continuacion'))}/20 | "
                f"V {entero(activo.get('score_volumen'))}/10 | "
                "Riesgo overlay: "
                f"{texto(activo.get('riesgo_clasificacion'))}"
            )
        )

    else:

        lineas.append(
            (
                "      Score "
                f"{texto(activo.get('score_version'))}: "
                f"T {entero(activo.get('score_tendencia'))}/25 | "
                f"M {entero(activo.get('score_momentum'))}/15 | "
                f"SPY {entero(activo.get('score_fuerza'))}/20 | "
                f"SEC {entero(activo.get('score_sector'))}/15 | "
                f"R {entero(activo.get('score_riesgo'))}/15 | "
                f"V {entero(activo.get('score_volumen'))}/10 | "
                f"P -{entero(activo.get('penalizacion_relativa'))}"
            )
        )

    # ========================================================
    # PERFIL HUMANO
    # ========================================================

    lineas.append(
        (
            "      Perfil: "
            f"{texto(activo.get('perfil'))} | "
            "Calidad: "
            f"{texto(activo.get('calidad'))} | "
            "Mercado: "
            f"{texto(activo.get('fortaleza_mercado'))} | "
            "Sector: "
            f"{texto(activo.get('fortaleza_sector'))} | "
            "Riesgo: "
            f"{texto(activo.get('riesgo_clasificacion'))} | "
            "Volumen: "
            f"{texto(activo.get('volumen_clasificacion'))}"
        )
    )

    # ========================================================
    # PRIORIDAD
    # ========================================================

    lineas.append(
        (
            "      Prioridad: "
            f"{prioridad} | "
            f"Alertas: {alertas}"
        )
    )

    lectura = generar_lectura_prioridad(
        activo
    )

    lineas.append(
        (
            "      Lectura tecnica: "
            f"{lectura}"
        )
    )

    # ========================================================
    # NEWS CONTEXT
    #
    # News solo se analiza actualmente para A+/A.
    # ========================================================

    if prioridad in [
        "A+",
        "A"
    ]:

        lineas.extend(
            generar_bloque_news(
                symbol,
                mapa_news
            )
        )

    # ========================================================
    # FUNDAMENTALES
    #
    # Se analizan A+/A/B.
    # ========================================================

    if prioridad in [
        "A+",
        "A",
        "B"
    ]:

        lineas.extend(
            generar_bloque_fundamental(
                symbol,
                mapa_fundamentales
            )
        )

    return "\n".join(
        lineas
    )


# ============================================================
# PAPER PERFORMANCE
# ============================================================

def resumir_paper(
    resultados
):

    if not resultados:

        return None

    df = pd.DataFrame(
        resultados
    )

    return {

        "casos":
            len(df),

        "retorno_medio":
            df[
                "retorno"
            ].mean(),

        "retorno_mediana":
            df[
                "retorno"
            ].median(),

        "spy_medio":
            df[
                "retorno_spy"
            ].mean(),

        "exceso_medio":
            df[
                "exceso_spy"
            ].mean(),

        "bate_spy":
            (
                df[
                    "exceso_spy"
                ] > 0
            ).mean()
            * 100,

        "positivas":
            (
                df[
                    "retorno"
                ] > 0
            ).mean()
            * 100,

        "drawdown_medio":
            df[
                "max_drawdown"
            ].mean(),

        "peor_drawdown":
            df[
                "max_drawdown"
            ].min(),

        "mejor":
            df[
                "retorno"
            ].max(),

        "peor":
            df[
                "retorno"
            ].min()
    }


def generar_lineas_performance_paper(
    resultados,
    prioridades=None
):

    lineas = []

    if prioridades is None:

        prioridades = [
            "A+",
            "A",
            "B"
        ]

    horizontes = [
        5,
        20,
        60
    ]

    for prioridad in prioridades:

        for horizonte in horizontes:

            filtrados = [

                fila

                for fila in resultados

                if (
                    fila.get(
                        "prioridad"
                    ) == prioridad

                    and

                    entero(
                        fila.get(
                            "horizonte"
                        )
                    ) == horizonte
                )
            ]

            resumen = resumir_paper(
                filtrados
            )

            if resumen is None:

                lineas.append(
                    (
                        f"{prioridad:<2} | "
                        f"{horizonte:>2}D | "
                        "PENDIENTE"
                    )
                )

                continue

            lineas.append(
                (
                    f"{prioridad:<2} | "
                    f"{horizonte:>2}D | "
                    f"n={resumen['casos']:<4} | "
                    f"Ret {resumen['retorno_medio']:+.2f}% | "
                    f"SPY {resumen['spy_medio']:+.2f}% | "
                    f"Exceso {resumen['exceso_medio']:+.2f}pp | "
                    f"Bate SPY {resumen['bate_spy']:.1f}% | "
                    f"DD {resumen['drawdown_medio']:+.2f}%"
                )
            )

    return lineas


def clasificar_consenso_analistas(
    consenso
):
    if consenso is None:
        return "SIN CONSENSO"

    consenso = numero(
        consenso
    )

    if consenso >= 0.5:
        return "POSITIVOS"

    if consenso < 0:
        return "NEGATIVOS"

    return "NEUTRALES"


def clasificar_cobertura_analistas(
    analyst_count
):
    cantidad = entero(
        analyst_count
    )

    if cantidad <= 2:
        return "BAJA"

    if cantidad <= 5:
        return "MEDIA"

    if cantidad <= 10:
        return "BUENA"

    return "ALTA"


def formatear_evento_compacto(
    evento
):
    symbol = texto(
        evento.get("symbol")
    )
    tipo = texto(
        evento.get("tipo")
    )
    mensaje = texto(
        evento.get("mensaje"),
        "SIN DETALLE"
    )

    if tipo == "FUERZA_CRECIENTE":
        mejora_rs20 = re.search(
            r"RS20[^|]*\(([+-]?\d+(?:\.\d+)?)\)",
            mensaje
        )

        if mejora_rs20:
            return (
                f"{symbol:<7} | {tipo:<18} | "
                f"RS20 mejora {numero(mejora_rs20.group(1)):+.1f}pp"
            )

    mensaje_corto = mensaje.split(
        "|",
        maxsplit=1
    )[0].strip()

    return (
        f"{symbol:<7} | {tipo:<18} | "
        f"{mensaje_corto}"
    )


def generar_lectura_combinada(
    activo,
    fundamental=None,
    contexto=None,
    analistas=None
):
    prioridad = activo.get(
        "prioridad_estudio"
    )
    tecnico_fuerte = prioridad in (
        "A+",
        "A"
    )
    alertas = formatear_alertas(
        activo.get("alertas_estudio")
    )

    score_fundamental = (
        entero(fundamental.get("score_fundamental"))
        if fundamental
        else None
    )
    fundamental_fuerte = (
        score_fundamental is not None
        and score_fundamental >= 70
    )

    upside = (
        analistas.get("upside_mean_pct")
        if analistas
        else None
    )
    consenso = (
        analistas.get("consensus_score")
        if analistas
        else None
    )
    analistas_disponibles = (
        analistas is not None
        and (
            upside is not None
            or consenso is not None
        )
    )
    expectativas_favorables = (
        upside is not None
        and numero(upside) >= 10
        and consenso is not None
        and numero(consenso) > 0
    )
    expectativas_debiles = (
        (
            upside is not None
            and numero(upside) < -5
        )
        or (
            consenso is not None
            and numero(consenso) < 0
        )
    )

    if alertas != "NINGUNA" and expectativas_debiles:
        return "REVISAR: RIESGO TECNICO Y EXPECTATIVAS DEBILES."

    if tecnico_fuerte and expectativas_debiles:
        return "BUEN MOMENTUM, PERO ANALISTAS MUESTRAN CAUTELA."

    if tecnico_fuerte and fundamental_fuerte and expectativas_favorables:
        return "TECNICO, FUNDAMENTALES Y ANALISTAS ALINEADOS."

    if tecnico_fuerte and expectativas_favorables and fundamental is None:
        return "TECNICO Y ANALISTAS ALINEADOS; FALTA VALIDACION FUNDAMENTAL."

    if tecnico_fuerte and fundamental_fuerte and not analistas_disponibles:
        return "TECNICO Y FUNDAMENTALES ALINEADOS; FALTAN EXPECTATIVAS EXTERNAS."

    if tecnico_fuerte and expectativas_favorables and not fundamental_fuerte:
        return "TECNICO Y ANALISTAS FAVORABLES; FUNDAMENTALES REQUIEREN CAUTELA."

    if (
        contexto
        and contexto.get("contexto") == "POSITIVO"
        and expectativas_favorables
    ):
        return "CATALIZADOR POSITIVO CON EXPECTATIVAS FAVORABLES."

    if tecnico_fuerte and fundamental is not None:
        return "TECNICO FUERTE; FUNDAMENTALES REQUIEREN LECTURA CONJUNTA."

    if tecnico_fuerte and analistas_disponibles:
        return "TECNICO FUERTE; ANALISTAS DISPONIBLES SIN ALINEACION CLARA."

    if tecnico_fuerte:
        return "TECNICO FUERTE; FALTAN CAPAS EXTERNAS PARA CONFIRMAR."

    return "CONFIGURACION PARA SEGUIMIENTO, SIN CONFLUENCIA COMPLETA."


def generar_ficha_resumida(
    activo,
    posicion,
    mapa_news,
    mapa_fundamentales,
    mapa_analistas,
    mapa_revisiones
):
    symbol = texto(
        activo.get("symbol")
    )
    prioridad = texto(
        activo.get("prioridad_estudio")
    )
    fundamental = mapa_fundamentales.get(
        symbol
    )
    contexto = mapa_news.get(
        symbol
    )
    analistas = mapa_analistas.get(
        symbol
    )
    revision = mapa_revisiones.get(
        symbol,
        {}
    )
    alertas = formatear_alertas(
        activo.get("alertas_estudio")
    )

    fundamental_texto = (
        f"{entero(fundamental.get('score_fundamental'))}/100 | "
        f"{texto(fundamental.get('calidad_fundamental'))} | "
        f"Valoracion {texto(fundamental.get('valoracion'))}"
        if fundamental
        else "SIN ANALISIS DISPONIBLE"
    )
    analistas_texto = (
        f"{safe_pct(analistas.get('upside_mean_pct'))} target | "
        f"{clasificar_consenso_analistas(analistas.get('consensus_score'))} | "
        f"n={entero(analistas.get('analyst_count'))} | "
        "Revision 7D "
        f"{texto(revision.get('clasificacion_7d'), 'SIN HISTORICO')}"
        if analistas
        else "SIN DATOS"
    )
    noticias_texto = (
        f"{texto(contexto.get('contexto'))} | "
        f"Catalizador {texto(contexto.get('fuerza_catalizador'))} | "
        f"Riesgo {texto(contexto.get('riesgo_narrativo'))}"
        if contexto
        else "SIN ANALISIS DISPONIBLE"
    )

    lineas = [
        (
            f"{posicion:>2}. {symbol:<7} | "
            f"{prioridad:<2} | "
            f"{entero(activo.get('score')):>3}/100 | "
            f"{safe_precio(activo.get('precio'))} | "
            f"{texto(activo.get('nombre'), symbol)}"
        ),
        (
            "    Tecnico: "
            f"{texto(activo.get('tendencia'))}, "
            f"RSI {safe_rsi(activo.get('rsi'))}, "
            f"RS20 {safe_pp(activo.get('fuerza_20d'))}, "
            f"riesgo {texto(activo.get('riesgo_clasificacion'))}, "
            f"alertas {alertas}"
        ),
        (
            f"    Fundamental: {fundamental_texto} | "
            f"Analistas: {analistas_texto}"
        ),
        (
            f"    Noticias: {noticias_texto} | Lectura: "
            f"{generar_lectura_combinada(activo, fundamental, contexto, analistas)}"
        ),
    ]

    return "\n".join(
        lineas
    )


def generar_lineas_paper_compacto(
    resultados,
    prioridades=None,
    variant=None,
    horizontes=(
        5,
        20,
        60
    )
):
    lineas = []

    for horizonte in horizontes:
        filtrados = [
            fila
            for fila in resultados
            if entero(fila.get("horizonte")) == horizonte
            and (
                variant is None
                or texto(
                    fila.get("variant"),
                    "BASE"
                ) == variant
            )
            and (
                prioridades is None
                or fila.get("prioridad") in prioridades
            )
        ]
        resumen = resumir_paper(
            filtrados
        )

        if resumen is None:
            lineas.append(
                f"{horizonte:>2}D | PENDIENTE"
            )
        else:
            lineas.append(
                (
                    f"{horizonte:>2}D | n={resumen['casos']:<4} | "
                    f"Ret {resumen['retorno_medio']:+.2f}% | "
                    f"Exceso {resumen['exceso_medio']:+.2f}pp | "
                    f"Bate SPY {resumen['bate_spy']:.1f}%"
                )
            )

    return lineas


# ============================================================
# GENERAR INFORME
# ============================================================

def generar_informe():

    # ========================================================
    # SCANS
    # ========================================================

    scan_times_todos = obtener_scan_times(
        limite=NUM_SCANS * 3
    )

    if not scan_times_todos:

        return (
            "No hay datos suficientes "
            "para generar el informe."
        )

    ultimo_scan_time = (
        scan_times_todos[0]
    )

    ultimo_scan = obtener_scan_por_fecha(
        ultimo_scan_time
    )

    if not ultimo_scan:

        return (
            "El ultimo scan no contiene datos."
        )

    version_actual = obtener_version_scan(
        ultimo_scan
    )

    # ========================================================
    # SCANS COMPARABLES
    # ========================================================

    scans_validos = []

    for scan_time in scan_times_todos:

        scan = obtener_scan_por_fecha(
            scan_time
        )

        if not scan:
            continue

        if (
            version_actual

            and obtener_version_scan(
                scan
            ) != version_actual
        ):

            continue

        scans_validos.append(
            (
                scan_time,
                scan
            )
        )

        if len(
            scans_validos
        ) >= NUM_SCANS:

            break

    if not scans_validos:

        return (
            "No existen scans comparables "
            "para generar el informe."
        )

    # ========================================================
    # SESION ACTUAL
    # ========================================================

    market_date = texto(
        ultimo_scan[0].get(
            "market_date"
        ),
        "N/A"
    )

    fecha_scan = texto(
        ultimo_scan[0].get(
            "scan_time"
        ),
        ultimo_scan_time
    )

    # ========================================================
    # NEWS
    # ========================================================

    news_context = (
        obtener_news_context_ultimo_scan()
    )

    mapa_news = construir_mapa_news(
        news_context
    )

    # ========================================================
    # FUNDAMENTALES
    # ========================================================

    fundamentales = (
        obtener_ultimas_clasificaciones_fundamentales()
    )

    mapa_fundamentales = (
        construir_mapa_fundamentales(
            fundamentales
        )
    )

    # ========================================================
    # ANALYST CONSENSUS
    # ========================================================

    analyst_snapshots = [
        fila
        for fila in obtener_ultimos_analyst_snapshots()
        if fila.get("source") == "YAHOO"
    ]

    mapa_analistas = {
        fila["symbol"]: fila
        for fila in analyst_snapshots
    }

    mapa_revisiones = calcular_revisiones_symbols(
        mapa_analistas.keys()
    )

    # ========================================================
    # PAPER
    # ========================================================

    resumen_tracking_momentum = (
        obtener_resumen_paper(
            strategy="MOMENTUM",
            source_score_version="v4"
        )
    )

    resultados_momentum = (
        obtener_resultados_paper(
            strategy="MOMENTUM"
        )
    )

    resultados_momentum_v4 = [
        resultado
        for resultado in resultados_momentum
        if resultado.get(
            "source_score_version"
        ) == "v4"
    ]

    resultados_momentum_v3 = [
        resultado
        for resultado in resultados_momentum
        if resultado.get(
            "source_score_version"
        ) == "v3"
    ]

    resumen_tracking_reversal = (
        obtener_resumen_paper(
            strategy="REVERSAL"
        )
    )

    resultados_reversal = (
        obtener_resultados_paper(
            strategy="REVERSAL"
        )
    )

    carteras_paper_live = obtener_resumen_paper_portfolios()

    # ========================================================
    # PRIORIDADES
    # ========================================================

    prioridades = {

        "A+": 0,
        "A": 0,
        "B": 0,
        "C": 0,
        "D": 0
    }

    for activo in ultimo_scan:

        prioridad = activo.get(
            "prioridad_estudio"
        )

        if prioridad in prioridades:

            prioridades[
                prioridad
            ] += 1

    candidatos_priorizados = sorted(

        ultimo_scan,

        key=lambda activo: (

            prioridad_orden(
                activo.get(
                    "prioridad_estudio"
                )
            ),

            -entero(
                activo.get(
                    "score"
                )
            )
        )
    )

    prioridad_a_mas = [

        activo

        for activo in candidatos_priorizados

        if activo.get(
            "prioridad_estudio"
        ) == "A+"
    ]

    prioridad_a = [

        activo

        for activo in candidatos_priorizados

        if activo.get(
            "prioridad_estudio"
        ) == "A"
    ]

    prioridad_b = [

        activo

        for activo in candidatos_priorizados

        if activo.get(
            "prioridad_estudio"
        ) == "B"
    ]

    # ========================================================
    # PERSISTENCIA
    # ========================================================

    apariciones_top = {}

    scores = {}

    for (
        scan_time,
        scan
    ) in scans_validos:

        for activo in scan[
            :20
        ]:

            symbol = activo[
                "symbol"
            ]

            apariciones_top[
                symbol
            ] = (
                apariciones_top.get(
                    symbol,
                    0
                )
                + 1
            )

        for activo in scan:

            symbol = activo[
                "symbol"
            ]

            scores.setdefault(
                symbol,
                []
            )

            scores[
                symbol
            ].append(
                entero(
                    activo.get(
                        "score"
                    )
                )
            )

    persistentes = sorted(

        apariciones_top.items(),

        key=lambda x: (
            -x[1],
            x[0]
        )
    )

    # ========================================================
    # MEJORANDO
    # ========================================================

    mejorando = []

    for (
        symbol,
        valores
    ) in scores.items():

        if len(
            valores
        ) < 2:

            continue

        score_actual = (
            valores[0]
        )

        score_antiguo = (
            valores[-1]
        )

        cambio = (
            score_actual
            - score_antiguo
        )

        if cambio >= 5:

            mejorando.append(
                (
                    symbol,
                    cambio,
                    score_actual
                )
            )

    mejorando = sorted(

        mejorando,

        key=lambda x: (
            -x[1],
            -x[2],
            x[0]
        )
    )

    # ========================================================
    # EVENTOS
    # ========================================================

    eventos = obtener_eventos_recientes(
        limite=MAX_EVENTOS
    )

    # ========================================================
    # ALERTAS TECNICAS
    # ========================================================

    activos_con_alertas = [

        activo

        for activo in ultimo_scan

        if formatear_alertas(
            activo.get(
                "alertas_estudio"
            )
        ) != "NINGUNA"
    ]

    activos_con_alertas = sorted(

        activos_con_alertas,

        key=lambda activo: (

            prioridad_orden(
                activo.get(
                    "prioridad_estudio"
                )
            ),

            -entero(
                activo.get(
                    "score"
                )
            )
        )
    )

    # ========================================================
    # RESUMEN NEWS
    # ========================================================

    resumen_news = {

        "POSITIVO": 0,
        "MIXTO": 0,
        "NEGATIVO": 0,
        "NEUTRO": 0,
        "SIN NOTICIAS": 0
    }

    for contexto in news_context:

        tipo = texto(
            contexto.get(
                "contexto"
            )
        )

        if tipo in resumen_news:

            resumen_news[
                tipo
            ] += 1

    # ========================================================
    # RESUMEN FUNDAMENTALES
    # ========================================================

    calidades_fundamentales = {}

    valoraciones_fundamentales = {}

    for fila in fundamentales:

        calidad = texto(
            fila.get(
                "calidad_fundamental"
            )
        )

        valoracion = texto(
            fila.get(
                "valoracion"
            )
        )

        calidades_fundamentales[
            calidad
        ] = (
            calidades_fundamentales.get(
                calidad,
                0
            )
            + 1
        )

        valoraciones_fundamentales[
            valoracion
        ] = (
            valoraciones_fundamentales.get(
                valoracion,
                0
            )
            + 1
        )

    # ========================================================
    # INFORME
    # ========================================================

    lineas = []

    lineas.append(
        "TRADING RADAR - INFORME SEMANAL"
    )

    lineas.append(
        "=" * 84
    )

    lineas.append("")

    lineas.append(
        (
            "Generado: "
            + datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
        )
    )

    lineas.append(
        f"Sesion de mercado: {market_date}"
    )

    lineas.append(
        f"Ultimo scan: {fecha_scan}"
    )

    lineas.append(
        (
            "Score analizado: "
            f"{version_actual or 'N/A'}"
        )
    )

    lineas.append(
        (
            "Scans comparables analizados: "
            f"{len(scans_validos)}"
        )
    )

    lineas.append(
        (
            "Activos en ultimo radar: "
            f"{len(ultimo_scan)}"
        )
    )

    # ========================================================
    # RESUMEN EJECUTIVO
    # ========================================================

    lineas.append("")

    lineas.append(
        "RESUMEN EJECUTIVO"
    )

    lineas.append(
        "-" * 84
    )

    lineas.append(
        (
            f"A+ : {prioridades['A+']} | "
            f"A : {prioridades['A']} | "
            f"B : {prioridades['B']} | "
            f"C : {prioridades['C']} | "
            f"D : {prioridades['D']}"
        )
    )

    lineas.append(
        (
            "News analizadas: "
            f"{len(news_context)}"
        )
    )

    lineas.append(
        (
            "News POSITIVO: "
            f"{resumen_news['POSITIVO']} | "
            "MIXTO: "
            f"{resumen_news['MIXTO']} | "
            "NEGATIVO: "
            f"{resumen_news['NEGATIVO']} | "
            "SIN NOTICIAS: "
            f"{resumen_news['SIN NOTICIAS']}"
        )
    )

    lineas.append(
        (
            "Fundamentales clasificados: "
            f"{len(fundamentales)}"
        )
    )

    lineas.append(
        (
            "Fundamental EXCELENTE: "
            f"{calidades_fundamentales.get('EXCELENTE', 0)} | "
            "SOLIDA: "
            f"{calidades_fundamentales.get('SOLIDA', 0)} | "
            "MIXTA: "
            f"{calidades_fundamentales.get('MIXTA', 0)} | "
            "DEBIL: "
            f"{calidades_fundamentales.get('DEBIL', 0)} | "
            "MUY DEBIL: "
            f"{calidades_fundamentales.get('MUY DEBIL', 0)}"
        )
    )

    lineas.append(
        (
            "Valoracion FAVORABLE: "
            f"{valoraciones_fundamentales.get('FAVORABLE', 0)} | "
            "RAZONABLE: "
            f"{valoraciones_fundamentales.get('RAZONABLE', 0)} | "
            "EXIGENTE: "
            f"{valoraciones_fundamentales.get('EXIGENTE', 0)} | "
            "MUY EXIGENTE: "
            f"{valoraciones_fundamentales.get('MUY EXIGENTE', 0)}"
        )
    )

    # ========================================================
    # A+
    # ========================================================

    lineas.append("")

    lineas.append(
        "PRIORIDAD A+ - REVISION PRINCIPAL"
    )

    lineas.append(
        "=" * 84
    )

    if prioridad_a_mas:

        for posicion, activo in enumerate(
            prioridad_a_mas[
                :5
            ],
            start=1
        ):

            lineas.append("")

            lineas.append(
                generar_ficha_resumida(
                    activo,
                    posicion,
                    mapa_news,
                    mapa_fundamentales,
                    mapa_analistas,
                    mapa_revisiones
                )
            )

    else:

        lineas.append(
            "No hay candidatos A+."
        )

    # ========================================================
    # A
    # ========================================================

    lineas.append("")

    lineas.append(
        "PRIORIDAD A - ALTA PRIORIDAD"
    )

    lineas.append(
        "=" * 84
    )

    if prioridad_a:

        for posicion, activo in enumerate(
            prioridad_a[
                :5
            ],
            start=1
        ):

            lineas.append("")

            lineas.append(
                generar_ficha_resumida(
                    activo,
                    posicion,
                    mapa_news,
                    mapa_fundamentales,
                    mapa_analistas,
                    mapa_revisiones
                )
            )

    else:

        lineas.append(
            "No hay candidatos A."
        )

    # ========================================================
    # CONFLICTOS / EXPECTATIVAS
    # ========================================================

    conflictos = []

    for activo in prioridad_a_mas + prioridad_a:
        analistas = mapa_analistas.get(
            activo.get("symbol")
        )

        if not analistas:
            continue

        upside = analistas.get("upside_mean_pct")
        consenso = analistas.get("consensus_score")

        if (
            upside is not None
            and numero(upside) < -5
        ) or (
            consenso is not None
            and numero(consenso) < 0
        ):
            conflictos.append((activo, analistas))

    conflictos = sorted(
        conflictos,
        key=lambda par: numero(
            par[1].get("upside_mean_pct"),
            999.0
        )
    )

    lineas.append("")
    lineas.append("CONFLICTOS A REVISAR")
    lineas.append("=" * 84)
    lineas.append("n = numero de analistas incluidos en el consenso.")

    if conflictos:
        for activo, analistas in conflictos[:20]:
            lineas.append(
                (
                    f"{texto(activo.get('symbol')):<7} | "
                    f"{texto(activo.get('prioridad_estudio')):<2} "
                    f"{entero(activo.get('score')):>3} | "
                    f"Target {safe_pct(analistas.get('upside_mean_pct'))} | "
                    "Consenso "
                    f"{decimal_consenso(analistas.get('consensus_score'))} | "
                    f"n={entero(analistas.get('analyst_count'))} "
                    f"{clasificar_cobertura_analistas(analistas.get('analyst_count'))}"
                )
            )
    else:
        lineas.append("No hay conflictos claros con analistas.")

    expectativas = []

    for activo in prioridad_a_mas + prioridad_a + prioridad_b:
        analistas = mapa_analistas.get(
            activo.get("symbol")
        )

        if (
            analistas
            and analistas.get("upside_mean_pct") is not None
        ):
            expectativas.append((activo, analistas))

    expectativas_cobertura = sorted(
        (
            par
            for par in expectativas
            if entero(par[1].get("analyst_count")) >= 3
        ),
        key=lambda par: numero(
            par[1].get("upside_mean_pct")
        ),
        reverse=True
    )

    expectativas_cobertura_baja = sorted(
        (
            par
            for par in expectativas
            if entero(par[1].get("analyst_count")) < 3
        ),
        key=lambda par: numero(
            par[1].get("upside_mean_pct")
        ),
        reverse=True
    )

    expectativas = (
        expectativas_cobertura
        + expectativas_cobertura_baja
    )

    lineas.append("")
    lineas.append("EXPECTATIVAS DESTACADAS")
    lineas.append("=" * 84)

    if expectativas:
        for activo, analistas in expectativas[:10]:
            lineas.append(
                (
                    f"{texto(activo.get('symbol')):<7} | "
                    f"{texto(activo.get('prioridad_estudio')):<2} | "
                    f"{entero(activo.get('score')):>3} | "
                    f"Target {safe_pct(analistas.get('upside_mean_pct'))} | "
                    "Consenso "
                    f"{decimal_consenso(analistas.get('consensus_score'))} | "
                    f"n={entero(analistas.get('analyst_count'))} "
                    f"{clasificar_cobertura_analistas(analistas.get('analyst_count'))}"
                )
            )
    else:
        lineas.append("No hay expectativas disponibles para A+/A/B.")

    revisiones_destacadas = [
        revision
        for revision in mapa_revisiones.values()
        if revision.get("clasificacion_7d") in (
            "MUY NEGATIVA",
            "NEGATIVA",
            "MUY POSITIVA",
            "POSITIVA"
        )
    ]
    orden_revision = {
        "MUY NEGATIVA": 0,
        "NEGATIVA": 1,
        "MUY POSITIVA": 2,
        "POSITIVA": 3
    }
    revisiones_destacadas = sorted(
        revisiones_destacadas,
        key=lambda revision: (
            orden_revision.get(
                revision.get("clasificacion_7d"),
                99
            ),
            -max(
                abs(numero(
                    revision.get("target_mean_change_pct_7d")
                )),
                abs(numero(
                    revision.get("eps_next_year_change_pct_7d")
                )),
                abs(numero(
                    revision.get("consensus_change_7d")
                ))
            ),
            revision.get("symbol", "")
        )
    )

    lineas.append("")
    lineas.append("REVISIONES ANALISTAS DESTACADAS")
    lineas.append("=" * 84)

    if revisiones_destacadas:
        for revision in revisiones_destacadas[:10]:
            lineas.append(
                (
                    f"{texto(revision.get('symbol')):<7} | "
                    "Target 7D "
                    f"{safe_pct(revision.get('target_mean_change_pct_7d'))} | "
                    "EPS "
                    f"{safe_pct(revision.get('eps_next_year_change_pct_7d'))} | "
                    "Consenso "
                    f"{decimal_consenso(revision.get('consensus_change_7d'))} | "
                    f"{texto(revision.get('clasificacion_7d'))}"
                )
            )
    else:
        lineas.append("No hay revisiones relevantes con historico 7D.")

    inicio_detalles_news_fund = len(lineas)

    # ========================================================
    # NEWS DESTACADAS
    # ========================================================

    lineas.append("")

    lineas.append(
        "CONTEXTO DE NOTICIAS DESTACADO"
    )

    lineas.append(
        "=" * 84
    )

    if news_context:

        noticias_ordenadas = sorted(

            news_context,

            key=lambda fila: (

                prioridad_orden(
                    fila.get(
                        "prioridad_tecnica"
                    )
                ),

                0
                if fila.get(
                    "contexto"
                ) in [
                    "NEGATIVO",
                    "MIXTO"
                ]
                else 1,

                -entero(
                    fila.get(
                        "score"
                    )
                )
            )
        )

        for contexto in noticias_ordenadas[
            :TOP_NEWS
        ]:

            lineas.append(
                (
                    f"{texto(contexto.get('symbol')):<7} | "
                    f"{entero(contexto.get('score')):>3}/100 | "
                    f"Prioridad "
                    f"{texto(contexto.get('prioridad_tecnica')):<2} | "
                    f"{texto(contexto.get('contexto'))}"
                )
            )

            lineas.append(
                (
                    "      Movimiento: "
                    f"{texto(contexto.get('movimiento_explicado'))} | "
                    "Catalizador: "
                    f"{texto(contexto.get('fuerza_catalizador'))} | "
                    "Riesgo narrativo: "
                    f"{texto(contexto.get('riesgo_narrativo'))}"
                )
            )

            lineas.append(
                (
                    "      Catalizadores: "
                    f"{formatear_lista_db(contexto.get('catalizadores'))}"
                )
            )

            lineas.append(
                (
                    "      Evidencias +: "
                    f"{formatear_lista_db(contexto.get('evidencias_positivas'))}"
                )
            )

            lineas.append(
                (
                    "      Evidencias -: "
                    f"{formatear_lista_db(contexto.get('evidencias_negativas'))}"
                )
            )

            lineas.append(
                (
                    "      Riesgos: "
                    f"{formatear_lista_db(contexto.get('riesgos'))}"
                )
            )

    else:

        lineas.append(
            "No hay contexto de noticias disponible."
        )

    # ========================================================
    # FUNDAMENTALES DESTACADOS
    # ========================================================

    lineas.append("")

    lineas.append(
        "FUNDAMENTALES DESTACADOS"
    )

    lineas.append(
        "=" * 84
    )

    if fundamentales:

        fundamentales_ordenados = sorted(

            fundamentales,

            key=lambda fila: (
                -entero(
                    fila.get(
                        "score_fundamental"
                    )
                ),
                fila.get(
                    "symbol",
                    ""
                )
            )
        )

        for fundamental in fundamentales_ordenados[
            :15
        ]:

            lineas.append(
                (
                    f"{texto(fundamental.get('symbol')):<7} | "
                    f"{entero(fundamental.get('score_fundamental')):>3}/100 | "
                    f"{texto(fundamental.get('calidad_fundamental')):<10} | "
                    f"{texto(fundamental.get('valoracion'))}"
                )
            )

    else:

        lineas.append(
            "No hay fundamentales clasificados."
        )

    del lineas[inicio_detalles_news_fund:]

    inicio_paper_detallado = len(lineas)

    # ========================================================
    # PAPER TRACKING
    # ========================================================

    lineas.append("")

    lineas.append(
        "PAPER TRACKING"
    )

    lineas.append(
        "=" * 84
    )

    lineas.append(
        "MOMENTUM V4"
    )

    lineas.append(
        "-" * 84
    )

    if resumen_tracking_momentum[
        "senales"
    ]:

        lineas.append(
            "Estado de senales:"
        )

        for fila in resumen_tracking_momentum[
            "senales"
        ]:

            lineas.append(
                (
                    f"  {texto(fila.get('prioridad')):<3} | "
                    f"{texto(fila.get('estado')):<10} | "
                    f"{entero(fila.get('cantidad')):>4}"
                )
            )

    else:

        lineas.append(
            "Todavia no existen senales Momentum V4."
        )

    lineas.append("")

    lineas.append(
        "Resultados maduros:"
    )

    if resumen_tracking_momentum[
        "resultados"
    ]:

        for fila in resumen_tracking_momentum[
            "resultados"
        ]:

            lineas.append(
                (
                    f"  {entero(fila.get('horizonte')):>2} sesiones: "
                    f"{entero(fila.get('cantidad'))}"
                )
            )

    else:

        lineas.append(
            "  Todavia ninguno."
        )

    lineas.append("")

    lineas.append(
        "Performance 5/20/60 sesiones:"
    )

    lineas.extend(
        generar_lineas_performance_paper(
            resultados_momentum_v4
        )
    )

    lineas.append(
        (
            "Momentum V4 paper: "
            f"{len(resultados_momentum_v4)} resultados maduros | "
            "Reversal V1 paper: "
            f"{len(resultados_reversal)} resultados maduros"
        )
    )

    lineas.append("")

    lineas.append(
        "REVERSAL V1"
    )

    lineas.append(
        "-" * 84
    )

    if resumen_tracking_reversal[
        "senales"
    ]:

        lineas.append(
            "Estado de senales:"
        )

        for fila in resumen_tracking_reversal[
            "senales"
        ]:

            lineas.append(
                (
                    f"  {texto(fila.get('prioridad')):<3} | "
                    f"{texto(fila.get('estado')):<10} | "
                    f"{entero(fila.get('cantidad')):>4}"
                )
            )

    else:

        lineas.append(
            "Todavia no existen senales Reversal V1."
        )

    lineas.append("")

    lineas.append(
        "Resultados maduros:"
    )

    if resumen_tracking_reversal[
        "resultados"
    ]:

        for fila in resumen_tracking_reversal[
            "resultados"
        ]:

            lineas.append(
                (
                    f"  {entero(fila.get('horizonte')):>2} sesiones: "
                    f"{entero(fila.get('cantidad'))}"
                )
            )

    else:

        lineas.append(
            "  Todavia ninguno."
        )

    lineas.append("")

    lineas.append(
        "Performance 5/20/60 sesiones:"
    )

    lineas.extend(
        generar_lineas_performance_paper(
            resultados_reversal,
            prioridades=["A"]
        )
    )

    del lineas[inicio_paper_detallado:]

    lineas.append("")
    lineas.append("PAPER TRACKING")
    lineas.append("=" * 84)
    lineas.append("Momentum V4 | BASE (A+/A):")
    lineas.extend(
        generar_lineas_paper_compacto(
            resultados_momentum_v4,
            prioridades=["A+", "A"],
            variant="BASE"
        )
    )

    lineas.append("")
    lineas.append("Momentum V4 | TP25 (A+/A):")
    lineas.extend(
        generar_lineas_paper_compacto(
            resultados_momentum_v4,
            prioridades=["A+", "A"],
            variant="TP25",
            horizontes=(5,)
        )
    )
    lineas.append("")
    lineas.append("Reversal V1 | BASE (A):")
    lineas.extend(
        generar_lineas_paper_compacto(
            resultados_reversal,
            prioridades=["A"],
            variant="BASE"
        )
    )
    lineas.append("")
    lineas.append("Reversal V1 | TP10 (A):")
    lineas.extend(
        generar_lineas_paper_compacto(
            resultados_reversal,
            prioridades=["A"],
            variant="TP10",
            horizontes=(5,)
        )
    )

    lineas.append("")
    lineas.append("PAPER PORTFOLIO LIVE")
    lineas.append("=" * 84)

    if carteras_paper_live:
        for cartera in carteras_paper_live:
            lineas.extend(generar_lineas_paper_portfolio_live(cartera))
    else:
        lineas.append("Carteras paper live todavia no inicializadas.")

    inicio_detalles_b_top = len(lineas)

    # ========================================================
    # B
    # ========================================================

    lineas.append("")

    lineas.append(
        "PRIORIDAD B - INTERESANTES CON CAUTELAS"
    )

    lineas.append(
        "=" * 84
    )

    if prioridad_b:

        for posicion, activo in enumerate(
            prioridad_b[
                :5
            ],
            start=1
        ):
            lineas.append(
                generar_ficha_activo(
                    activo,
                    posicion,
                    mapa_news,
                    mapa_fundamentales
                )
            )

    else:

        lineas.append(
            "No hay candidatos B."
        )

    # ========================================================
    # TOP 20
    # ========================================================

    lineas.append("")

    lineas.append(
        "TOP 20 ACTUAL - INFORMACION COMPLETA"
    )

    lineas.append(
        "=" * 84
    )

    for posicion, activo in enumerate(
        ultimo_scan[
            :TOP_COMPLETO
        ],
        start=1
    ):

        lineas.append("")

        lineas.append(
            generar_ficha_activo(
                activo,
                posicion,
                mapa_news,
                mapa_fundamentales
            )
        )

    del lineas[inicio_detalles_b_top:]

    # ========================================================
    # PERSISTENCIA
    # ========================================================

    lineas.append("")

    lineas.append(
        "MAS PERSISTENTES EN TOP 20"
    )

    lineas.append(
        "-" * 84
    )

    if persistentes:

        for (
            symbol,
            cantidad
        ) in persistentes[
            :5
        ]:

            lineas.append(
                (
                    f"{symbol:<8} "
                    f"{cantidad}/"
                    f"{len(scans_validos)} scans"
                )
            )

    else:

        lineas.append(
            "Sin datos suficientes."
        )

    # ========================================================
    # MEJORANDO
    # ========================================================

    lineas.append("")

    lineas.append(
        "MAYORES MEJORAS DE SCORE"
    )

    lineas.append(
        "-" * 84
    )

    if mejorando:

        for (
            symbol,
            cambio,
            score_actual
        ) in mejorando[
            :TOP_MEJORANDO
        ]:

            lineas.append(
                (
                    f"{symbol:<8} "
                    f"{cambio:+.0f} puntos "
                    f"-> {score_actual}/100"
                )
            )

    else:

        lineas.append(
            "No hay mejoras >= 5 puntos "
            "entre scans comparables."
        )

    inicio_alertas_detalladas = len(lineas)

    # ========================================================
    # ALERTAS TECNICAS
    # ========================================================

    lineas.append("")

    lineas.append(
        "ALERTAS TECNICAS DESTACADAS"
    )

    lineas.append(
        "-" * 84
    )

    if activos_con_alertas:

        for activo in activos_con_alertas[
            :15
        ]:

            lineas.append(
                (
                    f"{texto(activo.get('symbol')):<7} | "
                    f"{entero(activo.get('score')):>3}/100 | "
                    f"Prioridad "
                    f"{texto(activo.get('prioridad_estudio')):<2} | "
                    f"{formatear_alertas(activo.get('alertas_estudio'))}"
                )
            )

    else:

        lineas.append(
            "No hay alertas tecnicas destacadas."
        )

    del lineas[inicio_alertas_detalladas:]

    # ========================================================
    # EVENTOS
    # ========================================================

    lineas.append("")

    lineas.append(
        "EVENTOS RECIENTES"
    )

    lineas.append(
        "-" * 84
    )

    if eventos:

        for evento in eventos[
            :5
        ]:
            lineas.append(
                formatear_evento_compacto(
                    evento
                )
            )

    else:

        lineas.append(
            "Sin eventos relevantes."
        )

    inicio_leyenda_detallada = len(lineas)

    # ========================================================
    # LEYENDA
    # ========================================================

    lineas.append("")

    lineas.append(
        "COMO LEER EL RADAR"
    )

    lineas.append(
        "-" * 84
    )

    lineas.append(
        (
            "RS20/RS60 = fuerza relativa frente a SPY "
            "en 20/60 sesiones."
        )
    )

    lineas.append(
        (
            "S20/S60 = fuerza relativa frente al ETF "
            "sectorial."
        )
    )

    lineas.append(
        (
            "T = tendencia | M = momentum | "
            "SPY = fuerza mercado | SEC = fuerza sector | "
            "CONT = continuacion respecto a SMA20."
        )
    )

    lineas.append(
        (
            "Momentum V4: T 20 | M 20 | SPY 20 | "
            "SEC 10 | CONT 20 | V 10."
        )
    )

    lineas.append(
        (
            "En Momentum V4 el riesgo es un overlay "
            "y no concede puntos."
        )
    )

    lineas.append(
        (
            "A+, A y B son prioridades de estudio, "
            "no senales automaticas de compra."
        )
    )

    lineas.append(
        (
            "El Score Fundamental es independiente "
            "de Momentum V4 y de Reversal V1."
        )
    )

    lineas.append(
        (
            "La clasificacion fundamental resume crecimiento, "
            "rentabilidad, balance, cash flow y valoracion "
            "segun el modelo aplicable."
        )
    )

    lineas.append(
        (
            "Los modelos BANK, FINANCIAL, REIT y BIOTECH "
            "no utilizan exactamente las mismas metricas "
            "que una empresa operativa."
        )
    )

    lineas.append(
        (
            "Contexto de noticias indica si existe un "
            "catalizador visible, no si la empresa esta barata."
        )
    )

    lineas.append(
        (
            "Paper tracking mide que ocurrio despues de "
            "las senales historicas; no predice resultados futuros."
        )
    )

    del lineas[inicio_leyenda_detallada:]

    lineas.append("")
    lineas.append("COMO LEER EL RADAR")
    lineas.append("-" * 84)
    lineas.append(
        "Momentum V4 = fortaleza tecnica actual. "
        "A+/A/B son prioridades de estudio, no compras."
    )
    lineas.append(
        "Fundamental = calidad, crecimiento, balance, caja y valoracion de la empresa."
    )
    lineas.append(
        "Yahoo Analyst Consensus = expectativas externas; "
        "Target indica potencial frente al precio actual."
    )
    lineas.append(
        "Revision analistas = cambio reciente en targets, EPS y consenso; "
        "mide direccion de expectativas, no valoracion absoluta."
    )
    lineas.append(
        "n = numero de analistas; cuanto mayor sea n, mayor es la cobertura del consenso."
    )
    lineas.append(
        "Noticias = contexto y catalizadores recientes; "
        "no sustituyen tecnico ni fundamentales."
    )
    lineas.append(
        "Reversal V1 = candidatos castigados tecnicamente con posible rebote; "
        "es una estrategia separada."
    )
    lineas.append(
        "Paper Tracking = mide que ocurrio despues de las senales, no predice el futuro."
    )
    lineas.append(
        "Paper Portfolio Live = simulacion continua de capital realista con "
        "senales futuras; no usa dinero real ni ejecuta ordenes."
    )

    # ========================================================
    # DISCLAIMER
    # ========================================================

    lineas.append("")

    lineas.append(
        "=" * 84
    )

    lineas.append(
        (
            "Este radar identifica activos para investigar. "
            "No son recomendaciones de compra o venta."
        )
    )

    lineas.append(
        (
            "La prioridad tecnica debe interpretarse junto "
            "a fundamentales, noticias, riesgo y resultados "
            "historicos del modelo."
        )
    )

    return "\n".join(
        lineas
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # ESQUEMA
    # ========================================================

    inicializar_db()

    inicializar_tabla_eventos()

    asegurar_columna_market_date()

    asegurar_columnas_sectoriales()

    asegurar_columnas_score_v3()

    asegurar_columnas_v4_reversal()

    asegurar_columnas_clasificacion()

    inicializar_tablas_paper()

    inicializar_tablas_paper_portfolio()

    inicializar_tablas_news()

    # ========================================================
    # GENERAR INFORME
    # ========================================================

    informe = generar_informe()

    print(
        "\n"
        + informe
    )

    # ========================================================
    # EMAIL
    # ========================================================

    fecha = datetime.now().strftime(
        "%d/%m/%Y"
    )

    asunto = (
        f"Trading Radar - "
        f"Informe semanal {fecha}"
    )

    try:

        enviar_email(
            asunto,
            informe
        )

        print(
            "\nCorreo semanal enviado correctamente."
        )

    except Exception as e:

        print(
            f"\nERROR enviando correo: {e}"
        )


if __name__ == "__main__":

    main()
