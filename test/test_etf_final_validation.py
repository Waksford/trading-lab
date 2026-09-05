import unittest

import numpy as np
import pandas as pd

from research.etf_final_validation import (
    analizar_crisis,
    block_bootstrap,
    concentracion_beneficios,
    episodios_drawdown,
    metricas_anuales,
    rolling_summary,
)
from research.etf_rotation_analysis import simular_cartera


def curva(equity, start="2020-01-02"):
    indice = pd.bdate_range(start, periods=len(equity))
    return pd.DataFrame({
        "equity": equity,
        "is_invested": True,
        "holdings": "SPY",
    }, index=indice)


def precios(n=10):
    indice = pd.bdate_range("2024-01-02", periods=n)
    valores = np.linspace(100, 110, n)
    return pd.DataFrame({
        "open": valores, "high": valores, "low": valores,
        "close": valores, "volume": 1_000_000,
    }, index=indice)


class ETFFinalValidationTest(unittest.TestCase):

    def test_yearly_returns(self):
        indice = pd.to_datetime(["2020-01-02", "2020-12-31", "2021-12-31"])
        datos = pd.DataFrame({"equity": [10_000, 11_000, 12_100]}, index=indice)
        yearly = metricas_anuales(datos)
        self.assertAlmostEqual(yearly.loc[yearly.year == 2020, "return"].iloc[0], 10)
        self.assertAlmostEqual(yearly.loc[yearly.year == 2021, "return"].iloc[0], 10)

    def test_rolling_returns(self):
        datos = curva(np.linspace(100, 200, 1300))
        resultado = rolling_summary(datos, datos)
        self.assertEqual(set(resultado["window_years"]), {1, 3, 5})
        self.assertTrue((resultado["positive_pct"] == 100).all())
        self.assertTrue((resultado["beat_spy_pct"] == 0).all())

    def test_drawdown_duration_and_recovery(self):
        datos = curva([100, 110, 100, 90, 95, 110, 115])
        episodios = episodios_drawdown(datos)
        peor = episodios.iloc[0]
        self.assertAlmostEqual(peor["drawdown_pct"], (90 / 110 - 1) * 100)
        self.assertEqual(peor["recovery_sessions"], 2)
        self.assertTrue(peor["recovered"])

    def test_contribution_analysis(self):
        indice = pd.date_range("2020-01-31", periods=13, freq="ME")
        equity = 100 * np.cumprod([1] + [1.01] * 12)
        datos = pd.DataFrame({"equity": equity, "holdings": "SPY"}, index=indice)
        resultado = concentracion_beneficios(datos)
        self.assertAlmostEqual(resultado["top5_positive_contribution_pct"], 5 / 12 * 100)
        self.assertAlmostEqual(resultado["top10_positive_contribution_pct"], 10 / 12 * 100)
        self.assertIn("SPY:+100.00%", resultado["profit_contribution_by_etf"])

    def test_crisis_window_alignment(self):
        datos = curva([100, 120, 90, 100, 120], start="2020-02-17")
        resultado = analizar_crisis(
            {"TEST": datos}, {"CRISIS": ("2020-02-17", "2020-03-31")}
        )
        self.assertEqual(resultado.iloc[0]["trough_date"], datos.index[2])
        self.assertAlmostEqual(resultado.iloc[0]["max_drawdown"], -25)

    def test_bootstrap_deterministic_seed(self):
        datos = curva(np.linspace(100, 180, 1300))
        uno = block_bootstrap(datos, datos, simulations=100, seed=7)
        dos = block_bootstrap(datos, datos, simulations=100, seed=7)
        self.assertEqual(uno, dos)
        self.assertEqual(uno["beat_spy_probability"], 0)

    def test_capital_invariance_and_transaction_costs(self):
        historicos = {"SPY": precios()}
        signal = [historicos["SPY"].index[0]]
        retornos = []
        costes = []
        for capital in (1_000, 10_000, 50_000):
            resultado = simular_cartera(
                historicos, signal, lambda _: {"SPY": 1.0},
                initial_capital=capital, cost_rate=0.0005,
            )
            retornos.append(resultado["equity"].iloc[-1] / capital - 1)
            costes.append(resultado["transaction_cost"].sum())
        self.assertAlmostEqual(retornos[0], retornos[1])
        self.assertAlmostEqual(retornos[1], retornos[2])
        self.assertAlmostEqual(costes[1] / costes[0], 10)
        self.assertAlmostEqual(costes[2] / costes[0], 50)


if __name__ == "__main__":
    unittest.main()
