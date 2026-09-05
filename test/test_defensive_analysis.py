import unittest

import numpy as np
import pandas as pd

from research.defensive_analysis import (
    DEFENSIVE_ASSETS,
    construir_features,
    detectar_risk_off,
    fechas_señal,
    seleccionar_defensivos,
    simular_defensive,
)
from research.etf_final_validation import episodios_drawdown


def historicos_sinteticos():
    fechas = pd.bdate_range("2020-01-01", periods=280)
    resultado = {}
    for indice, symbol in enumerate(("SPY", *DEFENSIVE_ASSETS)):
        tendencia = 0.0002 + indice * 0.0001
        close = 100 * np.exp(np.arange(len(fechas)) * tendencia)
        resultado[symbol] = pd.DataFrame({
            "open": close * 1.01, "high": close * 1.02,
            "low": close * 0.99, "close": close,
        }, index=fechas)
    return resultado


class DefensiveAnalysisTest(unittest.TestCase):

    def test_deteccion_de_cinco_reglas(self):
        indice = pd.bdate_range("2020-01-01", periods=3)
        f = pd.DataFrame({
            "close": [90, 110, 80], "sma50": [95, 105, 90],
            "sma200": [100, 100, 100], "drawdown60": [-.11, -.02, -.20],
            "momentum60": [-.01, .02, -.03],
        }, index=indice)
        self.assertEqual(detectar_risk_off(f, "SPY_BELOW_SMA200").tolist(), [True, False, True])
        self.assertEqual(detectar_risk_off(f, "SPY_BEAR_TREND").tolist(), [True, False, True])
        self.assertEqual(detectar_risk_off(f, "SPY_DD60_BELOW_10").tolist(), [True, False, True])
        self.assertEqual(detectar_risk_off(f, "SPY_MOM60_NEGATIVE").tolist(), [True, False, True])
        self.assertEqual(detectar_risk_off(f, "SPY_MOM60_NEGATIVE_BELOW_SMA200").tolist(), [True, False, True])

    def test_selectores_top1_top2_y_fallback_shy(self):
        datos = historicos_sinteticos()
        features = construir_features(datos)
        fecha = datos["SPY"].index[-1]
        top1 = seleccionar_defensivos(features, fecha, "MOM60_TOP1")
        top2 = seleccionar_defensivos(features, fecha, "MOM60_TOP2")
        self.assertEqual(len(top1), 1)
        self.assertEqual(len(top2), 2)
        self.assertAlmostEqual(sum(top2.values()), 1.0)
        for symbol in DEFENSIVE_ASSETS:
            features[symbol].at[fecha, "momentum60"] = -0.1
        self.assertEqual(
            seleccionar_defensivos(features, fecha, "MIN_VOL20_POSITIVE"),
            {"SHY": 1.0},
        )

    def test_next_open_costes_no_lookahead_e_idempotencia(self):
        datos = historicos_sinteticos()
        features = construir_features(datos)
        calendario = datos["SPY"].index
        risk = pd.Series(False, index=calendario)
        risk.iloc[220:] = True
        curva1 = simular_defensive(datos, features, risk, "SHY_ONLY", "regime_change")
        curva2 = simular_defensive(datos, features, risk, "SHY_ONLY", "regime_change")
        pd.testing.assert_frame_equal(curva1, curva2)
        cambio = calendario[220]
        siguiente = calendario[221]
        self.assertEqual(curva1.at[cambio, "holdings"], "SPY")
        self.assertEqual(curva1.at[siguiente, "holdings"], "SHY")
        self.assertGreater(curva1["transaction_cost"].sum(), 0)
        self.assertGreaterEqual(curva1["cash"].min(), 0)

    def test_frecuencia_mensual_y_cambio_regimen(self):
        calendario = pd.bdate_range("2022-01-03", "2022-04-15")
        risk = pd.Series(False, index=calendario)
        risk.loc["2022-02-10":] = True
        mensual = fechas_señal(calendario, risk, "monthly")
        cambios = fechas_señal(calendario, risk, "regime_change")
        self.assertIn(pd.Timestamp("2022-02-10"), cambios)
        self.assertNotIn(pd.Timestamp("2022-02-10"), mensual)
        self.assertLess(len(cambios), len(calendario))

    def test_drawdown_y_recovery(self):
        fechas = pd.bdate_range("2022-01-03", periods=6)
        curva = pd.DataFrame({"equity": [100, 110, 90, 95, 110, 115]}, index=fechas)
        episodios = episodios_drawdown(curva)
        self.assertAlmostEqual(episodios.iloc[0]["drawdown_pct"], -18.181818, places=5)
        self.assertTrue(episodios.iloc[0]["recovered"])
        self.assertGreater(episodios.iloc[0]["recovery_sessions"], 0)


if __name__ == "__main__":
    unittest.main()
