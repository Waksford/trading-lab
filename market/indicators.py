import pandas as pd
import numpy as np


def calcular_indicadores(
    df: pd.DataFrame
) -> pd.DataFrame:

    datos = df.copy()

    datos = datos.sort_values(
        "timestamp"
    )

    # ========================================================
    # MEDIAS MÓVILES
    # ========================================================

    datos["sma_20"] = (
        datos["close"]
        .rolling(20)
        .mean()
    )

    datos["sma_50"] = (
        datos["close"]
        .rolling(50)
        .mean()
    )

    # ========================================================
    # RENTABILIDAD DIARIA
    # ========================================================

    datos["return_1d"] = (
        datos["close"]
        .pct_change()
    )

    # ========================================================
    # RENTABILIDAD ACUMULADA
    # ========================================================

    datos["return_20d"] = (
        datos["close"]
        .pct_change(20)
        * 100
    )

    datos["return_60d"] = (
        datos["close"]
        .pct_change(60)
        * 100
    )

    # ========================================================
    # VOLATILIDAD
    # ========================================================

    datos["volatility_20"] = (
        datos["return_1d"]
        .rolling(20)
        .std()
        * np.sqrt(252)
        * 100
    )

    # ========================================================
    # VOLUMEN
    # ========================================================

    # Las 20 sesiones ANTERIORES.
    # No metemos la sesión actual dentro
    # de su propia media.

    datos["volume_avg_20"] = (
        datos["volume"]
        .shift(1)
        .rolling(20)
        .mean()
    )

    datos["relative_volume"] = (
        datos["volume"]
        / datos["volume_avg_20"]
    )

    # ========================================================
    # RSI 14
    # ========================================================

    delta = (
        datos["close"]
        .diff()
    )

    ganancias = (
        delta.clip(
            lower=0
        )
    )

    perdidas = (
        -delta.clip(
            upper=0
        )
    )

    media_ganancias = (
        ganancias
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    media_perdidas = (
        perdidas
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    rs = (
        media_ganancias
        / media_perdidas
    )

    datos["rsi_14"] = (
        100
        - (
            100
            / (1 + rs)
        )
    )

    # ========================================================
    # DISTANCIA A MEDIAS
    # ========================================================

    datos["distance_sma20"] = (
        (
            datos["close"]
            / datos["sma_20"]
        )
        - 1
    ) * 100

    datos["distance_sma50"] = (
        (
            datos["close"]
            / datos["sma_50"]
        )
        - 1
    ) * 100

    return datos