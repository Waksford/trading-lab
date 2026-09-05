import unittest

import numpy as np
import pandas as pd

from research.defensive_analysis import (
    DEFENSIVE_ASSETS,
    construir_features,
    detectar_risk_off,
    simular_defensive,
)
from research.defensive_final_validation import (
    activaciones_finales,
    rolling_final,
    top2_sin_gld,
)


def datos():
    fechas = pd.bdate_range("2018-01-01", periods=320)
    frames = {}
    for i, symbol in enumerate(("SPY", *DEFENSIVE_ASSETS)):
        close = 100 * np.exp(np.arange(len(fechas)) * (0.0001 + i * 0.00005))
        if symbol == "SPY":
            close[220:] *= np.linspace(1, .75, len(close)-220)
        frames[symbol] = pd.DataFrame({"open": close*1.001, "high": close*1.01,
                                       "low": close*.99, "close": close}, index=fechas)
    return frames


class DefensiveFinalValidationTest(unittest.TestCase):

    def test_finalistas_equivalen_a_reglas_congeladas(self):
        historicos = datos()
        features = construir_features(historicos)
        features["SPY"]["close"] = historicos["SPY"]["close"]
        risk = detectar_risk_off(features["SPY"], "SPY_MOM60_NEGATIVE")
        simple1 = simular_defensive(historicos, features, risk, "SHY_ONLY", "monthly")
        simple2 = simular_defensive(historicos, features, risk, "SHY_ONLY", "monthly")
        pd.testing.assert_frame_equal(simple1, simple2)
        self.assertEqual(simple1.loc[simple1["risk_off"], "holdings"].unique().tolist(), ["SHY"])

    def test_activacion_mensual_y_next_open(self):
        historicos = datos()
        features = construir_features(historicos)
        features["SPY"]["close"] = historicos["SPY"]["close"]
        risk = detectar_risk_off(features["SPY"], "SPY_MOM60_NEGATIVE")
        curvas = {n: simular_defensive(historicos, features, risk, a, "monthly")
                  for n, a in {"DEFENSIVE_SIMPLE": "SHY_ONLY", "DEFENSIVE_TOP2": "MOM60_TOP2"}.items()}
        act = activaciones_finales(historicos, features, risk, curvas)
        validas = act.dropna(subset=["monthly_signal_date", "effective_entry"])
        self.assertFalse(validas.empty)
        calendario = historicos["SPY"].index
        for _, fila in validas.iterrows():
            self.assertEqual(calendario.get_loc(fila.effective_entry), calendario.get_loc(fila.monthly_signal_date)+1)

    def test_diagnostico_sin_gld_no_selecciona_gld(self):
        historicos = datos()
        features = construir_features(historicos)
        features["SPY"]["close"] = historicos["SPY"]["close"]
        risk = detectar_risk_off(features["SPY"], "SPY_MOM60_NEGATIVE")
        curva = top2_sin_gld(historicos, features, risk)
        self.assertFalse(curva["holdings"].str.contains("GLD").any())

    def test_rolling_incluye_comparacion_de_drawdown(self):
        historicos = datos()
        base = pd.DataFrame({"equity": np.linspace(10_000, 12_000, len(historicos["SPY"]))}, index=historicos["SPY"].index)
        resultado = rolling_final({"SPY": base, "DEFENSIVE_SIMPLE": base.copy()}, windows=(20,))
        self.assertIn("lower_drawdown_than_spy_pct", resultado.columns)
        self.assertEqual(set(resultado["window_years"]), {0})


if __name__ == "__main__":
    unittest.main()
