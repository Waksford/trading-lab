import time

from datetime import datetime

from analysis.fundamentals import (
    analizar_fundamentales
)

from analysis.fundamental_classifier import (
    clasificar_fundamental
)

from database.db import (
    inicializar_db,
    inicializar_tabla_fundamentales,
    inicializar_tabla_fundamental_classification,

    obtener_fundamentales_recientes,
    obtener_ultimo_fundamental,

    guardar_analisis_fundamental,
    guardar_clasificacion_fundamental
)


# ============================================================
# CONFIGURACION
# ============================================================

PAUSA_SEC = 0.15


# ============================================================
# PREPARAR FUNDAMENTAL PARA DB
# ============================================================

def preparar_para_db(
    resultado
):
    """
    Convierte el resultado de analizar_fundamentales()
    al esquema fundamental_analysis.
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
# OBTENER UNIVERSO A RECONSTRUIR
# ============================================================

def obtener_universo():
    """
    Recupera todos los simbolos que ya disponen de
    fundamental_analysis.

    Si existen multiples snapshots de un mismo simbolo,
    conserva solamente el mas reciente.
    """

    filas = obtener_fundamentales_recientes(
        limite=100000
    )

    por_symbol = {}

    for fila in filas:

        symbol = fila.get(
            "symbol"
        )

        if not symbol:
            continue

        symbol = symbol.upper()

        anterior = por_symbol.get(
            symbol
        )

        if anterior is None:

            por_symbol[
                symbol
            ] = fila

            continue

        fecha_actual = (
            fila.get(
                "analysis_date"
            )
            or ""
        )

        fecha_anterior = (
            anterior.get(
                "analysis_date"
            )
            or ""
        )

        if fecha_actual > fecha_anterior:

            por_symbol[
                symbol
            ] = fila

    return sorted(
        por_symbol.values(),
        key=lambda x:
            x.get(
                "symbol",
                ""
            )
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
        "     REBUILD FUNDAMENTALS V1"
    )

    print(
        "======================================"
    )

    print()

    # ========================================================
    # ESQUEMA
    # ========================================================

    inicializar_db()

    inicializar_tabla_fundamentales()

    inicializar_tabla_fundamental_classification()

    # ========================================================
    # UNIVERSO
    # ========================================================

    universo = obtener_universo()

    total = len(
        universo
    )

    print(
        f"Fundamentales existentes: {total}"
    )

    if total == 0:

        print(
            "No hay fundamentales para reconstruir."
        )

        return

    print()

    # ========================================================
    # CONTADORES
    # ========================================================

    refrescados = 0

    clasificados = 0

    sin_datos = 0

    errores = 0

    detalle_sin_datos = []

    detalle_errores = []

    # ========================================================
    # REBUILD
    # ========================================================

    for posicion, antiguo in enumerate(
        universo,
        start=1
    ):

        symbol = antiguo[
            "symbol"
        ].upper()

        precio = antiguo.get(
            "price"
        )

        print(
            f"[{posicion}/{total}] "
            f"{symbol:<7} | "
            f"Precio {precio}"
        )

        try:

            # =================================================
            # RECALCULAR FUNDAMENTALES DESDE SEC
            # =================================================

            resultado = (
                analizar_fundamentales(

                    symbol,

                    precio=precio
                )
            )

            if resultado.get(
                "error"
            ):

                sin_datos += 1

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

                time.sleep(
                    PAUSA_SEC
                )

                continue

            # =================================================
            # GUARDAR FUNDAMENTAL ANALYSIS
            # =================================================

            fila_db = preparar_para_db(
                resultado
            )

            guardar_analisis_fundamental(
                fila_db
            )

            refrescados += 1

            # =================================================
            # RECUPERAR SNAPSHOT ACTUALIZADO
            # =================================================

            fundamental = (
                obtener_ultimo_fundamental(
                    symbol
                )
            )

            if fundamental is None:

                raise RuntimeError(
                    (
                        "No se ha podido recuperar "
                        "fundamental_analysis tras guardarlo."
                    )
                )

            # =================================================
            # RECLASIFICAR
            # =================================================

            clasificacion = (
                clasificar_fundamental(
                    fundamental
                )
            )

            guardar_clasificacion_fundamental(

                fundamental[
                    "id"
                ],

                fundamental,

                clasificacion
            )

            clasificados += 1

            print(
                f"    Modelo: "
                f"{fundamental.get('model')}"
            )

            print(
                f"    Fundamental: "
                f"{clasificacion.get('score_fundamental')}/100 | "
                f"{clasificacion.get('calidad_fundamental')}"
            )

            print(
                f"    Balance: "
                f"{clasificacion.get('balance')}"
            )

            print(
                f"    Valoracion: "
                f"{clasificacion.get('valoracion')}"
            )

            print(
                "    Rebuild: OK"
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
        f"Universo:       "
        f"{total}"
    )

    print(
        f"Refrescados:    "
        f"{refrescados}"
    )

    print(
        f"Clasificados:   "
        f"{clasificados}"
    )

    print(
        f"Sin datos:      "
        f"{sin_datos}"
    )

    print(
        f"Errores:        "
        f"{errores}"
    )

    # ========================================================
    # DETALLE SIN DATOS
    # ========================================================

    if detalle_sin_datos:

        print()

        print(
            "SIN DATOS VALIDOS"
        )

        print(
            "-" * 50
        )

        for (
            symbol,
            motivo
        ) in detalle_sin_datos:

            print(
                f"{symbol:<8} | "
                f"{motivo}"
            )

    # ========================================================
    # DETALLE ERRORES
    # ========================================================

    if detalle_errores:

        print()

        print(
            "ERRORES"
        )

        print(
            "-" * 50
        )

        for (
            symbol,
            error
        ) in detalle_errores:

            print(
                f"{symbol:<8} | "
                f"{error}"
            )


if __name__ == "__main__":

    main()