import unittest

import numpy as np
import pandas as pd

from research.etf_rotation_analysis import (
    PERIODS,
    calcular_metricas,
    fechas_rebalanceo,
    metricas_periodos,
    seleccionar_etfs,
    simular_cartera,
)


def historico(valores, start="2024-01-02", opens=None):
    indice = pd.bdate_range(start, periods=len(valores))
    close = pd.Series(valores, index=indice, dtype=float)
    open_ = pd.Series(opens if opens is not None else valores, index=indice, dtype=float)
    return pd.DataFrame({
        "open": open_, "high": np.maximum(open_, close),
        "low": np.minimum(open_, close), "close": close, "volume": 1_000_000,
    }, index=indice)


def fila(symbol, group, m60, m120, trend=True):
    return {
        "symbol": symbol, "group": group,
        "momentum60": m60, "momentum120": m120,
        "rs60": m60, "rs120": m120,
        "momentum_combo": m60 + m120,
        "trend_rs": int(trend) * 2 + m60,
        "price_gt_sma200": trend, "sma50_gt_sma200": trend,
    }


class ETFRotationAnalysisTest(unittest.TestCase):

    def test_ranking_top1_y_top2_diversificado(self):
        ranking = pd.DataFrame([
            fila("SPY", "US", 2, 3),
            fila("QQQ", "US", 5, 5),
            fila("GLD", "Gold", 4, 4),
        ])
        self.assertEqual(seleccionar_etfs(ranking, "A_momentum60_top1"), ["QQQ"])
        self.assertEqual(
            seleccionar_etfs(ranking, "G_diversified_top2"),
            ["QQQ", "GLD"],
        )

    def test_cash_filter(self):
        ranking = pd.DataFrame([
            fila("SPY", "US", -1, 2, trend=False),
            fila("SHY", "Treasuries", 0.2, 0.3),
        ])
        self.assertEqual(
            seleccionar_etfs(ranking, "A_momentum60_top1", cash_filter=True),
            [],
        )

    def test_rebalanceo_semanal_y_mensual(self):
        indice = pd.bdate_range("2024-01-01", "2024-02-09")
        semanales = fechas_rebalanceo(indice, "weekly")
        mensuales = fechas_rebalanceo(indice, "monthly")
        self.assertEqual(semanales[0], pd.Timestamp("2024-01-05"))
        self.assertEqual(mensuales, [pd.Timestamp("2024-01-31")])

    def test_no_lookahead_next_open_costes_y_equity(self):
        datos = {"SPY": historico([100, 110, 120], opens=[100, 105, 115])}
        señal = datos["SPY"].index[0]
        curva = simular_cartera(
            datos, [señal], lambda fecha: {"SPY": 1.0},
            initial_capital=10_000, cost_rate=0.0005,
        )
        self.assertEqual(curva.iloc[0]["holdings"], "CASH")
        self.assertEqual(curva.iloc[1]["holdings"], "SPY")
        self.assertGreater(curva.attrs["total_costs"], 0)
        shares = (10_000 - curva.attrs["total_costs"]) / 105
        self.assertAlmostEqual(curva.iloc[1]["equity"], shares * 110, places=4)
        self.assertGreater(curva.iloc[-1]["equity"], curva.iloc[1]["equity"])

    def test_portfolio_sin_posiciones(self):
        datos = {"SPY": historico([100, 101, 102])}
        curva = simular_cartera(datos, [datos["SPY"].index[0]], lambda _: {})
        self.assertTrue((curva["equity"] == 10_000).all())
        self.assertTrue((curva["holdings"] == "CASH").all())
        self.assertEqual(curva.attrs["total_costs"], 0)

    def test_max_drawdown_cagr_y_sharpe(self):
        indice = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
        curva = pd.DataFrame({
            "equity": [10_000, 12_000, 9_000],
            "is_invested": [False, True, True],
        }, index=indice)
        metricas = calcular_metricas(curva, initial_capital=10_000)
        self.assertAlmostEqual(metricas["max_drawdown"], -25.0)
        self.assertLess(metricas["cagr"], 0)
        self.assertTrue(np.isfinite(metricas["sharpe"]))

    def test_period_split(self):
        indice = pd.bdate_range("2016-01-01", "2026-08-31")
        curva = pd.DataFrame({
            "equity": np.linspace(10_000, 20_000, len(indice)),
            "is_invested": True,
        }, index=indice)
        nombres = {fila["period"] for fila in metricas_periodos(curva)}
        self.assertEqual(nombres, set(PERIODS))


if __name__ == "__main__":
    unittest.main()
