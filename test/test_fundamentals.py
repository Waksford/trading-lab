from analysis.fundamentals import (
    analizar_fundamentales
)


ACTIVOS = [

    (
        "SENEA",
        189.00
    ),

    (
        "CBNA",
        46.00
    ),

    (
        "PCYO",
        11.50
    ),

    (
        "SNOW",
        320.00
    )
]


# ============================================================
# FORMATOS
# ============================================================

def dinero(
    valor
):

    if valor is None:

        return "N/A"


    abs_valor = abs(
        valor
    )


    if abs_valor >= 1_000_000_000:

        return (
            f"${valor / 1_000_000_000:.2f}B"
        )


    if abs_valor >= 1_000_000:

        return (
            f"${valor / 1_000_000:.2f}M"
        )


    return (
        f"${valor:,.2f}"
    )


def pct(
    valor
):

    if valor is None:

        return "N/A"


    return (
        f"{valor:+.2f}%"
    )


def multiplicador(
    valor
):

    if valor is None:

        return "N/A"


    return (
        f"{valor:.2f}x"
    )


# ============================================================
# TEST
# ============================================================

for symbol, precio in ACTIVOS:

    print()

    print(
        "=" * 70
    )

    print(
        f"       {symbol}"
    )

    print(
        "=" * 70
    )

    print()


    try:

        resultado = (
            analizar_fundamentales(

                symbol,

                precio=precio
            )
        )


        # ====================================================
        # ERROR / STALE
        # ====================================================

        if resultado.get(
            "error"
        ):

            print(
                "ERROR FUNDAMENTAL:"
            )

            print(
                resultado[
                    "error"
                ]
            )


            if resultado.get(
                "fecha_fy"
            ):

                print(
                    f"FY detectado: "
                    f"{resultado['fecha_fy']}"
                )


            if resultado.get(
                "antiguedad_fy_dias"
            ) is not None:

                print(
                    f"Antiguedad: "
                    f"{resultado['antiguedad_fy_dias']} dias"
                )


            continue


        # ====================================================
        # IDENTIDAD
        # ====================================================

        print(
            f"Empresa SEC:       "
            f"{resultado['nombre_sec']}"
        )


        print(
            f"CIK:               "
            f"{resultado['cik']}"
        )


        print(
            f"SIC:               "
            f"{resultado['sic']} "
            f"{resultado['sic_description']}"
        )


        print(
            f"Sector:            "
            f"{resultado['sector']}"
        )


        print(
            f"Modelo:            "
            f"{resultado['modelo']}"
        )


        print(
            f"Fecha FY:          "
            f"{resultado['fecha_fy']}"
        )


        print(
            f"Fecha referencia:  "
            f"{resultado['fecha_referencia']}"
        )


        print(
            f"Antiguedad FY:     "
            f"{resultado['antiguedad_fy_dias']} dias"
        )


        print()

        print(
            f"Modelo lectura: "
            f"{resultado['nota_modelo']}"
        )


        # ====================================================
        # FY
        # ====================================================

        print()

        print(
            "FY"
        )


        print(
            f"Ingresos:          "
            f"{dinero(resultado['revenue_fy'])}"
        )


        print(
            f"Revenue YoY:       "
            f"{pct(resultado['revenue_growth_fy'])}"
        )


        print(
            f"Beneficio neto:    "
            f"{dinero(resultado['net_income_fy'])}"
        )


        print(
            f"Net income YoY:    "
            f"{pct(resultado['net_income_growth_fy'])}"
        )


        # ====================================================
        # TTM
        # ====================================================

        print()

        print(
            "TTM"
        )


        print(
            f"Ingresos TTM:      "
            f"{dinero(resultado['revenue_ttm'])}"
        )


        print(
            f"Metodo revenue:    "
            f"{resultado['revenue_ttm_method']}"
        )


        print(
            f"Beneficio TTM:     "
            f"{dinero(resultado['net_income_ttm'])}"
        )


        print(
            f"Metodo net income: "
            f"{resultado['net_income_ttm_method']}"
        )


        print(
            f"Margen operativo:  "
            f"{pct(resultado['operating_margin_ttm'])}"
        )


        print(
            f"Margen neto:       "
            f"{pct(resultado['net_margin_ttm'])}"
        )


        # ====================================================
        # CASH FLOW
        # ====================================================

        print()

        print(
            "CASH FLOW"
        )


        print(
            f"CFO TTM:           "
            f"{dinero(resultado['cfo_ttm'])}"
        )


        print(
            f"Capex TTM:         "
            f"{dinero(resultado['capex_ttm'])}"
        )


        print(
            f"FCF TTM:           "
            f"{dinero(resultado['fcf_ttm'])}"
        )


        # ====================================================
        # BALANCE
        # ====================================================

        print()

        print(
            "BALANCE"
        )


        print(
            f"Caja:              "
            f"{dinero(resultado['cash'])}"
        )


        print(
            f"Deuda:             "
            f"{dinero(resultado['debt'])}"
        )


        print(
            f"Patrimonio:        "
            f"{dinero(resultado['equity'])}"
        )


        if (
            resultado[
                "modelo"
            ] == "OPERATING"
        ):

            print(
                f"Deuda/Equity:      "
                f"{multiplicador(resultado['debt_to_equity'])}"
            )


        # ====================================================
        # VALORACION
        # ====================================================

        print()

        print(
            "VALORACION"
        )


        print(
            f"Precio usado:      "
            f"${precio:.2f}"
        )


        print(
            f"Market Cap aprox:  "
            f"{dinero(resultado['market_cap'])}"
        )
        print(
            f"Shares metodo:     "
            f"{resultado['shares_method']}"
        )

        if (
            resultado[
                "pe_status"
            ] == "OK"
        ):

            print(
                f"P/E TTM:           "
                f"{multiplicador(resultado['pe_ttm'])}"
            )

        else:

            print(
                f"P/E TTM:           "
                f"{resultado['pe_status']}"
            )


        print(
            f"P/S TTM:           "
            f"{multiplicador(resultado['ps_ttm'])}"
        )


        print(
            f"P/B:               "
            f"{multiplicador(resultado['pb'])}"
        )


        print(
            f"FCF Yield:         "
            f"{pct(resultado['fcf_yield'])}"
        )


        # ====================================================
        # BANK / FINANCIAL
        # ====================================================

        if resultado[
            "modelo"
        ] in [
            "BANK",
            "FINANCIAL"
        ]:

            print()

            print(
                "FINANCIAL MODEL"
            )


            print(
                f"ROE aprox:         "
                f"{pct(resultado['roe_aprox'])}"
            )


            print(
                "FCF/debt industrial:"
                " NO APLICABLE"
            )


        # ====================================================
        # REIT
        # ====================================================

        if resultado[
            "modelo"
        ] == "REIT":

            print()

            print(
                "REIT MODEL"
            )


            print(
                "P/E:               NO APLICABLE"
            )


            print(
                "FFO/AFFO:          PENDIENTE V2"
            )


        # ====================================================
        # BIOTECH
        # ====================================================

        if (
            resultado[
                "modelo"
            ]
            == "BIOTECH_PRE_REVENUE"
        ):

            print()

            print(
                "BIOTECH MODEL"
            )


            print(
                f"Cash burn TTM:     "
                f"{dinero(resultado['cash_burn_ttm'])}"
            )


            if (
                resultado[
                    "cash_runway_years"
                ]
                is None
            ):

                runway = "N/A"

            else:

                runway = (
                    f"{resultado['cash_runway_years']:.2f} anos"
                )


            print(
                f"Cash runway:       "
                f"{runway}"
            )


            print(
                f"Cash/Market Cap:   "
                f"{pct(resultado['cash_to_market_cap'])}"
            )


    except Exception as e:

        print(
            f"ERROR: {e}"
        )