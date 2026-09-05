import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_factor_analysis import (
    agregar_outcomes,
    calcular_features_precios,
    calcular_rsi,
    clasificar_quintiles,
    construir_dataset,
    obtener_precios,
)
from research.etf_universe import CATEGORIES, ETF, ETF_UNIVERSE, validate_universe


def precios(close, start="2024-01-02"):
    indice = pd.bdate_range(start, periods=len(close))
    close = pd.Series(close, index=indice, dtype=float)
    return pd.DataFrame({
        "open": close - 0.25,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.arange(len(close)) + 1_000_000,
    }, index=indice)


class ETFFactorAnalysisTest(unittest.TestCase):

    def test_returns_sma_rsi_rs_volatilidad_y_drawdown(self):
        etf = precios(np.arange(1, 261, dtype=float))
        spy = pd.Series(100.0, index=etf.index)
        resultado = calcular_features_precios(etf, spy)
        fila = resultado.iloc[-1]

        self.assertAlmostEqual(fila["momentum20"], (260 / 240 - 1) * 100)
        self.assertAlmostEqual(fila["momentum60"], (260 / 200 - 1) * 100)
        self.assertAlmostEqual(fila["momentum120"], (260 / 140 - 1) * 100)
        self.assertAlmostEqual(fila["sma20"], np.mean(np.arange(241, 261)))
        self.assertAlmostEqual(fila["sma50"], np.mean(np.arange(211, 261)))
        self.assertAlmostEqual(fila["sma200"], np.mean(np.arange(61, 261)))
        self.assertAlmostEqual(fila["rs20"], fila["momentum20"])
        self.assertAlmostEqual(fila["rs60"], fila["momentum60"])
        self.assertAlmostEqual(fila["rs120"], fila["momentum120"])
        self.assertAlmostEqual(fila["rsi14"], 100.0)
        self.assertGreater(fila["volatility20"], 0)
        self.assertAlmostEqual(fila["drawdown60"], 0.0)

    def test_rsi_plano_es_neutral(self):
        serie = pd.Series([100.0] * 30)
        self.assertAlmostEqual(calcular_rsi(serie).iloc[-1], 50.0)

    def test_future_return_next_open_y_alineacion(self):
        etf = precios([100, 101, 102, 103, 104, 105, 106])
        spy = precios([200, 201, 202, 203, 204, 205, 206])
        resultado = agregar_outcomes(etf, spy, horizons=(5,))
        señal = resultado.iloc[0]

        self.assertEqual(señal["entry_date"], etf.index[1])
        self.assertNotEqual(señal["entry_date"], etf.index[0])
        self.assertAlmostEqual(señal["entry_price"], etf.iloc[1]["open"])
        self.assertAlmostEqual(
            señal["future_return_5"],
            (etf.iloc[5]["close"] / etf.iloc[1]["open"] - 1) * 100,
        )
        self.assertTrue(pd.isna(resultado.iloc[-1]["future_return_5"]))

    def test_quintiles_y_datos_insuficientes(self):
        grupos = clasificar_quintiles(pd.Series(range(1, 11)))
        self.assertEqual(list(grupos.iloc[:2]), ["Q1", "Q1"])
        self.assertEqual(list(grupos.iloc[-2:]), ["Q5", "Q5"])
        insuficientes = clasificar_quintiles(pd.Series([1.0, 2.0, np.nan]))
        self.assertTrue(insuficientes.isna().all())

    def test_universo_categorias_y_exclusion_estructuras(self):
        self.assertTrue(validate_universe())
        self.assertGreaterEqual(len(ETF_UNIVERSE), 50)
        self.assertEqual({etf.category for etf in ETF_UNIVERSE}, set(CATEGORIES))
        with self.assertRaises(ValueError):
            validate_universe((ETF("BAD3X", "Example 3x Bull ETF", CATEGORIES[0]),))
        with self.assertRaises(ValueError):
            validate_universe((ETF("INV", "Example Inverse ETF", CATEGORIES[0]),))

    def test_dataset_descarta_historial_insuficiente(self):
        corto = precios(np.arange(1, 150, dtype=float))
        dataset = construir_dataset({"SPY": corto}, corto.index[0], corto.index[-1])
        self.assertTrue(dataset.empty)

    def test_cache_offline_sin_redescarga(self):
        llamadas = []

        def downloader(symbol, start, end):
            llamadas.append((symbol, start, end))
            return precios([100, 101, 102, 103, 104])

        with tempfile.TemporaryDirectory() as temporal:
            cache = Path(temporal)
            inicio = pd.Timestamp("2024-01-02")
            fin = pd.Timestamp("2024-01-08")
            primera = obtener_precios("SPY", inicio, fin, cache_dir=cache, downloader=downloader)
            segunda = obtener_precios("SPY", inicio, fin, cache_dir=cache, downloader=downloader)
            self.assertEqual(len(primera), 5)
            self.assertEqual(len(segunda), 5)
            self.assertEqual(len(llamadas), 1)


if __name__ == "__main__":
    unittest.main()
