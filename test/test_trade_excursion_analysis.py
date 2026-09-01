import unittest

from research.portfolio_whatif import evaluar_senal_historica
from research.trade_excursion_analysis import (
    analizar_trades,
    construir_comparacion,
    distribuir_mae,
    dividir_resultados,
    mfe_perdedoras,
    percentil,
    preparar_trades,
    supervivencia_stops,
)


def trade(symbol, retorno, mfe, mae):
    return {
        "symbol": symbol,
        "return_pct": retorno,
        "mfe_pct": mfe,
        "mae_pct": mae,
    }


class TradeExcursionAnalysisTest(unittest.TestCase):

    def test_mfe_mae_incluyen_entrada_y_salida(self):
        senal = {
            "symbol": "AAA", "market_date": "2026-01-01",
            "strategy": "MOMENTUM", "source_score_version": "v4",
            "score_version": "v4", "prioridad": "A", "score": 90,
        }
        barras = [
            {"date": "2026-01-02", "open": 100, "high": 120, "low": 99, "close": 105},
            {"date": "2026-01-03", "open": 105, "high": 110, "low": 95, "close": 102},
            {"date": "2026-01-04", "open": 102, "high": 108, "low": 80, "close": 104},
        ]
        resultado, estado = evaluar_senal_historica(senal, barras, 3)
        self.assertEqual(estado, "completa")
        self.assertAlmostEqual(resultado["mfe_pct"], 20.0)
        self.assertAlmostEqual(resultado["mae_pct"], -20.0)
        self.assertEqual(resultado["fecha_entrada"], "2026-01-02")
        self.assertEqual(resultado["fecha_salida"], "2026-01-04")

    def test_giveback_y_clasificacion(self):
        preparados, ausentes = preparar_trades([
            trade("WIN", 8, 20, -4),
            trade("LOSS", 0, 5, -8),
            {"symbol": "MISS", "return_pct": 1, "mfe_pct": None, "mae_pct": -1},
        ])
        ganadoras, perdedoras = dividir_resultados(preparados)
        self.assertEqual(ausentes, 1)
        self.assertAlmostEqual(ganadoras[0]["giveback_pct"], 12)
        self.assertEqual([fila["symbol"] for fila in ganadoras], ["WIN"])
        self.assertEqual([fila["symbol"] for fila in perdedoras], ["LOSS"])

    def test_percentiles_lineales(self):
        valores = [0, 10, 20, 30]
        self.assertAlmostEqual(percentil(valores, 25), 7.5)
        self.assertAlmostEqual(percentil(valores, 50), 15)
        self.assertAlmostEqual(percentil(valores, 75), 22.5)

    def test_umbrales_stop_y_mfe(self):
        ganadoras = [trade("A", 1, 3, -2), trade("B", 1, 4, -5)]
        perdedoras = [trade("C", -1, 5, -2), trade("D", -2, 10, -4)]
        self.assertEqual(supervivencia_stops(ganadoras)[3], 50.0)
        self.assertEqual(supervivencia_stops(ganadoras)[5], 50.0)
        self.assertEqual(mfe_perdedoras(perdedoras)[5], 100.0)
        self.assertEqual(mfe_perdedoras(perdedoras)[10], 50.0)

    def test_intervalos_mae_sin_doble_conteo(self):
        trades = [
            trade("A", 1, 1, -2), trade("B", 1, 1, -4),
            trade("C", 1, 1, -5), trade("D", 1, 1, -8),
            trade("E", 1, 1, -10), trade("F", 1, 1, -15),
        ]
        distribucion = distribuir_mae(trades)
        self.assertEqual(sum(distribucion.values()), len(trades))
        self.assertTrue(all(cantidad == 1 for cantidad in distribucion.values()))

    def test_comparacion_entre_estrategias(self):
        momentum = analizar_trades(
            [trade("M1", 10, 15, -2), trade("M2", -5, 4, -6)],
            "momentum",
        )
        reversal = analizar_trades(
            [trade("R1", 5, 8, -4), trade("R2", 1, 3, -1)],
            "reversal",
        )
        comparacion = construir_comparacion([momentum, reversal])
        self.assertEqual([fila["strategy"] for fila in comparacion], ["MOMENTUM", "REVERSAL"])
        self.assertEqual(comparacion[0]["trades"], 2)
        self.assertEqual(comparacion[0]["win_pct"], 50.0)
        self.assertEqual(comparacion[1]["win_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
