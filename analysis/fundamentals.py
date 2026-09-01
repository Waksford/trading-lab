import requests

from datetime import (
    datetime,
    date
)

from market.sectors import (
    SEC_HEADERS,
    obtener_mapa_sec,
    obtener_metadata_sec
)


# ============================================================
# CONFIGURACION
# ============================================================

COMPANY_FACTS_URL = (
    "https://data.sec.gov/api/xbrl/"
    "companyfacts/CIK{cik}.json"
)


# Un FY mas antiguo que esto se considera
# demasiado viejo para valorar la empresa.

MAX_ANTIGUEDAD_FY_DIAS = 550


_MAPA_SEC_CACHE = None


# ============================================================
# TAGS XBRL
# ============================================================

TAGS = {

    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet"
    ],

    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss"
    ],

    "operating_income": [
        "OperatingIncomeLoss"
    ],

    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
    ],

    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets"
    ],

    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],

    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
    ],

    "debt_current": [
        "LongTermDebtCurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "ShortTermBorrowings"
    ],

    "debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent"
    ],

    "shares": [
        "EntityCommonStockSharesOutstanding"
    ],
    "weighted_shares": [
        "WeightedAverageNumberOfSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding"
    ]
}


# ============================================================
# FECHAS
# ============================================================

def parse_fecha(
    valor
):

    if not valor:
        return None

    try:

        return datetime.strptime(
            valor,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return None


def dias_entre(
    inicio,
    fin
):

    inicio = parse_fecha(
        inicio
    )

    fin = parse_fecha(
        fin
    )


    if (
        inicio is None
        or fin is None
    ):

        return None


    return (
        fin
        - inicio
    ).days


def antiguedad_dias(
    fecha
):

    fecha = parse_fecha(
        fecha
    )


    if fecha is None:

        return None


    return (
        date.today()
        - fecha
    ).days


# ============================================================
# CIK
# ============================================================

def obtener_cik(
    symbol
):

    global _MAPA_SEC_CACHE


    if _MAPA_SEC_CACHE is None:

        _MAPA_SEC_CACHE = (
            obtener_mapa_sec()
        )


    info = _MAPA_SEC_CACHE.get(
        symbol.upper()
    )


    if not info:

        return None


    return info[
        "cik"
    ]


# ============================================================
# COMPANY FACTS
# ============================================================

def descargar_companyfacts(
    cik
):

    url = (
        COMPANY_FACTS_URL.format(
            cik=cik
        )
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30
    )

    if response.status_code == 404:

        return None

    response.raise_for_status()

    return response.json()
# ============================================================
# FACT
# ============================================================

def obtener_fact(
    datos,
    tag,
    taxonomy="us-gaap"
):

    return (
        datos
        .get(
            "facts",
            {}
        )
        .get(
            taxonomy,
            {}
        )
        .get(
            tag
        )
    )


# ============================================================
# REGISTROS DE VARIOS TAGS
# ============================================================

def obtener_registros(
    datos,
    tags,
    unidades=("USD",),
    taxonomy="us-gaap"
):
    """
    Junta todos los registros de todos los tags
    equivalentes.

    Esto evita el problema anterior:
    escoger un tag viejo solo porque aparecia primero.
    """

    registros = []


    for prioridad_tag, tag in enumerate(
        tags
    ):

        fact = obtener_fact(
            datos,
            tag,
            taxonomy=taxonomy
        )


        if not fact:
            continue


        units = fact.get(
            "units",
            {}
        )


        valores = None

        unidad_usada = None


        for unidad in unidades:

            if unidad in units:

                valores = units[
                    unidad
                ]

                unidad_usada = unidad

                break


        if valores is None:

            continue


        for registro in valores:

            nuevo = dict(
                registro
            )

            nuevo[
                "_tag"
            ] = tag

            nuevo[
                "_tag_priority"
            ] = prioridad_tag

            nuevo[
                "_unit"
            ] = unidad_usada


            registros.append(
                nuevo
            )


    return registros


# ============================================================
# DURACION DE UN FACT
# ============================================================

def duracion_registro(
    registro
):

    return dias_entre(
        registro.get(
            "start"
        ),
        registro.get(
            "end"
        )
    )


# ============================================================
# DEDUPLICAR POR FECHA FINAL
# ============================================================
def deduplicar_por_end(
    registros
):
    """
    Deduplica registros que terminan en la misma fecha.

    Prioridad:
    1. end mas reciente
    2. filing mas reciente
    3. tag preferido segun el orden de TAGS
    """

    por_end = {}


    for registro in registros:

        end = registro.get(
            "end"
        )

        if not end:
            continue


        anterior = por_end.get(
            end
        )


        if anterior is None:

            por_end[
                end
            ] = registro

            continue


        filed_actual = registro.get(
            "filed",
            ""
        )

        filed_anterior = anterior.get(
            "filed",
            ""
        )


        prioridad_actual = registro.get(
            "_tag_priority",
            999
        )

        prioridad_anterior = anterior.get(
            "_tag_priority",
            999
        )


        # Filing mas reciente gana.
        if filed_actual > filed_anterior:

            por_end[
                end
            ] = registro

            continue


        # Si el filing es el mismo,
        # preferimos el tag con menor prioridad numerica.
        if (
            filed_actual == filed_anterior
            and prioridad_actual < prioridad_anterior
        ):

            por_end[
                end
            ] = registro


    return sorted(

        por_end.values(),

        key=lambda x:
            x.get(
                "end",
                ""
            ),

        reverse=True
    )

# ============================================================
# DATOS ANUALES
# ============================================================

def obtener_periodos_anuales(
    datos,
    tags
):
    """
    Busca ejercicios fiscales anuales entre TODOS
    los tags compatibles.

    Evita quedarse con un tag antiguo simplemente
    porque aparece primero en TAGS.
    """

    registros = obtener_registros(

        datos,

        tags,

        unidades=(
            "USD",
        )
    )


    validos = []


    for registro in registros:

        # ----------------------------------------------------
        # Valor obligatorio
        # ----------------------------------------------------

        if registro.get(
            "val"
        ) is None:

            continue


        # ----------------------------------------------------
        # Solo 10-K
        # ----------------------------------------------------

        if registro.get(
            "form"
        ) not in [
            "10-K",
            "10-K/A"
        ]:

            continue


        # ----------------------------------------------------
        # Si SEC marca fiscal period,
        # debe ser FY.
        #
        # Algunos registros antiguos pueden no traer fp,
        # por eso permitimos None.
        # ----------------------------------------------------

        if registro.get(
            "fp"
        ) not in [
            "FY",
            None
        ]:

            continue


        # ----------------------------------------------------
        # Debe existir start/end
        # ----------------------------------------------------

        duracion = (
            duracion_registro(
                registro
            )
        )


        if duracion is None:

            continue


        # ----------------------------------------------------
        # Ejercicio anual razonable
        #
        # Incluimos fiscal years de 52/53 semanas.
        # ----------------------------------------------------

        if not (
            300
            <= duracion
            <= 430
        ):

            continue


        validos.append(
            registro
        )


    # Esto devuelve SIEMPRE primero
    # el end mas reciente.
    return deduplicar_por_end(
        validos
    )

# ============================================================
# METRICA FY
# ============================================================

def obtener_metrica_fy(
    datos,
    tags
):

    registros = (
        obtener_periodos_anuales(
            datos,
            tags
        )
    )


    if not registros:

        return {

            "actual":
                None,

            "anterior":
                None,

            "fecha_actual":
                None,

            "fecha_anterior":
                None,

            "tag":
                None
        }


    actual = registros[
        0
    ]


    anterior = (

        registros[
            1
        ]

        if len(
            registros
        ) > 1

        else None
    )


    return {

        "actual":
            actual.get(
                "val"
            ),

        "anterior":
            (
                anterior.get(
                    "val"
                )

                if anterior

                else None
            ),

        "fecha_actual":
            actual.get(
                "end"
            ),

        "fecha_anterior":
            (
                anterior.get(
                    "end"
                )

                if anterior

                else None
            ),

        "tag":
            actual.get(
                "_tag"
            )
    }

# ============================================================
# PERIODOS TRIMESTRALES / YTD
# ============================================================

def obtener_periodos_trimestrales(
    datos,
    tags
):
    """
    Obtiene todos los periodos 10-Q validos para construir TTM.

    Incluye:
    - trimestre individual (~90 dias)
    - Q2 acumulado / YTD (~180 dias)
    - Q3 acumulado / YTD (~270 dias)

    Deduplica registros equivalentes conservando la mejor
    version disponible para cada periodo.
    """

    registros = obtener_registros(
        datos,
        tags,
        unidades=("USD",)
    )

    validos = []

    for registro in registros:

        if registro.get("val") is None:
            continue

        if registro.get("form") not in [
            "10-Q",
            "10-Q/A"
        ]:
            continue

        if (
            not registro.get("start")
            or not registro.get("end")
        ):
            continue

        duracion = duracion_registro(
            registro
        )

        if duracion is None:
            continue

        # Q1 / quarter-only ~90 días
        # Q2 YTD ~180 días
        # Q3 YTD ~270 días
        if not (
            60 <= duracion <= 300
        ):
            continue

        validos.append(
            registro
        )

    # --------------------------------------------------------
    # DEDUPLICACION
    #
    # No podemos deduplicar solo por END porque para una misma
    # fecha SEC puede contener:
    #
    #   Q3 individual -> ~90 dias
    #   Q3 YTD        -> ~270 dias
    #
    # y necesitamos conservar ambos.
    # --------------------------------------------------------

    unicos = {}

    for registro in validos:

        clave = (
            registro.get("start"),
            registro.get("end"),
            registro.get("val")
        )

        anterior = unicos.get(
            clave
        )

        if anterior is None:

            unicos[clave] = registro
            continue

        filed_actual = registro.get(
            "filed",
            ""
        )

        filed_anterior = anterior.get(
            "filed",
            ""
        )

        prioridad_actual = registro.get(
            "_tag_priority",
            999
        )

        prioridad_anterior = anterior.get(
            "_tag_priority",
            999
        )

        if filed_actual > filed_anterior:

            unicos[clave] = registro

        elif (
            filed_actual == filed_anterior
            and prioridad_actual < prioridad_anterior
        ):

            unicos[clave] = registro

    return sorted(
        unicos.values(),
        key=lambda x: (
            x.get("end", ""),
            duracion_registro(x) or 0,
            x.get("filed", "")
        ),
        reverse=True
    )


# ============================================================
# BUSCAR YTD ACTUAL
# ============================================================

def buscar_ytd_actual(
    datos,
    tags,
    fecha_fy
):
    """
    Busca el YTD mas reciente posterior
    al ultimo FY.

    Para Q2/Q3 preferimos el periodo acumulado
    mas largo terminado en la fecha mas reciente.
    """

    fecha_fy_date = parse_fecha(
        fecha_fy
    )


    if fecha_fy_date is None:

        return None


    registros = obtener_registros(

        datos,

        tags,

        unidades=(
            "USD",
        )
    )


    candidatos = []


    for registro in registros:

        if registro.get(
            "form"
        ) not in [
            "10-Q",
            "10-Q/A"
        ]:

            continue


        if registro.get(
            "val"
        ) is None:

            continue


        end = parse_fecha(
            registro.get(
                "end"
            )
        )


        if (
            end is None
            or end
            <= fecha_fy_date
        ):

            continue


        duracion = (
            duracion_registro(
                registro
            )
        )


        if duracion is None:

            continue


        # Q1 -> ~90 dias
        # Q2 YTD -> ~180
        # Q3 YTD -> ~270

        if not (
            60
            <= duracion
            <= 300
        ):

            continue


        candidatos.append(
            registro
        )


    if not candidatos:

        return None


    # Primero fecha final mas reciente.
    ultima_fecha = max(
        registro[
            "end"
        ]
        for registro in candidatos
    )


    misma_fecha = [

        registro

        for registro in candidatos

        if registro[
            "end"
        ] == ultima_fecha
    ]


    # Si existen quarter-only y YTD,
    # elegimos el YTD mas largo.

    return max(

        misma_fecha,

        key=lambda x: (
            duracion_registro(
                x
            )
            or 0
        )
    )


# ============================================================
# YTD COMPARABLE ANTERIOR
# ============================================================

def buscar_ytd_comparable(
    datos,
    tags,
    actual
):
    """
    Busca el YTD comparable del ejercicio anterior.

    Preferimos un registro perteneciente
    al mismo filing/accession.
    """

    if actual is None:

        return None


    registros = obtener_registros(

        datos,

        tags,

        unidades=(
            "USD",
        )
    )


    fecha_actual = parse_fecha(
        actual.get(
            "end"
        )
    )


    duracion_actual = (
        duracion_registro(
            actual
        )
    )


    if (
        fecha_actual is None
        or duracion_actual is None
    ):

        return None


    accession = actual.get(
        "accn"
    )


    candidatos = []


    for registro in registros:

        if registro.get(
            "val"
        ) is None:

            continue


        end = parse_fecha(
            registro.get(
                "end"
            )
        )


        if end is None:

            continue


        diferencia = (
            fecha_actual
            - end
        ).days


        # Aproximadamente un ano antes.

        if not (
            330
            <= diferencia
            <= 400
        ):

            continue


        duracion = (
            duracion_registro(
                registro
            )
        )


        if duracion is None:

            continue


        if abs(
            duracion
            - duracion_actual
        ) > 25:

            continue


        puntuacion = 0


        if (
            accession
            and registro.get(
                "accn"
            ) == accession
        ):

            puntuacion += 100


        if registro.get(
            "_tag"
        ) == actual.get(
            "_tag"
        ):

            puntuacion += 20


        puntuacion -= abs(
            365
            - diferencia
        )


        candidatos.append(
            (
                puntuacion,
                registro
            )
        )


    if not candidatos:

        return None


    candidatos.sort(

        key=lambda x:
            x[0],

        reverse=True
    )


    return candidatos[
        0
    ][
        1
    ]


# ============================================================
# TTM
# ============================================================

def calcular_ttm(
    datos,
    tags
):
    """
    Calcula TTM con una jerarquia distinta segun
    la antiguedad del ultimo FY.

    CASO NORMAL:
        FY + YTD actual - YTD comparable anterior

    CASO FY ENVEJECIDO:
        primero intenta reconstruir:
            YTD + siguiente trimestre

        y solo si eso falla:
            FY + YTD actual - YTD comparable anterior

    FALLBACK FINAL:
        FY
    """

    # ========================================================
    # FY
    # ========================================================

    fy = obtener_metrica_fy(
        datos,
        tags
    )


    if fy[
        "actual"
    ] is None:

        return {
            "valor": None,
            "metodo": "NO_DATA",
            "fecha": None,
            "fy": None,
            "ytd_actual": None,
            "ytd_anterior": None
        }


    fy_valor = float(
        fy[
            "actual"
        ]
    )


    fy_fecha = fy[
        "fecha_actual"
    ]


    antiguedad = antiguedad_dias(
        fy_fecha
    )


    # ========================================================
    # HELPER INTERNO:
    # FY + YTD - YTD ANTERIOR
    # ========================================================

    def intentar_fy_plus_ytd():

        ytd_actual = buscar_ytd_actual(
            datos,
            tags,
            fy_fecha
        )


        if ytd_actual is None:

            return None


        ytd_anterior = buscar_ytd_comparable(
            datos,
            tags,
            ytd_actual
        )


        if ytd_anterior is None:

            return None


        try:

            valor = (

                fy_valor

                + float(
                    ytd_actual[
                        "val"
                    ]
                )

                - float(
                    ytd_anterior[
                        "val"
                    ]
                )
            )


            return {

                "valor":
                    valor,

                "metodo":
                    "FY_PLUS_YTD",

                "fecha":
                    ytd_actual.get(
                        "end"
                    ),

                "fy":
                    fy_valor,

                "ytd_actual":
                    ytd_actual.get(
                        "val"
                    ),

                "ytd_anterior":
                    ytd_anterior.get(
                        "val"
                    )
            }


        except (
            TypeError,
            ValueError
        ):

            return None


    # ========================================================
    # HELPER INTERNO:
    # YTD + SIGUIENTE TRIMESTRE
    # ========================================================

    def intentar_ytd_plus_next_quarter():

        trimestrales = (
            obtener_periodos_trimestrales(
                datos,
                tags
            )
        )


        posteriores = [

            registro

            for registro in trimestrales

            if (
                registro.get(
                    "end"
                )

                and fy_fecha

                and registro.get(
                    "end"
                ) > fy_fecha
            )
        ]


        candidatos_ytd = []


        for registro in posteriores:

            duracion = (
                duracion_registro(
                    registro
                )
            )


            if (
                duracion is not None

                and

                170
                <= duracion
                <= 300

                and

                registro.get(
                    "val"
                )
                is not None
            ):

                candidatos_ytd.append(
                    registro
                )


        candidatos_q = []


        for registro in posteriores:

            duracion = (
                duracion_registro(
                    registro
                )
            )


            if (
                duracion is not None

                and

                70
                <= duracion
                <= 110

                and

                registro.get(
                    "val"
                )
                is not None
            ):

                candidatos_q.append(
                    registro
                )


        mejor = None


        for ytd in candidatos_ytd:

            ytd_end = ytd.get(
                "end"
            )


            if not ytd_end:

                continue


            for trimestre in candidatos_q:

                q_start = trimestre.get(
                    "start"
                )

                q_end = trimestre.get(
                    "end"
                )


                if (
                    not q_start
                    or not q_end
                ):

                    continue


                if q_start <= ytd_end:

                    continue


                try:

                    fecha_ytd = (
                        datetime.strptime(
                            ytd_end,
                            "%Y-%m-%d"
                        )
                    )


                    fecha_q_start = (
                        datetime.strptime(
                            q_start,
                            "%Y-%m-%d"
                        )
                    )


                    hueco = (
                        fecha_q_start
                        - fecha_ytd
                    ).days


                    if not (
                        1
                        <= hueco
                        <= 110
                    ):

                        continue


                    valor = (

                        float(
                            ytd[
                                "val"
                            ]
                        )

                        + float(
                            trimestre[
                                "val"
                            ]
                        )
                    )


                    candidato = {

                        "valor":
                            valor,

                        "metodo":
                            "YTD_PLUS_NEXT_QUARTER",

                        "fecha":
                            q_end,

                        "fy":
                            fy_valor,

                        "ytd_actual":
                            ytd.get(
                                "val"
                            ),

                        "ytd_anterior":
                            None
                    }


                    if (
                        mejor is None

                        or

                        q_end
                        > mejor[
                            "fecha"
                        ]
                    ):

                        mejor = (
                            candidato
                        )


                except (
                    TypeError,
                    ValueError
                ):

                    continue


        return mejor


    # ========================================================
    # CASO 1:
    # FY ENVEJECIDO
    #
    # Primero intentamos reconstruir usando
    # YTD + siguiente trimestre.
    # ========================================================

    if (
        antiguedad is not None
        and antiguedad >= 400
    ):

        reconstruido = (
            intentar_ytd_plus_next_quarter()
        )


        if reconstruido is not None:

            return reconstruido


        normal = (
            intentar_fy_plus_ytd()
        )


        if normal is not None:

            return normal


    # ========================================================
    # CASO 2:
    # FY NORMAL
    #
    # Metodo preferido:
    # FY + YTD - YTD comparable.
    # ========================================================

    else:

        normal = (
            intentar_fy_plus_ytd()
        )


        if normal is not None:

            return normal


    # ========================================================
    # FALLBACK FINAL
    # ========================================================

    return {

        "valor":
            fy_valor,

        "metodo":
            "FY",

        "fecha":
            fy_fecha,

        "fy":
            fy_valor,

        "ytd_actual":
            None,

        "ytd_anterior":
            None
    }
# ============================================================
# INSTANTANEO RECIENTE
# ============================================================

def obtener_ultimo_instantaneo(
    datos,
    tags,
    unidades=("USD",),
    taxonomy="us-gaap"
):

    registros = obtener_registros(

        datos,

        tags,

        unidades=unidades,

        taxonomy=taxonomy
    )


    validos = []


    for registro in registros:

        if registro.get(
            "val"
        ) is None:

            continue


        if registro.get(
            "form"
        ) not in [
            "10-K",
            "10-K/A",
            "10-Q",
            "10-Q/A",
            "20-F",
            "40-F"
        ]:

            continue


        if not registro.get(
            "end"
        ):

            continue


        validos.append(
            registro
        )


    if not validos:

        return {

            "valor":
                None,

            "fecha":
                None,

            "tag":
                None
        }


    validos.sort(

        key=lambda x: (

            x.get(
                "end",
                ""
            ),

            x.get(
                "filed",
                ""
            )
        ),

        reverse=True
    )


    ultimo = validos[
        0
    ]


    return {

        "valor":
            ultimo.get(
                "val"
            ),

        "fecha":
            ultimo.get(
                "end"
            ),

        "tag":
            ultimo.get(
                "_tag"
            )
    }


def obtener_acciones_outstanding(
    datos
):
    """
    Obtiene las acciones utilizadas para estimar market cap.

    Estrategia:

    1. Intentar EntityCommonStockSharesOutstanding
       desde taxonomy DEI.

    2. Si hay un unico valor reciente, usarlo.

    3. Si existen multiples clases / valores ambiguos,
       usar WeightedAverageNumberOfSharesOutstanding
       como fallback.

    No sumamos clases automaticamente porque SEC puede
    contener tanto el total como los valores por clase,
    lo que produciria doble conteo.
    """

    # ========================================================
    # 1. DEI - SHARES OUTSTANDING
    # ========================================================

    registros = obtener_registros(

        datos,

        TAGS[
            "shares"
        ],

        unidades=(
            "shares",
        ),

        taxonomy="dei"
    )


    validos = []


    for registro in registros:

        if registro.get(
            "val"
        ) is None:

            continue


        if registro.get(
            "form"
        ) not in [
            "10-K",
            "10-K/A",
            "10-Q",
            "10-Q/A"
        ]:

            continue


        if not registro.get(
            "end"
        ):

            continue


        validos.append(
            registro
        )


    if validos:

        fecha_mas_reciente = max(

            registro[
                "end"
            ]

            for registro in validos
        )


        misma_fecha = [

            registro

            for registro in validos

            if registro[
                "end"
            ] == fecha_mas_reciente
        ]


        valores = sorted(
            {
                float(
                    registro[
                        "val"
                    ]
                )

                for registro in misma_fecha

                if registro.get(
                    "val"
                ) is not None
            }
        )


        # Si SEC da un unico total claro,
        # lo usamos.
        if len(
            valores
        ) == 1:

            return {

                "valor":
                    valores[
                        0
                    ],

                "fecha":
                    fecha_mas_reciente,

                "metodo":
                    "DEI_OUTSTANDING"
            }


    # ========================================================
    # 2. FALLBACK WEIGHTED AVERAGE SHARES
    # ========================================================

    registros_weighted = obtener_registros(

        datos,

        TAGS[
            "weighted_shares"
        ],

        unidades=(
            "shares",
        ),

        taxonomy="us-gaap"
    )


    candidatos = []


    for registro in registros_weighted:

        if registro.get(
            "val"
        ) is None:

            continue


        if registro.get(
            "form"
        ) not in [
            "10-K",
            "10-K/A",
            "10-Q",
            "10-Q/A"
        ]:

            continue


        if not registro.get(
            "end"
        ):

            continue


        duracion = (
            duracion_registro(
                registro
            )
        )


        if duracion is None:

            continue


        # Preferimos periodos suficientemente representativos.
        if not (
            60
            <= duracion
            <= 430
        ):

            continue


        candidatos.append(
            registro
        )


    if candidatos:

        candidatos.sort(

            key=lambda x: (

                x.get(
                    "end",
                    ""
                ),

                x.get(
                    "filed",
                    ""
                ),

                # Ante empate preferimos
                # basic frente a diluted,
                # porque aparece primero en TAGS.
                -x.get(
                    "_tag_priority",
                    999
                )
            ),

            reverse=True
        )


        elegido = candidatos[
            0
        ]


        return {

            "valor":
                float(
                    elegido[
                        "val"
                    ]
                ),

            "fecha":
                elegido.get(
                    "end"
                ),

            "metodo":
                "WEIGHTED_AVERAGE"
        }


    # ========================================================
    # NO DATA
    # ========================================================

    return {

        "valor":
            None,

        "fecha":
            None,

        "metodo":
            "NO_DATA"
    }

# ============================================================
# CALCULOS
# ============================================================

def ratio(
    numerador,
    denominador
):

    if (
        numerador is None
        or denominador is None
        or denominador == 0
    ):

        return None


    return (
        numerador
        / denominador
    )


def porcentaje(
    numerador,
    denominador
):

    resultado = ratio(
        numerador,
        denominador
    )


    if resultado is None:

        return None


    return (
        resultado
        * 100
    )


def crecimiento(
    actual,
    anterior
):

    if (
        actual is None
        or anterior is None
        or anterior == 0
    ):

        return None


    return (
        (
            actual
            / anterior
        )
        - 1
    ) * 100


# ============================================================
# MODELO FUNDAMENTAL
# ============================================================

def clasificar_modelo_fundamental(
    sic,
    sector,
    revenue_ttm,
    net_income_ttm
):

    try:

        sic_int = int(
            sic
        )

    except (
        TypeError,
        ValueError
    ):

        sic_int = None


    # ========================================================
    # REIT
    # ========================================================

    if sic_int == 6798:

        return "REIT"


    # ========================================================
    # BANK
    # ========================================================

    if sic_int is not None:

        if (
            6020
            <= sic_int
            <= 6099
        ):

            return "BANK"


        if (
            6140
            <= sic_int
            <= 6163
        ):

            return "BANK"


    # ========================================================
    # OTRAS FINANCIERAS
    # ========================================================

    if sector == "Financials":

        return "FINANCIAL"


    # ========================================================
    # BIOTECH PRE-REVENUE
    # ========================================================

    if (
        sic_int
        in [
            2834,
            2835,
            2836
        ]
    ):

        ingresos_bajos = (

            revenue_ttm is None

            or

            revenue_ttm
            < 25_000_000
        )


        pierde_dinero = (

            net_income_ttm is None

            or

            net_income_ttm
            < 0
        )


        if (
            ingresos_bajos
            and pierde_dinero
        ):

            return (
                "BIOTECH_PRE_REVENUE"
            )


    return "OPERATING"


# ============================================================
# ANALISIS FUNDAMENTAL
# ============================================================

def analizar_fundamentales(
    symbol,
    precio=None
):

    symbol = symbol.upper()


    cik = obtener_cik(
        symbol
    )


    if not cik:

        return {

            "symbol":
                symbol,

            "error":
                "CIK_SEC_NO_ENCONTRADO"
        }


    # ========================================================
    # SEC
    # ========================================================

    datos = descargar_companyfacts(
        cik
    )
    if datos is None:

        return {

            "symbol":
                symbol,

            "cik":
                cik,

            "error":
                "COMPANYFACTS_NO_DISPONIBLE"
        }

    metadata = obtener_metadata_sec(
        cik
    )


    sic = metadata.get(
        "sic"
    )


    sic_description = metadata.get(
        "sic_description"
    )


    sector = metadata.get(
        "sector",
        "Unknown"
    )


    # ========================================================
    # FY
    # ========================================================

    revenue_fy = obtener_metrica_fy(

        datos,

        TAGS[
            "revenue"
        ]
    )


    net_income_fy = obtener_metrica_fy(

        datos,

        TAGS[
            "net_income"
        ]
    )


    operating_income_fy = (
        obtener_metrica_fy(

            datos,

            TAGS[
                "operating_income"
            ]
        )
    )


    cfo_fy = obtener_metrica_fy(

        datos,

        TAGS[
            "operating_cash_flow"
        ]
    )


    capex_fy = obtener_metrica_fy(

        datos,

        TAGS[
            "capex"
        ]
    )


    # ========================================================
    # FECHA FY DE REFERENCIA
    # ========================================================

    fechas_fy = [

        revenue_fy[
            "fecha_actual"
        ],

        net_income_fy[
            "fecha_actual"
        ]
    ]


    fechas_fy = [

        fecha

        for fecha in fechas_fy

        if fecha
    ]


    fecha_fy = (

        max(
            fechas_fy
        )

        if fechas_fy

        else None
    )


    # ========================================================
    # RECHAZAR DATOS DEMASIADO ANTIGUOS
    # ========================================================

    antiguedad_fy = (
        antiguedad_dias(
            fecha_fy
        )
    )


    if (
        antiguedad_fy is not None

        and

        antiguedad_fy
        > MAX_ANTIGUEDAD_FY_DIAS
    ):

        return {

            "symbol":
                symbol,

            "cik":
                cik,

            "nombre_sec":
                datos.get(
                    "entityName"
                ),

            "sic":
                sic,

            "sector":
                sector,

            "fecha_fy":
                fecha_fy,

            "antiguedad_fy_dias":
                antiguedad_fy,

            "error":
                "FUNDAMENTALES_DEMASIADO_ANTIGUOS"
        }


    # ========================================================
    # TTM
    # ========================================================

    revenue_ttm = calcular_ttm(

        datos,

        TAGS[
            "revenue"
        ]
    )


    net_income_ttm = calcular_ttm(

        datos,

        TAGS[
            "net_income"
        ]
    )


    operating_income_ttm = (
        calcular_ttm(

            datos,

            TAGS[
                "operating_income"
            ]
        )
    )


    cfo_ttm = calcular_ttm(

        datos,

        TAGS[
            "operating_cash_flow"
        ]
    )


    capex_ttm = calcular_ttm(

        datos,

        TAGS[
            "capex"
        ]
    )


    # ========================================================
    # BALANCE
    # ========================================================

    cash = obtener_ultimo_instantaneo(

        datos,

        TAGS[
            "cash"
        ]
    )


    equity = obtener_ultimo_instantaneo(

        datos,

        TAGS[
            "equity"
        ]
    )


    debt_current = obtener_ultimo_instantaneo(

        datos,

        TAGS[
            "debt_current"
        ]
    )


    debt_noncurrent = obtener_ultimo_instantaneo(

        datos,

        TAGS[
            "debt_noncurrent"
        ]
    )


    # ========================================================
    # SHARES
    # ========================================================

    shares = obtener_acciones_outstanding(
        datos
    )

    # ========================================================
    # DEUDA
    # ========================================================

    componentes_deuda = [

        debt_current[
            "valor"
        ],

        debt_noncurrent[
            "valor"
        ]
    ]


    componentes_deuda = [

        valor

        for valor in componentes_deuda

        if valor is not None
    ]


    deuda_total = (

        sum(
            componentes_deuda
        )

        if componentes_deuda

        else None
    )


    # ========================================================
    # FREE CASH FLOW FY
    # ========================================================

    fcf_fy = None


    if (
        cfo_fy[
            "actual"
        ] is not None

        and

        capex_fy[
            "actual"
        ] is not None
    ):

        fcf_fy = (

            cfo_fy[
                "actual"
            ]

            - abs(
                capex_fy[
                    "actual"
                ]
            )
        )


    # ========================================================
    # FREE CASH FLOW TTM
    # ========================================================

    fcf_ttm = None


    if (
        cfo_ttm[
            "valor"
        ] is not None

        and

        capex_ttm[
            "valor"
        ] is not None
    ):

        fcf_ttm = (

            cfo_ttm[
                "valor"
            ]

            - abs(
                capex_ttm[
                    "valor"
                ]
            )
        )


    # ========================================================
    # MODELO
    # ========================================================

    modelo = (
        clasificar_modelo_fundamental(

            sic,

            sector,

            revenue_ttm[
                "valor"
            ],

            net_income_ttm[
                "valor"
            ]
        )
    )


    # ========================================================
    # MARKET CAP
    # ========================================================

    market_cap = None


    if (
        precio is not None

        and

        shares[
            "valor"
        ] is not None
    ):

        market_cap = (

            precio

            * shares[
                "valor"
            ]
        )


    # ========================================================
    # CRECIMIENTO FY
    # ========================================================

    revenue_growth_fy = crecimiento(

        revenue_fy[
            "actual"
        ],

        revenue_fy[
            "anterior"
        ]
    )


    net_income_growth_fy = crecimiento(

        net_income_fy[
            "actual"
        ],

        net_income_fy[
            "anterior"
        ]
    )


    # ========================================================
    # MARGENES TTM
    # ========================================================

    net_margin_ttm = porcentaje(

        net_income_ttm[
            "valor"
        ],

        revenue_ttm[
            "valor"
        ]
    )


    operating_margin_ttm = porcentaje(

        operating_income_ttm[
            "valor"
        ],

        revenue_ttm[
            "valor"
        ]
    )


    # ========================================================
    # VALORACION GENERAL
    # ========================================================

    pe_ttm = None

    pe_status = "N/A"


    if (
        market_cap is not None

        and

        net_income_ttm[
            "valor"
        ] is not None
    ):

        if (
            net_income_ttm[
                "valor"
            ] > 0
        ):

            pe_ttm = ratio(

                market_cap,

                net_income_ttm[
                    "valor"
                ]
            )

            pe_status = "OK"

        else:

            # Punto 3:
            # nunca mostrar P/E negativo.

            pe_status = "N/M"


    ps_ttm = None


    if (
        market_cap is not None

        and

        revenue_ttm[
            "valor"
        ] not in [
            None,
            0
        ]
    ):

        ps_ttm = ratio(

            market_cap,

            revenue_ttm[
                "valor"
            ]
        )


    pb = ratio(

        market_cap,

        equity[
            "valor"
        ]
    )


    fcf_yield = porcentaje(

        fcf_ttm,

        market_cap
    )


    # ========================================================
    # MODELO OPERATING
    # ========================================================

    debt_to_equity = None


    if modelo == "OPERATING":

        debt_to_equity = ratio(

            deuda_total,

            equity[
                "valor"
            ]
        )


    # ========================================================
    # BANK / FINANCIAL
    # ========================================================

    roe_aprox = None


    if modelo in [
        "BANK",
        "FINANCIAL"
    ]:

        roe_aprox = porcentaje(

            net_income_ttm[
                "valor"
            ],

            equity[
                "valor"
            ]
        )


        # FCF y deuda no se interpretan
        # con el modelo industrial.

        fcf_yield = None

        debt_to_equity = None

        ps_ttm = None


    # ========================================================
    # REIT
    # ========================================================

    if modelo == "REIT":

        # Para REIT queremos FFO/AFFO.
        # No usamos P/E/FCF como valuation final.

        pe_ttm = None
        pe_status = "NO_APLICABLE_REIT"

        ps_ttm = None
        fcf_yield = None
        debt_to_equity = None


    # ========================================================
    # BIOTECH PRE-REVENUE
    # ========================================================

    cash_burn = None

    cash_runway_years = None

    cash_to_market_cap = None


    if (
        modelo
        == "BIOTECH_PRE_REVENUE"
    ):

        pe_ttm = None
        pe_status = "N/M"

        ps_ttm = None

        fcf_yield = None

        debt_to_equity = None


        if (
            cfo_ttm[
                "valor"
            ] is not None

            and

            cfo_ttm[
                "valor"
            ] < 0
        ):

            cash_burn = abs(
                cfo_ttm[
                    "valor"
                ]
            )


        if (
            cash[
                "valor"
            ] is not None

            and

            cash_burn
            not in [
                None,
                0
            ]
        ):

            cash_runway_years = (

                cash[
                    "valor"
                ]

                / cash_burn
            )


        cash_to_market_cap = porcentaje(

            cash[
                "valor"
            ],

            market_cap
        )


    # ========================================================
    # FECHA MAS RECIENTE
    # ========================================================

    fechas = [

        revenue_ttm[
            "fecha"
        ],

        net_income_ttm[
            "fecha"
        ],

        cash[
            "fecha"
        ],

        equity[
            "fecha"
        ]
    ]


    fechas = [

        fecha

        for fecha in fechas

        if fecha
    ]


    fecha_referencia = (

        max(
            fechas
        )

        if fechas

        else fecha_fy
    )


    # ========================================================
    # NOTAS DEL MODELO
    # ========================================================

    if modelo == "OPERATING":

        nota_modelo = (
            "Modelo operativo general: crecimiento, "
            "margenes, FCF, deuda y valoracion TTM."
        )


    elif modelo == "BANK":

        nota_modelo = (
            "Modelo bancario: se priorizan P/E, P/B "
            "y ROE aproximado. FCF y deuda industrial "
            "no se utilizan."
        )


    elif modelo == "FINANCIAL":

        nota_modelo = (
            "Modelo financiero: se priorizan beneficio, "
            "P/E, P/B y ROE. El modelo industrial de "
            "deuda y FCF no es aplicable."
        )


    elif modelo == "REIT":

        nota_modelo = (
            "Modelo REIT: P/E y FCF industrial no se "
            "consideran validos. FFO/AFFO se incorporara "
            "como metrica principal."
        )


    else:

        nota_modelo = (
            "Modelo biotech pre-revenue: se priorizan "
            "caja, cash burn y runway. P/E y P/S no son "
            "metricas principales."
        )


    # ========================================================
    # RETURN
    # ========================================================

    return {

        "symbol":
            symbol,

        "cik":
            cik,

        "nombre_sec":
            datos.get(
                "entityName"
            ),

        "sic":
            sic,

        "sic_description":
            sic_description,

        "sector":
            sector,

        "modelo":
            modelo,

        "nota_modelo":
            nota_modelo,

        # ----------------------------------------------------
        # CALIDAD TEMPORAL
        # ----------------------------------------------------

        "fecha_fy":
            fecha_fy,

        "antiguedad_fy_dias":
            antiguedad_fy,

        "fecha_referencia":
            fecha_referencia,

        # ----------------------------------------------------
        # FY
        # ----------------------------------------------------

        "revenue_fy":
            revenue_fy[
                "actual"
            ],

        "revenue_previous_fy":
            revenue_fy[
                "anterior"
            ],

        "revenue_growth_fy":
            revenue_growth_fy,

        "net_income_fy":
            net_income_fy[
                "actual"
            ],

        "net_income_previous_fy":
            net_income_fy[
                "anterior"
            ],

        "net_income_growth_fy":
            net_income_growth_fy,

        "operating_income_fy":
            operating_income_fy[
                "actual"
            ],

        "cfo_fy":
            cfo_fy[
                "actual"
            ],

        "capex_fy":
            capex_fy[
                "actual"
            ],

        "fcf_fy":
            fcf_fy,

        # ----------------------------------------------------
        # TTM
        # ----------------------------------------------------

        "revenue_ttm":
            revenue_ttm[
                "valor"
            ],

        "revenue_ttm_method":
            revenue_ttm[
                "metodo"
            ],

        "net_income_ttm":
            net_income_ttm[
                "valor"
            ],

        "net_income_ttm_method":
            net_income_ttm[
                "metodo"
            ],

        "operating_income_ttm":
            operating_income_ttm[
                "valor"
            ],

        "cfo_ttm":
            cfo_ttm[
                "valor"
            ],

        "capex_ttm":
            capex_ttm[
                "valor"
            ],

        "fcf_ttm":
            fcf_ttm,

        "net_margin_ttm":
            net_margin_ttm,

        "operating_margin_ttm":
            operating_margin_ttm,

        # ----------------------------------------------------
        # BALANCE
        # ----------------------------------------------------

        "cash":
            cash[
                "valor"
            ],

        "debt":
            deuda_total,

        "equity":
            equity[
                "valor"
            ],

        "debt_to_equity":
            debt_to_equity,

        # ----------------------------------------------------
        # SHARES
        # ----------------------------------------------------

        "shares_outstanding":
            shares[
                "valor"
            ],

        "shares_method":
            shares[
                "metodo"
            ],
        # ----------------------------------------------------
        # MARKET CAP
        # ----------------------------------------------------

        "price":
            precio,

        "market_cap":
            market_cap,

        # ----------------------------------------------------
        # VALORACION
        # ----------------------------------------------------

        "pe_ttm":
            pe_ttm,

        "pe_status":
            pe_status,

        "ps_ttm":
            ps_ttm,

        "pb":
            pb,

        "fcf_yield":
            fcf_yield,

        # ----------------------------------------------------
        # BANK / FINANCIAL
        # ----------------------------------------------------

        "roe_aprox":
            roe_aprox,

        # ----------------------------------------------------
        # BIOTECH
        # ----------------------------------------------------

        "cash_burn_ttm":
            cash_burn,

        "cash_runway_years":
            cash_runway_years,

        "cash_to_market_cap":
            cash_to_market_cap
    }