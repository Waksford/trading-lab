from datetime import (
    datetime,
    timedelta
)

import time

from analysis.fundamentals import (
    analizar_fundamentales
)

from database.db import (
    inicializar_db,
    inicializar_tabla_fundamentales,
    obtener_ultimo_scan,
    obtener_ultimo_fundamental,
    guardar_analisis_fundamental
)


# ============================================================
# CONFIGURACION
# ============================================================

PRIORIDADES = (
    "A+",
    "A",
    "B"
)


FUNDAMENTAL_MAX_AGE_DAYS = 7


PAUSA_SEC = 0.15


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
        )

    except ValueError:

        try:

            return datetime.fromisoformat(
                valor
            )

        except ValueError:

            return None


def fundamental_es_reciente(
    fundamental,
    dias=FUNDAMENTAL_MAX_AGE_DAYS
):
    """
    Comprueba si ya tenemos un snapshot fundamental
    suficientemente reciente.
    """

    if not fundamental:
        return False

    fecha = parse_fecha(
        fundamental.get(
            "analysis_date"
        )
    )

    if fecha is None:
        return False

    limite = (
        datetime.now()
        - timedelta(
            days=dias
        )
    )

    return (
        fecha
        >= limite
    )


# ============================================================
# ADAPTAR RESULTADO AL ESQUEMA SQLITE
# ============================================================

def preparar_para_db(
    resultado
):
    """
    Convierte los nombres de analysis/fundamentals.py
    a los nombres utilizados por fundamental_analysis.
    """

    return {

        # ----------------------------------------------------
        # IDENTIDAD
        # ----------------------------------------------------

        "symbol":
            resultado.get(
                "symbol"
            ),

        "analysis_date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),

        "company_name":
            resultado.get(
                "nombre_sec"
            ),

        "cik":
            resultado.get(
                "cik"
            ),

        "sic":
            resultado.get(
                "sic"
            ),

        "sic_description":
            resultado.get(
                "sic_description"
            ),

        "sector":
            resultado.get(
                "sector"
            ),

        "model":
            resultado.get(
                "modelo"
            ),

        # ----------------------------------------------------
        # FECHAS
        # ----------------------------------------------------

        "fy_date":
            resultado.get(
                "fecha_fy"
            ),

        "reference_date":
            resultado.get(
                "fecha_referencia"
            ),

        "fy_age_days":
            resultado.get(
                "antiguedad_fy_dias"
            ),

        # ----------------------------------------------------
        # FY
        # ----------------------------------------------------

        "revenue_fy":
            resultado.get(
                "revenue_fy"
            ),

        "revenue_yoy":
            resultado.get(
                "revenue_growth_fy"
            ),

        "net_income_fy":
            resultado.get(
                "net_income_fy"
            ),

        "net_income_yoy":
            resultado.get(
                "net_income_growth_fy"
            ),

        # ----------------------------------------------------
        # TTM
        # ----------------------------------------------------

        "revenue_ttm":
            resultado.get(
                "revenue_ttm"
            ),

        "revenue_ttm_method":
            resultado.get(
                "revenue_ttm_method"
            ),

        "net_income_ttm":
            resultado.get(
                "net_income_ttm"
            ),

        "net_income_ttm_method":
            resultado.get(
                "net_income_ttm_method"
            ),

        "operating_margin":
            resultado.get(
                "operating_margin_ttm"
            ),

        "net_margin":
            resultado.get(
                "net_margin_ttm"
            ),

        # ----------------------------------------------------
        # CASH FLOW
        # ----------------------------------------------------

        "cfo_ttm":
            resultado.get(
                "cfo_ttm"
            ),

        "capex_ttm":
            resultado.get(
                "capex_ttm"
            ),

        "fcf_ttm":
            resultado.get(
                "fcf_ttm"
            ),

        # ----------------------------------------------------
        # BALANCE
        # ----------------------------------------------------

        "cash":
            resultado.get(
                "cash"
            ),

        "debt":
            resultado.get(
                "debt"
            ),

        "equity":
            resultado.get(
                "equity"
            ),

        "debt_to_equity":
            resultado.get(
                "debt_to_equity"
            ),

        # ----------------------------------------------------
        # PRECIO
        # ----------------------------------------------------

        "price":
            resultado.get(
                "price"
            ),

        "shares":
            resultado.get(
                "shares_outstanding"
            ),

        "shares_method":
            resultado.get(
                "shares_method"
            ),

        "market_cap":
            resultado.get(
                "market_cap"
            ),

        # ----------------------------------------------------
        # VALORACION
        # ----------------------------------------------------

        "pe_ttm":
            resultado.get(
                "pe_ttm"
            ),

        "ps_ttm":
            resultado.get(
                "ps_ttm"
            ),

        "pb":
            resultado.get(
                "pb"
            ),

        "fcf_yield":
            resultado.get(
                "fcf_yield"
            ),

        # ----------------------------------------------------
        # FINANCIAL
        # ----------------------------------------------------

        "roe":
            resultado.get(
                "roe_aprox"
            )
    }


# ============================================================
# CANDIDATOS
# ============================================================

def obtener_candidatos(
    scan
):
    """
    Selecciona A+/A/B del ultimo scan.

    Evita analizar dos veces el mismo ticker.
    """

    candidatos = {}

    for activo in scan:

        prioridad = activo.get(
            "prioridad_estudio"
        )

        if prioridad not in PRIORIDADES:

            continue

        symbol = activo.get(
            "symbol"
        )

        if not symbol:

            continue

        symbol = symbol.upper()

        anterior = candidatos.get(
            symbol
        )

        if (
            anterior is None

            or

            (
                activo.get(
                    "score"
                )
                or 0
            )
            >
            (
                anterior.get(
                    "score"
                )
                or 0
            )
        ):

            candidatos[
                symbol
            ] = activo

    return list(
        candidatos.values()
    )


# ============================================================
# FORMATO CONSOLA
# ============================================================

def formatear_dinero(
    valor
):

    if valor is None:

        return "N/A"

    valor = float(
        valor
    )

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


def formatear_pct(
    valor
):

    if valor is None:

        return "N/A"

    return (
        f"{float(valor):+.2f}%"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "======================================"
    )

    print(
        "    FUNDAMENTALS ANALYZER V1"
    )

    print(
        "======================================"
    )

    print()

    # ========================================================
    # DB
    # ========================================================

    inicializar_db()

    inicializar_tabla_fundamentales()

    # ========================================================
    # ULTIMO SCAN
    # ========================================================

    scan = obtener_ultimo_scan()

    if not scan:

        print(
            "No hay scans disponibles."
        )

        return

    candidatos = obtener_candidatos(
        scan
    )

    print(
        f"Candidatos A+/A/B: "
        f"{len(candidatos)}"
    )

    print()

    # ========================================================
    # CONTADORES
    # ========================================================

    analizados = 0

    guardados = 0

    omitidos_recientes = 0

    errores = 0

    errores_datos = 0

    detalle_errores = []

    detalle_sin_datos = []

    total = len(
        candidatos
    )

    # ========================================================
    # ANALIZAR
    # ========================================================

    for posicion, activo in enumerate(
        candidatos,
        start=1
    ):

        symbol = activo[
            "symbol"
        ].upper()

        prioridad = activo.get(
            "prioridad_estudio"
        )

        score = activo.get(
            "score"
        )

        precio = activo.get(
            "precio"
        )

        print(
            f"[{posicion}/{total}] "
            f"{symbol:<7} | "
            f"{score}/100 | "
            f"{prioridad}"
        )

        # ====================================================
        # CACHE SQLITE
        # ====================================================

        previo = obtener_ultimo_fundamental(
            symbol
        )

        if fundamental_es_reciente(
            previo
        ):

            omitidos_recientes += 1

            print(
                "    Fundamental reciente: "
                "omitido"
            )

            continue

        # ====================================================
        # SEC
        # ====================================================

        try:

            resultado = (
                analizar_fundamentales(

                    symbol,

                    precio=precio
                )
            )

            analizados += 1

            # ================================================
            # ERROR CONTROLADO
            # ================================================

            if resultado.get(
                "error"
            ):

                errores_datos += 1

                detalle_sin_datos.append(
                    (
                        symbol,
                        resultado[
                            "error"
                        ]
                    )
                )

                print(
                    "    SIN DATOS VALIDOS: "
                    f"{resultado['error']}"
                )

                continue

            # ================================================
            # GUARDAR
            # ================================================

            fila_db = preparar_para_db(
                resultado
            )

            guardar_analisis_fundamental(
                fila_db
            )

            guardados += 1

            # ================================================
            # RESUMEN HUMANO
            # ================================================

            print(
                f"    Modelo: "
                f"{resultado.get('modelo')}"
            )

            print(
                f"    Referencia: "
                f"{resultado.get('fecha_referencia')}"
            )

            print(
                f"    Revenue TTM: "
                f"{formatear_dinero(resultado.get('revenue_ttm'))}"
            )

            print(
                f"    Net income TTM: "
                f"{formatear_dinero(resultado.get('net_income_ttm'))}"
            )

            if (
                resultado.get(
                    "pe_status"
                )
                == "OK"
            ):

                pe_texto = (
                    f"{resultado.get('pe_ttm'):.2f}x"
                )

            else:

                pe_texto = (
                    resultado.get(
                        "pe_status"
                    )
                    or "N/A"
                )

            print(
                f"    P/E: "
                f"{pe_texto}"
            )

            print(
                f"    FCF Yield: "
                f"{formatear_pct(resultado.get('fcf_yield'))}"
            )

            print(
                "    Guardado: OK"
            )

        except Exception as e:

            errores += 1

            detalle_errores.append(
                (
                    symbol,
                    str(e)
                )
            )

            print(
                f"    ERROR: {e}"
            )

        time.sleep(
            PAUSA_SEC
        )

    # ========================================================
    # RESUMEN
    # ========================================================

    print()

    print(
        "======================================"
    )

    print(
        "              RESUMEN"
    )

    print(
        "======================================"
    )

    print()

    print(
        f"Candidatos:         "
        f"{total}"
    )

    print(
        f"Consultados SEC:    "
        f"{analizados}"
    )

    print(
        f"Guardados:          "
        f"{guardados}"
    )

    print(
        f"Recientes omitidos: "
        f"{omitidos_recientes}"
    )

    print(
        f"Sin datos validos:  "
        f"{errores_datos}"
    )

    print(
        f"Errores:            "
        f"{errores}"
    )

    # ========================================================
    # DETALLE DE PROBLEMAS
    # ========================================================

    if detalle_sin_datos:

        print()

        print(
            "SIN DATOS VALIDOS"
        )

        print(
            "-" * 38
        )

        for symbol, motivo in detalle_sin_datos:

            print(
                f"{symbol:<8} | {motivo}"
            )

    if detalle_errores:

        print()

        print(
            "ERRORES"
        )

        print(
            "-" * 38
        )

        for symbol, error in detalle_errores:

            print(
                f"{symbol:<8} | {error}"
            )


if __name__ == "__main__":

    main()