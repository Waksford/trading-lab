from datetime import datetime, timedelta

from database.db import (
    PAPER_PORTFOLIO_START_DATE,
    inicializar_tablas_paper,
    inicializar_tablas_paper_portfolio,
    obtener_conexion,
    obtener_resumen_paper_portfolios
)


INITIAL_CAPITAL = 10_000.0
MAX_POSITIONS = 10
TOP_SIGNALS = 5
HOLDING_SESSIONS = 5
PAPER_TOTAL_COST_PCT = 0.10
SIDE_COST_RATE = PAPER_TOTAL_COST_PCT / 2 / 100


CONFIGURACIONES = {
    "MOMENTUM_LIVE": {
        "strategy": "MOMENTUM",
        "prioridades": ("A+", "A")
    },
    "REVERSAL_LIVE": {
        "strategy": "REVERSAL",
        "prioridades": ("A",)
    }
}


def _barra_hasta(datos, market_date, exacta=False):
    if datos is None:
        return None

    candidatas = datos[
        datos["market_date"] == market_date
        if exacta
        else datos["market_date"] <= market_date
    ]
    if candidatas.empty:
        return None
    return candidatas.sort_values("market_date").iloc[-1]


def _senales_candidatas(
    cursor,
    configuracion,
    entry_date,
    previous_market_date=None
):
    prioridades = configuracion["prioridades"]
    placeholders = ",".join("?" for _ in prioridades)
    orden_prioridad = (
        "CASE prioridad WHEN 'A+' THEN 0 WHEN 'A' THEN 1 ELSE 9 END,"
        if configuracion["strategy"] == "MOMENTUM"
        else ""
    )
    return cursor.execute(
        f"""
        SELECT * FROM paper_signals
        WHERE market_date < ?
          AND (? IS NULL OR market_date >= ?)
          AND market_date >= ?
          AND strategy = ?
          AND source_score_version = 'v4'
          AND variant = 'BASE'
          AND prioridad IN ({placeholders})
        ORDER BY {orden_prioridad} score DESC, symbol ASC
        LIMIT ?
        """,
        (
            str(entry_date),
            (
                str(previous_market_date)
                if previous_market_date is not None
                else None
            ),
            (
                str(previous_market_date)
                if previous_market_date is not None
                else None
            ),
            PAPER_PORTFOLIO_START_DATE,
            configuracion["strategy"],
            *prioridades,
            TOP_SIGNALS
        )
    ).fetchall()


def procesar_paper_portfolios(historicos, fecha_hasta=None):
    """Procesa cronologicamente carteras live con OHLC ya descargado."""

    datos_spy = historicos.get("SPY")
    if datos_spy is None or datos_spy.empty:
        raise ValueError("Se necesita historico de SPY")

    sesiones = sorted(set(datos_spy["market_date"]))
    if fecha_hasta is not None:
        sesiones = [fecha for fecha in sesiones if fecha <= fecha_hasta]

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    carteras = cursor.execute(
        "SELECT * FROM paper_portfolios WHERE status = 'ACTIVE' ORDER BY id"
    ).fetchall()
    ahora = datetime.now().isoformat(timespec="seconds")

    for cartera in carteras:
        configuracion = CONFIGURACIONES[cartera["name"]]
        cash = float(cartera["current_cash"])
        ultima_equity = cursor.execute(
            """
            SELECT market_date FROM paper_portfolio_equity
            WHERE portfolio_id = ? ORDER BY market_date DESC LIMIT 1
            """,
            (cartera["id"],)
        ).fetchone()
        fecha_ultima = ultima_equity["market_date"] if ultima_equity else None
        sesiones_pendientes = [
            fecha
            for fecha in sesiones
            if str(fecha) > PAPER_PORTFOLIO_START_DATE
            and (fecha_ultima is None or str(fecha) > fecha_ultima)
        ]

        for indice, market_date in enumerate(sesiones):
            if market_date not in sesiones_pendientes:
                continue

            abiertas = cursor.execute(
                """
                SELECT * FROM paper_portfolio_positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                ORDER BY id
                """,
                (cartera["id"],)
            ).fetchall()

            for posicion in abiertas:
                try:
                    entry_index = sesiones.index(
                        datetime.strptime(
                            posicion["entry_date"],
                            "%Y-%m-%d"
                        ).date()
                    )
                    market_index = sesiones.index(market_date)
                except ValueError:
                    continue
                if market_index - entry_index + 1 < HOLDING_SESSIONS:
                    continue
                barra = _barra_hasta(
                    historicos.get(posicion["symbol"]),
                    market_date,
                    exacta=True
                )
                if barra is None:
                    continue
                exit_price = float(barra["close"])
                proceeds = posicion["shares"] * exit_price * (1 - SIDE_COST_RATE)
                pnl = proceeds - posicion["capital_allocated"]
                retorno = pnl / posicion["capital_allocated"] * 100
                cash += proceeds
                cursor.execute(
                    """
                    UPDATE paper_portfolio_positions SET
                        status = 'CLOSED', planned_exit_date = ?,
                        actual_exit_date = ?,
                        exit_price = ?, exit_reason = 'TIME', pnl = ?,
                        return_pct = ?, last_price = ?, price_stale = 0,
                        updated_at = ?
                    WHERE id = ? AND status = 'OPEN'
                    """,
                    (
                        str(market_date), str(market_date),
                        exit_price, pnl, retorno,
                        exit_price, ahora, posicion["id"]
                    )
                )

            previous_market_date = (
                sesiones[indice - 1]
                if indice > 0
                else None
            )
            candidatas = _senales_candidatas(
                cursor,
                configuracion,
                market_date,
                previous_market_date
            )
            if candidatas:
                abiertas_symbols = {
                    fila["symbol"]
                    for fila in cursor.execute(
                        """
                        SELECT symbol FROM paper_portfolio_positions
                        WHERE portfolio_id = ? AND status = 'OPEN'
                        """,
                        (cartera["id"],)
                    ).fetchall()
                }
                abiertas_count = len(abiertas_symbols)

                for senal in candidatas:
                    if abiertas_count >= MAX_POSITIONS or cash <= 0:
                        break
                    if senal["symbol"] in abiertas_symbols:
                        continue
                    barra = _barra_hasta(
                        historicos.get(senal["symbol"]),
                        market_date,
                        exacta=True
                    )
                    if barra is None:
                        continue
                    precio = float(barra["open"])
                    if precio <= 0:
                        continue
                    huecos = MAX_POSITIONS - abiertas_count
                    asignacion = cash / huecos
                    shares = asignacion / (precio * (1 + SIDE_COST_RATE))
                    capital = shares * precio * (1 + SIDE_COST_RATE)
                    if capital <= 0 or capital > cash + 1e-8:
                        continue
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO paper_portfolio_positions (
                            portfolio_id, paper_signal_id, symbol, signal_date,
                            entry_date, entry_price, shares, capital_allocated,
                            status, planned_exit_date, last_price,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
                        """,
                        (
                            cartera["id"], senal["id"], senal["symbol"],
                            senal["market_date"], str(market_date), precio,
                            shares, capital, None,
                            float(barra["close"]), ahora, ahora
                        )
                    )
                    if cursor.rowcount:
                        cash = max(0.0, cash - capital)
                        abiertas_symbols.add(senal["symbol"])
                        abiertas_count += 1

                        if cartera["benchmark_start_price"] is None:
                            spy_barra = _barra_hasta(datos_spy, market_date, exacta=True)
                            cursor.execute(
                                """
                                UPDATE paper_portfolios SET
                                    benchmark_start_date = ?,
                                    benchmark_start_price = ?
                                WHERE id = ? AND benchmark_start_price IS NULL
                                """,
                                (
                                    str(market_date), float(spy_barra["open"]),
                                    cartera["id"]
                                )
                            )

            abiertas = cursor.execute(
                """
                SELECT * FROM paper_portfolio_positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                """,
                (cartera["id"],)
            ).fetchall()
            positions_value = 0.0
            for posicion in abiertas:
                barra = _barra_hasta(historicos.get(posicion["symbol"]), market_date)
                stale = 1
                precio = posicion["last_price"] or posicion["entry_price"]
                if barra is not None:
                    precio = float(barra["close"])
                    stale = int(barra["market_date"] != market_date)
                positions_value += posicion["shares"] * precio
                cursor.execute(
                    """
                    UPDATE paper_portfolio_positions
                    SET last_price = ?, price_stale = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (precio, stale, ahora, posicion["id"])
                )

            equity = cash + positions_value
            retorno = (equity / cartera["initial_capital"] - 1) * 100
            pico = cursor.execute(
                """
                SELECT MAX(equity) FROM paper_portfolio_equity
                WHERE portfolio_id = ?
                """,
                (cartera["id"],)
            ).fetchone()[0]
            pico = max(float(pico or cartera["initial_capital"]), equity)
            drawdown = (equity / pico - 1) * 100 if pico > 0 else 0.0
            exposure = positions_value / equity * 100 if equity > 0 else 0.0
            cartera_actual = cursor.execute(
                "SELECT * FROM paper_portfolios WHERE id = ?",
                (cartera["id"],)
            ).fetchone()
            spy_value = spy_return = None
            if cartera_actual["benchmark_start_price"]:
                spy_barra = _barra_hasta(datos_spy, market_date)
                spy_value = INITIAL_CAPITAL * (
                    float(spy_barra["close"])
                    / cartera_actual["benchmark_start_price"]
                )
                spy_return = (spy_value / INITIAL_CAPITAL - 1) * 100

            cursor.execute(
                """
                INSERT INTO paper_portfolio_equity (
                    portfolio_id, market_date, cash, positions_value, equity,
                    return_pct, drawdown_pct, exposure_pct,
                    spy_value, spy_return_pct, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(portfolio_id, market_date) DO UPDATE SET
                    cash=excluded.cash, positions_value=excluded.positions_value,
                    equity=excluded.equity, return_pct=excluded.return_pct,
                    drawdown_pct=excluded.drawdown_pct,
                    exposure_pct=excluded.exposure_pct,
                    spy_value=excluded.spy_value,
                    spy_return_pct=excluded.spy_return_pct,
                    updated_at=excluded.updated_at
                """,
                (
                    cartera["id"], str(market_date), cash, positions_value,
                    equity, retorno, drawdown, exposure, spy_value,
                    spy_return, ahora, ahora
                )
            )

        cursor.execute(
            """
            UPDATE paper_portfolios SET current_cash = ?, updated_at = ?
            WHERE id = ?
            """,
            (cash, ahora, cartera["id"])
        )

    conexion.commit()
    conexion.close()
    return obtener_resumen_paper_portfolios()


def imprimir_resumen(carteras):
    print("\n========================================")
    print("       PAPER PORTFOLIO LIVE")
    print("========================================")
    for cartera in carteras:
        equity = cartera.get("equity") or {}
        print(f"\n{cartera['name']}")
        print(f"Capital inicial:      ${cartera['initial_capital']:,.2f}")
        print(f"Equity actual:        ${equity.get('equity', cartera['current_cash']):,.2f}")
        print(f"Retorno:              {equity.get('return_pct', 0):+.2f}%")
        print(f"SPY:                  {equity.get('spy_return_pct') or 0:+.2f}%")
        print(f"Cash:                 ${cartera['current_cash']:,.2f}")
        print(f"Exposicion:           {equity.get('exposure_pct', 0):.1f}%")
        print(f"Posiciones abiertas:  {len(cartera['abiertas'])}")
        print(f"Trades cerrados:      {cartera['cerradas']}")
        print(f"Max drawdown:         {(cartera.get('max_drawdown_pct') or 0):+.2f}%")


def main():
    inicializar_tablas_paper()
    inicializar_tablas_paper_portfolio()

    conexion = obtener_conexion()
    symbols = {
        fila["symbol"]
        for fila in conexion.execute(
            """
            SELECT DISTINCT symbol FROM paper_signals
            WHERE market_date >= ? AND variant = 'BASE'
            """,
            (PAPER_PORTFOLIO_START_DATE,)
        ).fetchall()
    }
    conexion.close()
    symbols.add("SPY")

    from paper_simulator import descargar_historico, preparar_historicos

    df = descargar_historico(
        symbols,
        datetime.strptime(PAPER_PORTFOLIO_START_DATE, "%Y-%m-%d") - timedelta(days=2),
        datetime.now() + timedelta(days=1)
    )
    if df.empty:
        print("No se ha obtenido historico.")
        return
    imprimir_resumen(
        procesar_paper_portfolios(preparar_historicos(df))
    )


if __name__ == "__main__":
    main()
