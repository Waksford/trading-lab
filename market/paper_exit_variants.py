import pandas as pd


def aplicar_take_profit(
    resultado_base,
    datos_activo,
    datos_spy,
    take_profit_pct,
    coste_total_pct
):
    """Aplica una salida TP intradia sobre la ventana 5D ya validada."""

    resultado = dict(resultado_base)
    fecha_entrada = pd.to_datetime(
        resultado["fecha_entrada"]
    ).date()
    fecha_planificada = pd.to_datetime(
        resultado["fecha_salida"]
    ).date()
    precio_entrada = float(resultado["precio_entrada"])
    precio_objetivo = precio_entrada * (1 + take_profit_pct / 100)

    ventana = datos_activo[
        (datos_activo["market_date"] >= fecha_entrada)
        & (datos_activo["market_date"] <= fecha_planificada)
    ].sort_values("market_date").copy()

    salida_tp = None

    for _, barra in ventana.iterrows():

        if float(barra["high"]) >= precio_objetivo:
            salida_tp = barra
            break

    if salida_tp is None:
        resultado.update({
            "exit_reason": "TIME",
            "planned_exit_date": str(fecha_planificada),
            "actual_exit_date": str(fecha_planificada),
            "holding_sessions_real": 5,
        })
        return resultado

    fecha_salida = salida_tp["market_date"]
    precio_salida = max(
        float(salida_tp["open"]),
        precio_objetivo
    )

    sesiones_spy = datos_spy[
        (datos_spy["market_date"] >= fecha_entrada)
        & (datos_spy["market_date"] <= fecha_salida)
    ].sort_values("market_date")

    if sesiones_spy.empty:
        return None

    spy_entrada = float(sesiones_spy.iloc[0]["open"])
    spy_salida = float(sesiones_spy.iloc[-1]["close"])
    ventana_real = ventana[ventana["market_date"] <= fecha_salida]

    retorno = (
        (precio_salida / precio_entrada - 1) * 100
        - coste_total_pct
    )
    retorno_spy = (
        (spy_salida / spy_entrada - 1) * 100
        - coste_total_pct
    )

    cierres = pd.Series(
        [precio_entrada]
        + ventana_real["close"].astype(float).tolist()
    )
    drawdowns = (cierres / cierres.cummax() - 1) * 100

    resultado.update({
        "fecha_salida": str(fecha_salida),
        "precio_salida": precio_salida,
        "retorno": retorno,
        "retorno_spy": retorno_spy,
        "exceso_spy": retorno - retorno_spy,
        "max_subida": (
            float(ventana_real["high"].max()) / precio_entrada - 1
        ) * 100,
        "max_caida": (
            float(ventana_real["low"].min()) / precio_entrada - 1
        ) * 100,
        "max_drawdown": float(drawdowns.min()),
        "exit_reason": "TAKE_PROFIT",
        "planned_exit_date": str(fecha_planificada),
        "actual_exit_date": str(fecha_salida),
        "holding_sessions_real": len(sesiones_spy),
    })

    return resultado
