# scoring/reversal_v1.py


REVERSAL_VERSION = "reversal_v1"


def detectar_reversal_v1(
    score_v4,
    rsi,
    distancia_sma20,
    volatilidad,
):
    """
    Detecta candidatos de reversal / rebote.

    Esta estrategia es independiente del momentum V4.

    Regla validada:

    - Score momentum V4 entre 5 y 12
    - RSI entre 25 y 40
    - Distancia SMA20 entre -20% y -10%
    - Volatilidad MUY ALTA
    """

    try:
        score_v4 = float(
            score_v4
        )

        rsi = float(
            rsi
        )

        distancia_sma20 = float(
            distancia_sma20
        )

    except (
        TypeError,
        ValueError
    ):

        return {
            "version":
                REVERSAL_VERSION,

            "candidate":
                False,

            "priority":
                None,

            "reason":
                "Datos insuficientes",
        }


    volatilidad = (
        str(
            volatilidad
        )
        .strip()
        .upper()
    )


    # ========================================================
    # REVERSAL V1
    # ========================================================

    if (
        5 <= score_v4 <= 12

        and

        25 <= rsi < 40

        and

        -20 <= distancia_sma20 < -10

        and

        volatilidad == "MUY ALTA"
    ):

        return {

            "version":
                REVERSAL_VERSION,

            "candidate":
                True,

            "priority":
                "A",

            "reason":
                (
                    "Reversal por sobreventa: "
                    "score momentum 5-12, "
                    "RSI 25-40, "
                    "distancia SMA20 -20/-10%, "
                    "volatilidad MUY ALTA"
                ),
        }


    return {

        "version":
            REVERSAL_VERSION,

        "candidate":
            False,

        "priority":
            None,

        "reason":
            None,
    }