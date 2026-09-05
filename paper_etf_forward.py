"""Forward paper portfolios for the frozen ETF candidate and live benchmarks."""

import json
from datetime import datetime

import pandas as pd

from database.db import ETF_FORWARD_START_DATE, obtener_conexion
from paper_portfolio_config import (
    BALANCED_60_40,
    DEFENSIVE_CANDIDATE,
    ETF_TOP2_CANDIDATE,
    FORWARD_ETF_PORTFOLIOS,
    SPY_BUY_HOLD,
    SHY_BUY_HOLD,
)
from research.defensive_analysis import construir_features, detectar_risk_off
from research.etf_rotation_analysis import (
    GROUP_BY_SYMBOL,
    TRANSACTION_COST,
    construir_panel_features,
    ranking_fecha,
    seleccionar_etfs,
)


FORWARD_NAMES = FORWARD_ETF_PORTFOLIOS
ETF_STRATEGY = "G_diversified_top2"


def _adaptar_historicos_forward(historicos):
    adaptados = {}
    for symbol, datos in historicos.items():
        if datos is None or datos.empty or symbol not in GROUP_BY_SYMBOL:
            continue
        frame = datos.copy()
        frame.index = pd.to_datetime(frame["market_date"])
        adaptados[symbol] = frame.sort_index()
    return adaptados


def preparar_panel_forward(historicos):
    """Adapt paper OHLC frames to the exact feature builder used by research."""
    adaptados = _adaptar_historicos_forward(historicos)
    return adaptados, construir_panel_features(adaptados)


def seleccion_etf_paper(panel, signal_date):
    """Thin adapter: the frozen selection remains owned by research."""
    ranking = ranking_fecha(panel, pd.Timestamp(signal_date))
    seleccion = seleccionar_etfs(ranking, ETF_STRATEGY, cash_filter=True)
    peso = 1.0 / len(seleccion) if seleccion else 0.0
    return ranking, {symbol: peso for symbol in seleccion}


def _precio(datos, fecha, campo):
    if datos is None or fecha not in datos.index:
        return None
    valor = datos.at[fecha, campo]
    return None if pd.isna(valor) else float(valor)


def _objetivo(cartera, panel, signal_date, defensive_features=None):
    nombre = cartera["name"]
    if nombre == ETF_TOP2_CANDIDATE:
        ranking, pesos = seleccion_etf_paper(panel, signal_date)
        columnas = [
            "symbol", "group", "momentum60", "momentum120",
            "momentum_combo", "price_gt_sma200",
        ]
        auditoria = ranking[columnas].sort_values(
            ["momentum_combo", "symbol"], ascending=[False, True]
        ).head(10).to_dict("records") if not ranking.empty else []
        motivo = None if pesos else "Ningun ETF supera el filtro cash congelado"
        return pesos, auditoria, motivo
    if nombre == BALANCED_60_40:
        return {"SPY": 0.6, "IEF": 0.4}, [], None
    if nombre == DEFENSIVE_CANDIDATE:
        if defensive_features is None:
            raise ValueError("No hay features para Defensive Candidate")
        spy_features = defensive_features["SPY"].copy()
        spy_close = float(spy_features.at[signal_date, "close"])
        momentum60 = float(spy_features.at[signal_date, "momentum60"])
        risk_off = bool(detectar_risk_off(
            spy_features, "SPY_MOM60_NEGATIVE"
        ).at[signal_date])
        target = "SHY" if risk_off else "SPY"
        return {target: 1.0}, [{
            "spy_close": spy_close, "spy_momentum60": momentum60,
            "state": "RISK_OFF" if risk_off else "RISK_ON",
            "new_target": target,
        }], None
    if nombre == SHY_BUY_HOLD:
        return {"SHY": 1.0}, [], None
    return {"SPY": 1.0}, [], None


def _es_ejecucion(cartera, fecha, anterior, tiene_rebalanceos):
    activacion = pd.Timestamp(cartera["activation_date"] or ETF_FORWARD_START_DATE)
    if anterior == activacion and not tiene_rebalanceos:
        return cartera["name"] != DEFENSIVE_CANDIDATE
    if anterior is None or fecha <= activacion or anterior < activacion:
        return False
    if cartera["name"] in (SPY_BUY_HOLD, SHY_BUY_HOLD):
        return False
    return fecha.month != anterior.month


def _rebalancear(
    cursor, cartera, historicos, panel, signal_date, execution_date, ahora,
    defensive_features=None,
):
    pesos, ranking, motivo = _objetivo(
        cartera, panel, signal_date, defensive_features
    )
    holdings = {r["symbol"]: dict(r) for r in cursor.execute(
        "SELECT * FROM paper_portfolio_holdings WHERE portfolio_id = ?", (cartera["id"],)
    ).fetchall()}
    if cartera["name"] == DEFENSIVE_CANDIDATE:
        previous = next(iter(holdings), "CASH")
        ranking[0]["previous_target"] = previous
        ranking[0]["operation"] = (
            "NO_CHANGE" if set(holdings) == set(pesos) else f"{previous}->{next(iter(pesos))}"
        )
    opens = {s: _precio(historicos.get(s), execution_date, "open") for s in set(holdings) | set(pesos)}
    if cartera["name"] == BALANCED_60_40 and any(not opens.get(s) for s in ("SPY", "IEF")):
        raise ValueError("SPY e IEF deben tener apertura para ejecutar el 60/40")
    if cartera["name"] == SHY_BUY_HOLD and not opens.get("SHY"):
        raise ValueError("SHY debe tener apertura para ejecutar buy and hold")
    if cartera["name"] == SPY_BUY_HOLD and not opens.get("SPY"):
        raise ValueError("SPY debe tener apertura para ejecutar buy and hold")
    pesos = {s: w for s, w in pesos.items() if opens.get(s) and w > 0}
    suma = sum(pesos.values())
    pesos = {s: w / suma for s, w in pesos.items()} if suma else {}
    actual = {s: h["shares"] * (opens.get(s) or h["last_price"] or h["entry_price"]) for s, h in holdings.items()}
    equity_open = float(cartera["current_cash"]) + sum(actual.values())
    if cartera["name"] == DEFENSIVE_CANDIDATE and set(holdings) == set(pesos):
        cursor.execute(
            """INSERT INTO paper_portfolio_rebalances
               (portfolio_id, signal_date, execution_date, ranking_json,
                selected_json, target_weights_json, cash_filter, cash_reason,
                equity_before, equity_after, costs, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, 'NO_CHANGE', ?, ?, 0.0, ?)""",
            (cartera["id"], str(signal_date.date()), str(execution_date.date()),
             json.dumps(ranking), json.dumps(list(pesos)), json.dumps(pesos),
             equity_open, equity_open, ahora),
        )
        cursor.execute(
            "UPDATE paper_portfolios SET last_rebalance_date=?, updated_at=? WHERE id=?",
            (str(execution_date.date()), ahora, cartera["id"]),
        )
        print(
            "DEFENSIVE MONTHLY DECISION | "
            f"Signal {signal_date.date()} | SPY momentum60 "
            f"{ranking[0]['spy_momentum60']:+.2%} | State {ranking[0]['state']} | "
            f"Previous {previous} | Target {ranking[0]['new_target']} | "
            f"Execution {execution_date.date()} open | NO_CHANGE | costes $0.00"
        )
        return
    target_total = equity_open
    for _ in range(4):
        targets = {s: target_total * w for s, w in pesos.items()}
        traded = sum(abs(targets.get(s, 0.0) - actual.get(s, 0.0)) for s in set(targets) | set(actual))
        target_total = max(equity_open - traded * TRANSACTION_COST, 0.0) if pesos else 0.0
    targets = {s: target_total * w for s, w in pesos.items()}
    traded = sum(abs(targets.get(s, 0.0) - actual.get(s, 0.0)) for s in set(targets) | set(actual))
    coste_total = traded * TRANSACTION_COST
    cash = max(equity_open - sum(targets.values()) - coste_total, 0.0)

    insercion_rebalanceo = cursor.execute(
        """INSERT INTO paper_portfolio_rebalances
           (portfolio_id, signal_date, execution_date, ranking_json, selected_json,
            target_weights_json, cash_filter, cash_reason, equity_before,
            equity_after, costs, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (cartera["id"], str(signal_date.date()), str(execution_date.date()),
         json.dumps(ranking), json.dumps(list(pesos)), json.dumps(pesos),
         int(cartera["name"] == ETF_TOP2_CANDIDATE), motivo, equity_open,
         equity_open - coste_total, coste_total, ahora)
    )
    rebalance_id = insercion_rebalanceo.lastrowid
    operaciones = []
    for symbol in sorted(set(actual) | set(targets)):
        precio = opens.get(symbol)
        if not precio:
            continue
        diferencia = targets.get(symbol, 0.0) - actual.get(symbol, 0.0)
        if abs(diferencia) < 1e-8:
            continue
        side = "BUY" if diferencia > 0 else "SELL"
        gross = abs(diferencia)
        fee = gross * TRANSACTION_COST
        shares_delta = gross / precio
        previo = holdings.get(symbol)
        realized = None
        if side == "SELL" and previo:
            proporcion = min(shares_delta / previo["shares"], 1.0)
            base_vendida = previo["cost_basis"] * proporcion
            realized = gross - fee - base_vendida
        cursor.execute(
            """INSERT INTO paper_portfolio_trades
               (portfolio_id, rebalance_id, symbol, side, trade_date, price,
                shares, gross_value, fee, realized_pnl, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cartera["id"], rebalance_id, symbol, side, str(execution_date.date()),
             precio, shares_delta, gross, fee, realized, ahora)
        )
        operaciones.append(f"{side} {symbol} ${gross:.2f}")

    for symbol in set(holdings) - set(targets):
        cursor.execute("DELETE FROM paper_portfolio_holdings WHERE portfolio_id=? AND symbol=?", (cartera["id"], symbol))
    for symbol, target in targets.items():
        shares = target / opens[symbol]
        previo = holdings.get(symbol)
        diferencia = target - actual.get(symbol, 0.0)
        if previo is None:
            basis = target + max(diferencia, 0.0) * TRANSACTION_COST
        elif diferencia >= 0:
            basis = previo["cost_basis"] + diferencia * (1 + TRANSACTION_COST)
        else:
            proporcion_restante = shares / previo["shares"] if previo["shares"] else 0.0
            basis = previo["cost_basis"] * proporcion_restante
        cursor.execute(
            """INSERT INTO paper_portfolio_holdings
               (portfolio_id, symbol, category, shares, cost_basis, entry_date,
                entry_price, last_price, price_stale, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
               ON CONFLICT(portfolio_id, symbol) DO UPDATE SET
                category=excluded.category, shares=excluded.shares,
                cost_basis=excluded.cost_basis, last_price=excluded.last_price,
                price_stale=0, updated_at=excluded.updated_at""",
            (cartera["id"], symbol, GROUP_BY_SYMBOL.get(symbol), shares, basis,
             str(execution_date.date()), opens[symbol], opens[symbol], ahora, ahora)
        )
    cursor.execute(
        """UPDATE paper_portfolios SET current_cash=?, total_costs=total_costs+?,
           last_rebalance_date=?, updated_at=? WHERE id=?""",
        (cash, coste_total, str(execution_date.date()), ahora, cartera["id"])
    )
    print(
        f"{cartera['name']} rebalanceo | senal {signal_date.date()} | "
        f"ejecucion {execution_date.date()} | seleccion {list(pesos)} | "
        f"categorias {[GROUP_BY_SYMBOL.get(s) for s in pesos]} | filtro_cash "
        f"{cartera['name'] == ETF_TOP2_CANDIDATE} | pesos {pesos} | "
        f"operaciones {operaciones} | costes ${coste_total:.2f} | "
        f"equity ${equity_open:.2f} -> ${equity_open - coste_total:.2f}"
    )
    if cartera["name"] == DEFENSIVE_CANDIDATE:
        print(
            "DEFENSIVE MONTHLY DECISION | "
            f"Signal {signal_date.date()} | SPY momentum60 "
            f"{ranking[0]['spy_momentum60']:+.2%} | State {ranking[0]['state']} | "
            f"Previous {ranking[0]['previous_target']} | Target {ranking[0]['new_target']} | "
            f"Execution {execution_date.date()} open | {ranking[0]['operation']} | "
            f"costes ${coste_total:.2f}"
        )


def _valorar(cursor, cartera, historicos, fecha, ahora):
    cash = cursor.execute("SELECT current_cash FROM paper_portfolios WHERE id=?", (cartera["id"],)).fetchone()[0]
    valor = 0.0
    for holding in cursor.execute("SELECT * FROM paper_portfolio_holdings WHERE portfolio_id=?", (cartera["id"],)).fetchall():
        precio = _precio(historicos.get(holding["symbol"]), fecha, "close")
        stale = 0
        if precio is None:
            precio = holding["last_price"] or holding["entry_price"]
            stale = 1
        valor += holding["shares"] * precio
        cursor.execute("UPDATE paper_portfolio_holdings SET last_price=?, price_stale=?, updated_at=? WHERE id=?", (precio, stale, ahora, holding["id"]))
    equity = cash + valor
    peak = cursor.execute("SELECT MAX(equity) FROM paper_portfolio_equity WHERE portfolio_id=?", (cartera["id"],)).fetchone()[0]
    peak = max(float(peak or cartera["initial_capital"]), equity)
    retorno = (equity / cartera["initial_capital"] - 1) * 100
    dd = (equity / peak - 1) * 100 if peak else 0.0
    exposure = valor / equity * 100 if equity else 0.0
    cursor.execute(
        """INSERT INTO paper_portfolio_equity
           (portfolio_id, market_date, cash, positions_value, equity, return_pct,
            drawdown_pct, exposure_pct, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(portfolio_id, market_date) DO UPDATE SET cash=excluded.cash,
            positions_value=excluded.positions_value, equity=excluded.equity,
            return_pct=excluded.return_pct, drawdown_pct=excluded.drawdown_pct,
            exposure_pct=excluded.exposure_pct, updated_at=excluded.updated_at""",
        (cartera["id"], str(fecha.date()), cash, valor, equity, retorno, dd,
         exposure, ahora, ahora)
    )


def procesar_carteras_etf_forward(historicos, fecha_hasta=None):
    """Value daily and rebalance only next-open after valid monthly signals."""
    datos = _adaptar_historicos_forward(historicos)
    if "SPY" not in datos:
        raise ValueError("Se necesita historico de SPY para carteras ETF forward")
    panel = None
    error_panel = None
    try:
        panel = construir_panel_features(datos)
    except Exception as exc:
        error_panel = exc
    defensive_features = None
    error_defensive = None
    try:
        defensive_features = construir_features(datos)
        defensive_features["SPY"]["close"] = datos["SPY"]["close"]
    except Exception as exc:
        error_defensive = exc
    sesiones = list(datos["SPY"].index.sort_values().unique())
    if fecha_hasta is not None:
        sesiones = [f for f in sesiones if f.date() <= fecha_hasta]
    conexion = obtener_conexion()
    conexion.execute("PRAGMA foreign_keys = ON")
    carteras = conexion.execute(
        "SELECT * FROM paper_portfolios WHERE status='ACTIVE' AND portfolio_type='FORWARD_ETF' ORDER BY id"
    ).fetchall()
    ahora = datetime.now().isoformat(timespec="seconds")
    estados = {}
    for cartera in carteras:
        try:
            conexion.execute(f"SAVEPOINT forward_{cartera['id']}")
            if cartera["name"] == ETF_TOP2_CANDIDATE and error_panel is not None:
                raise RuntimeError(f"No se pudo construir panel ETF: {error_panel}")
            if cartera["name"] == DEFENSIVE_CANDIDATE and error_defensive is not None:
                raise RuntimeError(f"No se pudo construir features Defensive: {error_defensive}")
            ultima = conexion.execute("SELECT MAX(market_date) FROM paper_portfolio_equity WHERE portfolio_id=?", (cartera["id"],)).fetchone()[0]
            rebalances = conexion.execute("SELECT COUNT(*) FROM paper_portfolio_rebalances WHERE portfolio_id=?", (cartera["id"],)).fetchone()[0]
            for indice, fecha in enumerate(sesiones):
                if fecha.date().isoformat() < ETF_FORWARD_START_DATE or (ultima and fecha.date().isoformat() <= ultima):
                    continue
                anterior = sesiones[indice - 1] if indice else None
                actual = conexion.execute("SELECT * FROM paper_portfolios WHERE id=?", (cartera["id"],)).fetchone()
                if _es_ejecucion(actual, fecha, anterior, bool(rebalances)):
                    _rebalancear(
                        conexion, actual, datos, panel, anterior, fecha, ahora,
                        defensive_features,
                    )
                    rebalances += 1
                _valorar(conexion, actual, datos, fecha, ahora)
            conexion.execute(f"RELEASE forward_{cartera['id']}")
            estados[cartera["name"]] = {"ok": True, "error": None}
        except Exception as exc:
            conexion.execute(f"ROLLBACK TO forward_{cartera['id']}")
            conexion.execute(f"RELEASE forward_{cartera['id']}")
            print(f"ERROR {cartera['name']}: {exc}")
            estados[cartera["name"]] = {"ok": False, "error": str(exc)}
    conexion.commit()
    conexion.close()
    return estados
