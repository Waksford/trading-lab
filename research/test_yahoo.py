import sys
import yfinance as yf


def probar(symbol):

    print()
    print("=" * 80)
    print(symbol)
    print("=" * 80)

    ticker = yf.Ticker(symbol)

    # ========================================================
    # PRICE TARGETS
    # ========================================================

    print()
    print("PRICE TARGETS")
    print("-" * 80)

    try:

        targets = (
            ticker.get_analyst_price_targets()
        )

        print(targets)

    except Exception as e:

        print(
            f"ERROR TARGETS: {e}"
        )

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    print()
    print("RECOMMENDATIONS")
    print("-" * 80)

    try:

        recomendaciones = (
            ticker.get_recommendations()
        )

        print(recomendaciones)

    except Exception as e:

        print(
            f"ERROR RECOMMENDATIONS: {e}"
        )

    # ========================================================
    # RECOMMENDATIONS SUMMARY
    # ========================================================

    print()
    print("RECOMMENDATIONS SUMMARY")
    print("-" * 80)

    try:

        resumen = (
            ticker.get_recommendations_summary()
        )

        print(resumen)

    except Exception as e:

        print(
            f"ERROR SUMMARY: {e}"
        )

    # ========================================================
    # EARNINGS ESTIMATES
    # ========================================================

    print()
    print("EARNINGS ESTIMATES")
    print("-" * 80)

    try:

        estimaciones = (
            ticker.get_earnings_estimate()
        )

        print(estimaciones)

    except Exception as e:

        print(
            f"ERROR EARNINGS: {e}"
        )


def main():

    symbols = [
        symbol.strip().upper()
        for symbol in sys.argv[1:]
        if symbol.strip()
    ]

    if not symbols:

        print(
            "Uso: python -m "
            "research.test_yahoo_analysts "
            "GWRE PD HRMY"
        )

        return

    for symbol in symbols:

        probar(symbol)


if __name__ == "__main__":
    main()