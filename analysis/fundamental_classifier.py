# ============================================================
# FUNDAMENTAL CLASSIFIER V1
# ============================================================


# ============================================================
# HELPERS
# ============================================================

def numero(
    valor,
    defecto=None
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


def texto(
    valor,
    defecto="N/A"
):

    if valor is None:
        return defecto

    valor = str(
        valor
    ).strip()

    if not valor:
        return defecto

    return valor


# ============================================================
# CRECIMIENTO
# ============================================================

def clasificar_crecimiento(
    fundamental
):

    revenue_yoy = numero(
        fundamental.get(
            "revenue_yoy"
        )
    )

    net_income_yoy = numero(
        fundamental.get(
            "net_income_yoy"
        )
    )

    # ========================================================
    # SIN INGRESOS
    # ========================================================

    if revenue_yoy is None:

        if net_income_yoy is None:

            return {
                "clasificacion":
                    "NO EVALUABLE",

                "puntos":
                    0,

                "detalle":
                    "No existen suficientes datos comparables de crecimiento."
            }

        if net_income_yoy >= 15:

            return {
                "clasificacion":
                    "FUERTE",

                "puntos":
                    4,

                "detalle":
                    "El beneficio muestra crecimiento fuerte."
            }

        if net_income_yoy >= 0:

            return {
                "clasificacion":
                    "MODERADO",

                "puntos":
                    3,

                "detalle":
                    "El beneficio mantiene crecimiento positivo."
            }

        return {
            "clasificacion":
                "DEBIL",

            "puntos":
                1,

            "detalle":
                "El beneficio se esta deteriorando."
        }

    # ========================================================
    # REVENUE
    # ========================================================

    if revenue_yoy >= 20:

        clasificacion = "FUERTE"
        puntos = 4

    elif revenue_yoy >= 5:

        clasificacion = "MODERADO"
        puntos = 3

    elif revenue_yoy >= 0:

        clasificacion = "BAJO"
        puntos = 2

    else:

        clasificacion = "NEGATIVO"
        puntos = 1

    # ========================================================
    # CONFIRMACION BENEFICIO
    # ========================================================

    if net_income_yoy is not None:

        if (
            revenue_yoy > 0
            and net_income_yoy > revenue_yoy
        ):

            detalle = (
                "Los ingresos crecen y el beneficio "
                "crece a mayor ritmo."
            )

        elif (
            revenue_yoy > 0
            and net_income_yoy < 0
        ):

            detalle = (
                "Los ingresos crecen, pero el beneficio "
                "se esta deteriorando."
            )

        elif (
            revenue_yoy < 0
            and net_income_yoy > 0
        ):

            detalle = (
                "Los ingresos caen, aunque el beneficio "
                "ha mejorado."
            )

        else:

            detalle = (
                "Ingresos y beneficio mantienen una "
                "evolucion similar."
            )

    else:

        detalle = (
            "La clasificacion se basa principalmente "
            "en crecimiento de ingresos."
        )

    return {
        "clasificacion":
            clasificacion,

        "puntos":
            puntos,

        "detalle":
            detalle
    }


# ============================================================
# RENTABILIDAD OPERATING
# ============================================================

def clasificar_rentabilidad_operating(
    fundamental
):

    net_income = numero(
        fundamental.get(
            "net_income_ttm"
        )
    )

    margen_neto = numero(
        fundamental.get(
            "net_margin"
        )
    )

    margen_operativo = numero(
        fundamental.get(
            "operating_margin"
        )
    )

    if (
        net_income is None
        and margen_neto is None
        and margen_operativo is None
    ):

        return {
            "clasificacion":
                "NO EVALUABLE",

            "puntos":
                0
        }

    if (
        net_income is not None
        and net_income < 0
    ):

        return {
            "clasificacion":
                "NEGATIVA",

            "puntos":
                0
        }

    margen_referencia = (
        margen_operativo
    )

    if margen_referencia is None:

        margen_referencia = (
            margen_neto
        )

    if margen_referencia is None:

        return {
            "clasificacion":
                "POSITIVA",

            "puntos":
                2
        }

    if margen_referencia >= 20:

        return {
            "clasificacion":
                "MUY ALTA",

            "puntos":
                4
        }

    if margen_referencia >= 10:

        return {
            "clasificacion":
                "ALTA",

            "puntos":
                3
        }

    if margen_referencia >= 5:

        return {
            "clasificacion":
                "MODERADA",

            "puntos":
                2
        }

    if margen_referencia >= 0:

        return {
            "clasificacion":
                "BAJA",

            "puntos":
                1
        }

    return {
        "clasificacion":
            "NEGATIVA",

        "puntos":
            0
    }


# ============================================================
# BALANCE OPERATING
# ============================================================

def clasificar_balance_operating(
    fundamental
):
    """
    Evalua el balance de una empresa operativa.

    IMPORTANTE:
    Si el patrimonio neto es <= 0 no interpretamos
    Debt/Equity negativo como baja deuda.

    Ese caso se considera especificamente:
        PATRIMONIO NEGATIVO
    """

    deuda_equity = numero(
        fundamental.get(
            "debt_to_equity"
        )
    )

    cash = numero(
        fundamental.get(
            "cash"
        )
    )

    debt = numero(
        fundamental.get(
            "debt"
        )
    )

    equity = numero(
        fundamental.get(
            "equity"
        )
    )

    # ========================================================
    # PATRIMONIO NEGATIVO
    # ========================================================

    if (
        equity is not None
        and equity <= 0
    ):

        return {
            "clasificacion":
                "PATRIMONIO NEGATIVO",

            "puntos":
                0
        }

    # ========================================================
    # SIN DATOS
    # ========================================================

    if (
        deuda_equity is None
        and cash is None
        and debt is None
    ):

        return {
            "clasificacion":
                "NO EVALUABLE",

            "puntos":
                0
        }

    # ========================================================
    # DEBT / EQUITY
    # ========================================================

    if deuda_equity is not None:

        if deuda_equity <= 0.25:

            clasificacion = (
                "MUY SOLIDO"
            )

            puntos = 4

        elif deuda_equity <= 0.75:

            clasificacion = (
                "SOLIDO"
            )

            puntos = 3

        elif deuda_equity <= 1.5:

            clasificacion = (
                "MODERADO"
            )

            puntos = 2

        else:

            clasificacion = (
                "APALANCADO"
            )

            puntos = 1

    else:

        clasificacion = (
            "NO EVALUABLE"
        )

        puntos = 0

    # ========================================================
    # CAJA NETA
    # ========================================================

    if (
        cash is not None
        and debt is not None
        and cash > debt
    ):

        if puntos < 4:

            puntos += 1

        if puntos >= 4:

            clasificacion = (
                "MUY SOLIDO"
            )

    return {
        "clasificacion":
            clasificacion,

        "puntos":
            min(
                puntos,
                4
            )
    }


# ============================================================
# CASH FLOW
# ============================================================

def clasificar_cash_flow(
    fundamental
):

    fcf = numero(
        fundamental.get(
            "fcf_ttm"
        )
    )

    fcf_yield = numero(
        fundamental.get(
            "fcf_yield"
        )
    )

    if fcf is None:

        return {
            "clasificacion":
                "NO EVALUABLE",

            "puntos":
                0
        }

    if fcf < 0:

        return {
            "clasificacion":
                "NEGATIVO",

            "puntos":
                0
        }

    if fcf_yield is None:

        return {
            "clasificacion":
                "POSITIVO",

            "puntos":
                2
        }

    if fcf_yield >= 8:

        return {
            "clasificacion":
                "MUY FUERTE",

            "puntos":
                4
        }

    if fcf_yield >= 4:

        return {
            "clasificacion":
                "FUERTE",

            "puntos":
                3
        }

    if fcf_yield >= 2:

        return {
            "clasificacion":
                "MODERADO",

            "puntos":
                2
        }

    if fcf_yield > 0:

        return {
            "clasificacion":
                "BAJO",

            "puntos":
                1
        }

    return {
        "clasificacion":
            "NEGATIVO",

        "puntos":
            0
    }


# ============================================================
# VALORACION OPERATING
# ============================================================

def clasificar_valoracion_operating(
    fundamental
):
    """
    Clasificacion prudente de la exigencia
    de los multiplos disponibles.

    No equivale a estimar valor intrinseco.
    """

    pe = numero(
        fundamental.get(
            "pe_ttm"
        )
    )

    ps = numero(
        fundamental.get(
            "ps_ttm"
        )
    )

    fcf_yield = numero(
        fundamental.get(
            "fcf_yield"
        )
    )

    puntos_exigencia = 0

    metricas = 0

    # ========================================================
    # P/E
    # ========================================================

    if pe is not None:

        metricas += 1

        if pe <= 15:

            puntos_exigencia += 0

        elif pe <= 25:

            puntos_exigencia += 1

        elif pe <= 40:

            puntos_exigencia += 2

        else:

            puntos_exigencia += 3

    # ========================================================
    # P/S
    # ========================================================

    if ps is not None:

        metricas += 1

        if ps <= 2:

            puntos_exigencia += 0

        elif ps <= 5:

            puntos_exigencia += 1

        elif ps <= 10:

            puntos_exigencia += 2

        else:

            puntos_exigencia += 3

    # ========================================================
    # FCF YIELD
    # ========================================================

    if fcf_yield is not None:

        metricas += 1

        if fcf_yield >= 6:

            puntos_exigencia += 0

        elif fcf_yield >= 3:

            puntos_exigencia += 1

        elif fcf_yield >= 1:

            puntos_exigencia += 2

        else:

            puntos_exigencia += 3

    if metricas == 0:

        return {
            "clasificacion":
                "NO EVALUABLE",

            "puntos":
                0
        }

    media = (
        puntos_exigencia
        / metricas
    )

    if media <= 0.5:

        return {
            "clasificacion":
                "FAVORABLE",

            "puntos":
                4
        }

    if media <= 1.25:

        return {
            "clasificacion":
                "RAZONABLE",

            "puntos":
                3
        }

    if media <= 2.0:

        return {
            "clasificacion":
                "EXIGENTE",

            "puntos":
                2
        }

    return {
        "clasificacion":
            "MUY EXIGENTE",

        "puntos":
            1
    }


# ============================================================
# BANK / FINANCIAL
# ============================================================

def clasificar_bank(
    fundamental
):

    pe = numero(
        fundamental.get(
            "pe_ttm"
        )
    )

    pb = numero(
        fundamental.get(
            "pb"
        )
    )

    roe = numero(
        fundamental.get(
            "roe"
        )
    )

    fortalezas = []

    debilidades = []

    alertas = []

    # ========================================================
    # RENTABILIDAD
    # ========================================================

    if roe is None:

        rentabilidad = (
            "NO EVALUABLE"
        )

        puntos_rentabilidad = 0

    elif roe >= 15:

        rentabilidad = (
            "MUY ALTA"
        )

        puntos_rentabilidad = 4

        fortalezas.append(
            "ROE elevado"
        )

    elif roe >= 10:

        rentabilidad = (
            "ALTA"
        )

        puntos_rentabilidad = 3

        fortalezas.append(
            "ROE solido"
        )

    elif roe >= 7:

        rentabilidad = (
            "MODERADA"
        )

        puntos_rentabilidad = 2

    else:

        rentabilidad = (
            "BAJA"
        )

        puntos_rentabilidad = 1

        debilidades.append(
            "ROE reducido"
        )

    # ========================================================
    # VALORACION
    # ========================================================

    puntos_valoracion = 0

    if pe is not None:

        if pe <= 10:

            puntos_valoracion += 2

        elif pe <= 15:

            puntos_valoracion += 1

        elif pe >= 25:

            debilidades.append(
                "P/E elevado"
            )

    if pb is not None:

        if pb <= 1.5:

            puntos_valoracion += 2

        elif pb <= 2:

            puntos_valoracion += 1

        elif pb >= 3:

            debilidades.append(
                "P/B elevado"
            )

    if puntos_valoracion >= 3:

        valoracion = (
            "FAVORABLE"
        )

    elif puntos_valoracion >= 1:

        valoracion = (
            "RAZONABLE"
        )

    else:

        valoracion = (
            "EXIGENTE"
        )

    # ========================================================
    # CALIDAD
    # ========================================================

    puntos_totales = (
        puntos_rentabilidad
        + puntos_valoracion
    )

    score_normalizado = round(
        (
            puntos_totales
            / 8
        )
        * 100
    )

    if puntos_totales >= 6:

        calidad = "EXCELENTE"

    elif puntos_totales >= 4:

        calidad = "SOLIDA"

    elif puntos_totales >= 2:

        calidad = "MIXTA"

    else:

        calidad = "DEBIL"

    return {

        "calidad_fundamental":
            calidad,

        "crecimiento":
            "NO EVALUABLE",

        "rentabilidad":
            rentabilidad,

        "balance":
            "MODELO BANCARIO",

        "cash_flow":
            "NO APLICABLE",

        "valoracion":
            valoracion,

        "fortalezas":
            fortalezas,

        "debilidades":
            debilidades,

        "alertas":
            alertas,

        "score_fundamental":
            score_normalizado
    }


# ============================================================
# BIOTECH
# ============================================================

def clasificar_biotech(
    fundamental
):

    cash = numero(
        fundamental.get(
            "cash"
        )
    )

    market_cap = numero(
        fundamental.get(
            "market_cap"
        )
    )

    fortalezas = []

    debilidades = []

    alertas = []

    if (
        cash is not None
        and market_cap is not None
        and market_cap > 0
    ):

        cash_pct = (
            cash
            / market_cap
        ) * 100

    else:

        cash_pct = None

    if cash_pct is None:

        balance = "NO EVALUABLE"

        puntos = 0

    elif cash_pct >= 50:

        balance = "CAJA MUY ALTA"

        puntos = 4

        fortalezas.append(
            "Caja muy elevada frente a capitalizacion"
        )

    elif cash_pct >= 25:

        balance = "CAJA ALTA"

        puntos = 3

        fortalezas.append(
            "Buena posicion de caja"
        )

    elif cash_pct >= 10:

        balance = "CAJA MODERADA"

        puntos = 2

    else:

        balance = "CAJA BAJA"

        puntos = 1

        debilidades.append(
            "Caja reducida frente a capitalizacion"
        )

    alertas.append(
        "Revisar cash burn, runway, pipeline y posible dilucion"
    )

    score_normalizado = round(
        (
            puntos
            / 4
        )
        * 100
    )

    return {

        "calidad_fundamental":
            (
                "SOLIDA"
                if puntos >= 3
                else
                "MIXTA"
            ),

        "crecimiento":
            "NO APLICABLE",

        "rentabilidad":
            "PRE-REVENUE / NO APLICABLE",

        "balance":
            balance,

        "cash_flow":
            "CASH BURN RELEVANTE",

        "valoracion":
            "NO EVALUABLE CON MULTIPLOS TRADICIONALES",

        "fortalezas":
            fortalezas,

        "debilidades":
            debilidades,

        "alertas":
            alertas,

        "score_fundamental":
            score_normalizado
    }


# ============================================================
# OPERATING
# ============================================================

def clasificar_operating(
    fundamental
):

    crecimiento = (
        clasificar_crecimiento(
            fundamental
        )
    )

    rentabilidad = (
        clasificar_rentabilidad_operating(
            fundamental
        )
    )

    balance = (
        clasificar_balance_operating(
            fundamental
        )
    )

    cash_flow = (
        clasificar_cash_flow(
            fundamental
        )
    )

    valoracion = (
        clasificar_valoracion_operating(
            fundamental
        )
    )

    fortalezas = []

    debilidades = []

    alertas = []

    # ========================================================
    # FORTALEZAS
    # ========================================================

    if crecimiento[
        "clasificacion"
    ] in [
        "FUERTE",
        "MODERADO"
    ]:

        fortalezas.append(
            "Crecimiento positivo"
        )

    if rentabilidad[
        "clasificacion"
    ] in [
        "MUY ALTA",
        "ALTA"
    ]:

        fortalezas.append(
            "Margenes elevados"
        )

    if balance[
        "clasificacion"
    ] in [
        "MUY SOLIDO",
        "SOLIDO"
    ]:

        fortalezas.append(
            "Balance solido"
        )

    if cash_flow[
        "clasificacion"
    ] in [
        "MUY FUERTE",
        "FUERTE"
    ]:

        fortalezas.append(
            "Generacion de caja fuerte"
        )

    if valoracion[
        "clasificacion"
    ] in [
        "FAVORABLE",
        "RAZONABLE"
    ]:

        fortalezas.append(
            "Valoracion no extrema"
        )

    # ========================================================
    # DEBILIDADES
    # ========================================================

    if crecimiento[
        "clasificacion"
    ] in [
        "NEGATIVO",
        "DEBIL"
    ]:

        debilidades.append(
            "Crecimiento debil"
        )

    if rentabilidad[
        "clasificacion"
    ] in [
        "NEGATIVA",
        "BAJA"
    ]:

        debilidades.append(
            "Rentabilidad reducida"
        )

    if balance[
        "clasificacion"
    ] == "APALANCADO":

        debilidades.append(
            "Apalancamiento elevado"
        )

    if balance[
        "clasificacion"
    ] == "PATRIMONIO NEGATIVO":

        debilidades.append(
            "Patrimonio neto negativo"
        )

    if cash_flow[
        "clasificacion"
    ] == "NEGATIVO":

        debilidades.append(
            "Free cash flow negativo"
        )

    if valoracion[
        "clasificacion"
    ] in [
        "EXIGENTE",
        "MUY EXIGENTE"
    ]:

        debilidades.append(
            "Valoracion exigente"
        )

    # ========================================================
    # ALERTAS
    # ========================================================

    net_income = numero(
        fundamental.get(
            "net_income_ttm"
        )
    )

    fcf = numero(
        fundamental.get(
            "fcf_ttm"
        )
    )

    if (
        net_income is not None
        and net_income < 0
    ):

        alertas.append(
            "Beneficio neto TTM negativo"
        )

    if (
        fcf is not None
        and fcf < 0
    ):

        alertas.append(
            "FCF TTM negativo"
        )

    if balance[
        "clasificacion"
    ] == "PATRIMONIO NEGATIVO":

        alertas.append(
            "Patrimonio neto negativo"
        )

    pe = numero(
        fundamental.get(
            "pe_ttm"
        )
    )

    if (
        pe is not None
        and pe >= 50
    ):

        alertas.append(
            "P/E muy elevado"
        )

    ps = numero(
        fundamental.get(
            "ps_ttm"
        )
    )

    if (
        ps is not None
        and ps >= 15
    ):

        alertas.append(
            "P/S muy elevado"
        )

    # ========================================================
    # SCORE FUNDAMENTAL
    # ========================================================

    puntos = (

        crecimiento[
            "puntos"
        ]

        + rentabilidad[
            "puntos"
        ]

        + balance[
            "puntos"
        ]

        + cash_flow[
            "puntos"
        ]

        + valoracion[
            "puntos"
        ]
    )

    score_normalizado = round(
        (
            puntos
            / 20
        )
        * 100
    )

    if puntos >= 17:

        calidad = "EXCELENTE"

    elif puntos >= 13:

        calidad = "SOLIDA"

    elif puntos >= 9:

        calidad = "MIXTA"

    elif puntos >= 5:

        calidad = "DEBIL"

    else:

        calidad = "MUY DEBIL"

    return {

        "calidad_fundamental":
            calidad,

        "crecimiento":
            crecimiento[
                "clasificacion"
            ],

        "rentabilidad":
            rentabilidad[
                "clasificacion"
            ],

        "balance":
            balance[
                "clasificacion"
            ],

        "cash_flow":
            cash_flow[
                "clasificacion"
            ],

        "valoracion":
            valoracion[
                "clasificacion"
            ],

        "fortalezas":
            fortalezas,

        "debilidades":
            debilidades,

        "alertas":
            alertas,

        "score_fundamental":
            score_normalizado
    }


# ============================================================
# LECTURA HUMANA
# ============================================================

def generar_lectura(
    resultado
):

    calidad = resultado[
        "calidad_fundamental"
    ]

    crecimiento = resultado[
        "crecimiento"
    ]

    rentabilidad = resultado[
        "rentabilidad"
    ]

    balance = resultado[
        "balance"
    ]

    cash_flow = resultado[
        "cash_flow"
    ]

    valoracion = resultado[
        "valoracion"
    ]

    partes = []

    partes.append(
        (
            f"Calidad fundamental "
            f"{calidad.lower()}."
        )
    )

    if crecimiento not in [
        "NO EVALUABLE",
        "NO APLICABLE"
    ]:

        partes.append(
            (
                "El crecimiento se clasifica "
                f"como {crecimiento.lower()}."
            )
        )

    if rentabilidad not in [
        "NO EVALUABLE",
        "NO APLICABLE"
    ]:

        partes.append(
            (
                "La rentabilidad es "
                f"{rentabilidad.lower()}."
            )
        )

    if balance not in [
        "NO EVALUABLE"
    ]:

        partes.append(
            (
                "El balance se considera "
                f"{balance.lower()}."
            )
        )

    if cash_flow not in [
        "NO EVALUABLE",
        "NO APLICABLE"
    ]:

        partes.append(
            (
                "La generacion de caja se clasifica "
                f"como {cash_flow.lower()}."
            )
        )

    if valoracion not in [
        "NO EVALUABLE"
    ]:

        partes.append(
            (
                "La valoracion se clasifica "
                f"como {valoracion.lower()}."
            )
        )

    partes.append(
        (
            "Esta clasificacion sirve para priorizar "
            "investigacion y no determina por si sola "
            "si una accion debe comprarse."
        )
    )

    return " ".join(
        partes
    )


# ============================================================
# FUNCION PRINCIPAL
# ============================================================

def clasificar_fundamental(
    fundamental
):
    """
    Clasifica un snapshot de fundamental_analysis.

    No modifica el Score tecnico V3.
    """

    modelo = texto(
        fundamental.get(
            "model"
        ),
        "OPERATING"
    )

    if modelo == "BANK":

        resultado = clasificar_bank(
            fundamental
        )

    elif modelo == "FINANCIAL":

        resultado = clasificar_bank(
            fundamental
        )

    elif modelo == "BIOTECH_PRE_REVENUE":

        resultado = clasificar_biotech(
            fundamental
        )

    elif modelo == "REIT":

        resultado = {

            "calidad_fundamental":
                "PENDIENTE MODELO REIT",

            "crecimiento":
                "NO EVALUABLE",

            "rentabilidad":
                "NO EVALUABLE",

            "balance":
                "NO EVALUABLE",

            "cash_flow":
                "NO APLICABLE",

            "valoracion":
                "REQUIERE FFO/AFFO",

            "fortalezas":
                [],

            "debilidades":
                [],

            "alertas":
                [
                    (
                        "Pendiente incorporar "
                        "FFO/AFFO para REIT"
                    )
                ],

            "score_fundamental":
                0
        }

    else:

        resultado = clasificar_operating(
            fundamental
        )

    resultado[
        "symbol"
    ] = fundamental.get(
        "symbol"
    )

    resultado[
        "model"
    ] = modelo

    resultado[
        "lectura"
    ] = generar_lectura(
        resultado
    )

    return resultado