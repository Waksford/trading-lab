import unittest

from research.stop_takeprofit_analysis import (
    escenarios_no_dominados,
    resolver_salida,
    simular_cartera_salidas,
    validar_base,
)


def resultado(symbol, signal, entry, exit_date, entry_price=100, exit_price=105, score=90):
    return {
        "symbol": symbol,
        "strategy": "MOMENTUM",
        "source_score_version": "v4",
        "score_version": "v4",
        "prioridad": "A",
        "score": score,
        "horizonte": 5,
        "market_date": signal,
        "fecha_entrada": entry,
        "fecha_salida": exit_date,
        "precio_entrada": entry_price,
        "precio_salida": exit_price,
    }


def barra(fecha, apertura, maximo, minimo, cierre):
    return {
        "date": fecha, "open": apertura, "high": maximo,
        "low": minimo, "close": cierre,
    }


class StopTakeProfitAnalysisTest(unittest.TestCase):

    def test_stop_y_take_profit_intradía(self):
        self.assertEqual(
            resolver_salida(barra("2026-01-01", 100, 105, 89, 95), 100, -10, None)[:2],
            ("STOP", 90),
        )
        take = resolver_salida(
            barra("2026-01-01", 100, 111, 99, 108), 100, None, 10
        )
        self.assertEqual(take[0], "TAKE_PROFIT")
        self.assertAlmostEqual(take[1], 110)

    def test_gaps_stop_y_take_profit(self):
        stop = resolver_salida(barra("2026-01-01", 84, 90, 80, 85), 100, -10, None)
        take = resolver_salida(barra("2026-01-01", 115, 120, 114, 118), 100, None, 10)
        self.assertEqual(stop, ("STOP", 84.0, True, False))
        self.assertEqual(take, ("TAKE_PROFIT", 115.0, False, True))

    def test_misma_vela_aplica_stop_primero(self):
        salida = resolver_salida(
            barra("2026-01-01", 100, 120, 80, 105), 100, -10, 10
        )
        self.assertEqual(salida, ("STOP", 90, False, False, True))

    def escenario(self):
        resultado_base = resultado(
            "AAA", "2026-01-01", "2026-01-02", "2026-01-06", 100, 105
        )
        barras = [
            barra("2026-01-02", 100, 102, 98, 101),
            barra("2026-01-03", 101, 103, 99, 102),
            barra("2026-01-04", 102, 104, 100, 103),
            barra("2026-01-05", 103, 105, 101, 104),
            barra("2026-01-06", 104, 106, 102, 105),
        ]
        return [resultado_base], {"AAA": barras, "SPY": barras}

    def test_time_exit_costes_fecha_y_holding(self):
        resultados, historicos = self.escenario()
        simulacion = simular_cartera_salidas(
            resultados, historicos, "momentum", capital=1000,
            max_positions=1, cost_pct=1, spy_bars=historicos["SPY"],
        )
        trade = simulacion["trade_details"][0]
        self.assertEqual(trade["exit_reason"], "TIME")
        self.assertEqual(str(trade["actual_exit_date"]), "2026-01-06")
        self.assertEqual(trade["holding_sessions_real"], 5)
        self.assertAlmostEqual(simulacion["capital_final"], 1029.105)

    def test_salida_temprana_libera_capital_para_nueva_entrada(self):
        resultados = [
            resultado("AAA", "2026-01-01", "2026-01-02", "2026-01-06", 100, 100, 100),
            resultado("BBB", "2026-01-02", "2026-01-03", "2026-01-07", 100, 100, 90),
        ]
        aaa = [
            barra("2026-01-02", 100, 111, 99, 110),
            barra("2026-01-03", 110, 111, 109, 110),
            barra("2026-01-06", 100, 100, 100, 100),
        ]
        bbb = [
            barra("2026-01-03", 100, 101, 99, 100),
            barra("2026-01-04", 100, 101, 99, 100),
            barra("2026-01-05", 100, 101, 99, 100),
            barra("2026-01-06", 100, 101, 99, 100),
            barra("2026-01-07", 100, 101, 99, 100),
        ]
        spy = [barra(f"2026-01-0{dia}", 100, 101, 99, 100) for dia in range(2, 8)]
        simulacion = simular_cartera_salidas(
            resultados, {"AAA": aaa, "BBB": bbb, "SPY": spy}, "momentum",
            take_profit_pct=10, max_positions=1, cost_pct=0, spy_bars=spy,
        )
        self.assertEqual(simulacion["trades"], 2)
        self.assertEqual(simulacion["exit_tp_count"], 1)
        self.assertLessEqual(simulacion["max_positions_real"], 1)
        self.assertAlmostEqual(simulacion["trade_details"][1]["capital_allocated"], 11000)

    def test_equity_mark_to_market_y_drawdown(self):
        resultados, historicos = self.escenario()
        historicos["AAA"][1]["close"] = 50
        simulacion = simular_cartera_salidas(
            resultados, historicos, "momentum", capital=1000,
            max_positions=1, cost_pct=0, spy_bars=historicos["SPY"],
        )
        self.assertAlmostEqual(simulacion["max_drawdown_pct"], -50.4950495)

    def test_none_none_coincide_con_simulador_base(self):
        resultados, historicos = self.escenario()
        base = simular_cartera_salidas(
            resultados, historicos, "momentum", capital=1000,
            max_positions=1, cost_pct=0, spy_bars=historicos["SPY"],
        )
        coincide, diferencias = validar_base(
            resultados, historicos, "momentum", base,
            capital=1000, holding=5, top=5, max_positions=1, cost_pct=0,
        )
        self.assertTrue(coincide, diferencias)

    def test_escenarios_no_dominados(self):
        filas = [
            {"return_pct": 10, "max_drawdown_pct": -5, "id": "A"},
            {"return_pct": 9, "max_drawdown_pct": -6, "id": "B"},
            {"return_pct": 8, "max_drawdown_pct": -3, "id": "C"},
        ]
        self.assertEqual(
            {fila["id"] for fila in escenarios_no_dominados(filas)},
            {"A", "C"},
        )


if __name__ == "__main__":
    unittest.main()
