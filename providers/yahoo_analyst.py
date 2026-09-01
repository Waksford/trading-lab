from datetime import datetime

import pandas as pd
import yfinance as yf


def normalizar_symbol(
    symbol
):
    return str(symbol).strip().upper()


def _numero(
    valor
):
    if valor is None:
        return None

    try:
        numero = float(valor)
    except (
        TypeError,
        ValueError
    ):
        return None

    if pd.isna(numero):
        return None

    return numero


def _entero(
    valor
):
    numero = _numero(
        valor
    )

    if numero is None:
        return 0

    return max(
        0,
        int(numero)
    )


def _normalizar_clave(
    valor
):
    return (
        str(valor)
        .strip()
        .lower()
        .replace("_", "")
        .replace(" ", "")
    )


def _fila_recomendaciones(
    recomendaciones
):
    if recomendaciones is None:
        return None

    if isinstance(
        recomendaciones,
        dict
    ):
        recomendaciones = pd.DataFrame(
            recomendaciones
        )

    if not isinstance(
        recomendaciones,
        pd.DataFrame
    ) or recomendaciones.empty:
        return None

    periodo_columna = next(
        (
            columna
            for columna in recomendaciones.columns
            if _normalizar_clave(columna) == "period"
        ),
        None
    )

    if periodo_columna is not None:
        recientes = recomendaciones[
            recomendaciones[periodo_columna]
            .astype(str)
            .str.strip()
            .str.lower()
            == "0m"
        ]

        if not recientes.empty:
            return recientes.iloc[0]

    return recomendaciones.iloc[0]


def _valor_serie(
    serie,
    nombre
):
    if serie is None:
        return None

    clave_buscada = _normalizar_clave(
        nombre
    )

    for clave, valor in serie.items():
        if _normalizar_clave(clave) == clave_buscada:
            return valor

    return None


def _valor_estimacion(
    estimaciones,
    periodo,
    columna
):
    if not isinstance(
        estimaciones,
        pd.DataFrame
    ) or estimaciones.empty:
        return None

    fila_periodo = next(
        (
            indice
            for indice in estimaciones.index
            if str(indice).strip().lower()
            == periodo.lower()
        ),
        None
    )

    columna_real = next(
        (
            nombre
            for nombre in estimaciones.columns
            if _normalizar_clave(nombre)
            == _normalizar_clave(columna)
        ),
        None
    )

    if fila_periodo is None or columna_real is None:
        return None

    return estimaciones.loc[
        fila_periodo,
        columna_real
    ]


def obtener_consenso_analistas(
    symbol,
    price_internal=None,
    ticker_factory=yf.Ticker
):
    """
    Consulta Yahoo y devuelve un snapshot limpio listo para DB.

    No escribe en SQLite ni modifica ningún score del proyecto.
    """

    symbol = normalizar_symbol(
        symbol
    )

    if not symbol:
        raise ValueError(
            "symbol no puede estar vacio"
        )

    ticker = ticker_factory(
        symbol
    )

    errores = []

    try:
        targets = (
            ticker.get_analyst_price_targets()
            or {}
        )
    except Exception as exc:
        targets = {}
        errores.append(
            f"targets: {exc}"
        )

    try:
        recomendaciones = (
            ticker.get_recommendations_summary()
        )
    except Exception as exc:
        recomendaciones = None
        errores.append(
            f"recommendations_summary: {exc}"
        )

    if recomendaciones is None or (
        isinstance(recomendaciones, pd.DataFrame)
        and recomendaciones.empty
    ):
        try:
            recomendaciones = (
                ticker.get_recommendations()
            )
        except Exception as exc:
            recomendaciones = None
            errores.append(
                f"recommendations: {exc}"
            )

    try:
        estimaciones = (
            ticker.get_earnings_estimate()
        )
    except Exception as exc:
        estimaciones = None
        errores.append(
            f"earnings_estimate: {exc}"
        )

    fila_recomendaciones = _fila_recomendaciones(
        recomendaciones
    )

    strong_buy = _entero(
        _valor_serie(
            fila_recomendaciones,
            "strongBuy"
        )
    )
    buy = _entero(
        _valor_serie(
            fila_recomendaciones,
            "buy"
        )
    )
    hold = _entero(
        _valor_serie(
            fila_recomendaciones,
            "hold"
        )
    )
    sell = _entero(
        _valor_serie(
            fila_recomendaciones,
            "sell"
        )
    )
    strong_sell = _entero(
        _valor_serie(
            fila_recomendaciones,
            "strongSell"
        )
    )

    analyst_count = (
        strong_buy
        + buy
        + hold
        + sell
        + strong_sell
    )

    consensus_score = None

    if analyst_count > 0:
        consensus_score = (
            strong_buy * 2
            + buy
            - sell
            - strong_sell * 2
        ) / analyst_count

        consensus_score = max(
            -2.0,
            min(
                2.0,
                consensus_score
            )
        )

    target_low = _numero(
        targets.get("low")
    )
    target_high = _numero(
        targets.get("high")
    )
    target_mean = _numero(
        targets.get("mean")
    )
    target_median = _numero(
        targets.get("median")
    )
    price_yahoo = _numero(
        targets.get("current")
    )
    price_internal = _numero(
        price_internal
    )

    upside_mean_pct = None
    upside_median_pct = None

    if (
        price_internal is not None
        and price_internal > 0
    ):
        if target_mean is not None and target_mean > 0:
            upside_mean_pct = (
                target_mean
                / price_internal
                - 1
            ) * 100

        if target_median is not None and target_median > 0:
            upside_median_pct = (
                target_median
                / price_internal
                - 1
            ) * 100

    recommendation_period = _valor_serie(
        fila_recomendaciones,
        "period"
    )

    ahora = datetime.now()

    snapshot = {
        "snapshot_time": ahora.isoformat(
            timespec="seconds"
        ),
        "snapshot_date": ahora.date().isoformat(),
        "symbol": symbol,
        "price_internal": price_internal,
        "price_yahoo": price_yahoo,
        "target_low": target_low,
        "target_high": target_high,
        "target_mean": target_mean,
        "target_median": target_median,
        "upside_mean_pct": upside_mean_pct,
        "upside_median_pct": upside_median_pct,
        "strong_buy": strong_buy,
        "buy": buy,
        "hold": hold,
        "sell": sell,
        "strong_sell": strong_sell,
        "analyst_count": analyst_count,
        "consensus_score": consensus_score,
        "recommendation_period": (
            str(recommendation_period)
            if recommendation_period is not None
            else None
        ),
        "eps_0q": _numero(
            _valor_estimacion(
                estimaciones,
                "0q",
                "avg"
            )
        ),
        "eps_next_q": _numero(
            _valor_estimacion(
                estimaciones,
                "+1q",
                "avg"
            )
        ),
        "eps_0y": _numero(
            _valor_estimacion(
                estimaciones,
                "0y",
                "avg"
            )
        ),
        "eps_next_y": _numero(
            _valor_estimacion(
                estimaciones,
                "+1y",
                "avg"
            )
        ),
        "eps_growth_0y": _numero(
            _valor_estimacion(
                estimaciones,
                "0y",
                "growth"
            )
        ),
        "eps_growth_next_y": _numero(
            _valor_estimacion(
                estimaciones,
                "+1y",
                "growth"
            )
        ),
        "eps_analysts_0y": _numero(
            _valor_estimacion(
                estimaciones,
                "0y",
                "numberOfAnalysts"
            )
        ),
        "eps_analysts_next_y": _numero(
            _valor_estimacion(
                estimaciones,
                "+1y",
                "numberOfAnalysts"
            )
        ),
        "source": "YAHOO",
        "created_at": ahora.isoformat(
            timespec="seconds"
        ),
    }

    externos = [
        snapshot["price_yahoo"],
        snapshot["target_low"],
        snapshot["target_high"],
        snapshot["target_mean"],
        snapshot["target_median"],
        snapshot["analyst_count"]
            if snapshot["analyst_count"] > 0
            else None,
        snapshot["eps_0q"],
        snapshot["eps_next_q"],
        snapshot["eps_0y"],
        snapshot["eps_next_y"],
    ]

    if not any(
        valor is not None
        for valor in externos
    ):
        if errores:
            raise RuntimeError(
                " | ".join(errores)
            )
        return None

    return snapshot
