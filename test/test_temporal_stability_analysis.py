import unittest
from datetime import date

from research.temporal_stability_analysis import (
    agrupar_trades_por_semana,
    analizar_variante,
    calcular_concentracion,
    calcular_consistencia,
    comparar_variantes,
    inicio_semana,
    punto_division_mitades,
    resumir_mitades,
    resumir_semanas,
)


def trade(symbol, signal_date, exit_date, retorno, pnl, reason="TIME"):
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "actual_exit_date": exit_date,
        "return_pct": retorno,
        "pnl": pnl,
        "exit_reason": reason,
    }


class TemporalStabilityAnalysisTest(unittest.TestCase):

    def test_asigna_semana_de_signal_date(self):
        dato = trade(
            "AAA", date(2026, 1, 9), date(2026, 1, 14), 5, 100
        )
        grupos = agrupar_trades_por_semana([dato])
        self.assertEqual(list(grupos), [date(2026, 1, 5)])
        self.assertEqual(inicio_semana(dato["signal_date"]), date(2026, 1, 5))

    def test_salida_semana_siguiente_no_cambia_asignacion(self):
        dato = trade(
            "AAA", date(2026, 1, 9), date(2026, 1, 16), 5, 100
        )
        semana = resumir_semanas([dato])[0]
        self.assertEqual(semana["week_start"], date(2026, 1, 5))
        self.assertEqual(semana["week_end"], date(2026, 1, 9))

    def test_mitades_deterministas_por_fechas_unicas(self):
        trades = [
            trade("A", date(2026, 1, 1), date(2026, 1, 2), 1, 10),
            trade("B", date(2026, 1, 2), date(2026, 1, 3), 1, 20),
            trade("C", date(2026, 1, 3), date(2026, 1, 4), 1, 30),
            trade("D", date(2026, 1, 4), date(2026, 1, 5), 1, 40),
            trade("E", date(2026, 1, 5), date(2026, 1, 6), 1, 50),
        ]
        self.assertEqual(punto_division_mitades(trades), date(2026, 1, 3))
        mitades = resumir_mitades(trades)
        self.assertEqual([fila["trades"] for fila in mitades], [3, 2])
        self.assertEqual([fila["total_pnl"] for fila in mitades], [60, 90])

    def test_semanas_positivas_y_negativas(self):
        trades = [
            trade("A", date(2026, 1, 5), date(2026, 1, 6), 2, 100),
            trade("B", date(2026, 1, 12), date(2026, 1, 13), -1, -50),
        ]
        consistencia = calcular_consistencia(resumir_semanas(trades))
        self.assertEqual(consistencia["semanas_positivas"], 1)
        self.assertEqual(consistencia["semanas_negativas"], 1)
        self.assertEqual(consistencia["porcentaje_semanas_positivas"], 50)

    def test_concentracion_semanas_y_top_trades(self):
        trades = [
            trade("A", date(2026, 1, 5), date(2026, 1, 6), 10, 100),
            trade("B", date(2026, 1, 6), date(2026, 1, 7), 5, 50),
            trade("C", date(2026, 1, 12), date(2026, 1, 13), 3, 30),
            trade("D", date(2026, 1, 19), date(2026, 1, 20), 2, 20),
            trade("E", date(2026, 1, 20), date(2026, 1, 21), -1, -10),
            trade("F", date(2026, 1, 26), date(2026, 1, 27), 1, 10),
        ]
        concentracion = calcular_concentracion(trades)
        self.assertAlmostEqual(concentracion["best_week_pct"], 75)
        self.assertAlmostEqual(concentracion["top_2_weeks_pct"], 90)
        self.assertAlmostEqual(concentracion["top_3_trades_pct"], 90)
        self.assertAlmostEqual(concentracion["top_5_trades_pct"], 105)

    def test_concentracion_no_interpretable_si_pnl_no_positivo(self):
        trades = [trade("A", date(2026, 1, 5), date(2026, 1, 6), -1, -10)]
        self.assertTrue(
            all(valor is None for valor in calcular_concentracion(trades).values())
        )

    def test_comparacion_base_variante(self):
        base_sim = {"trade_details": [
            trade("A", date(2026, 1, 5), date(2026, 1, 6), 1, 100)
        ]}
        variante_sim = {"trade_details": [
            trade("A", date(2026, 1, 5), date(2026, 1, 6), 2, 130),
            trade("B", date(2026, 1, 12), date(2026, 1, 13), 1, 20),
        ]}
        base = analizar_variante("BASE", base_sim)
        variante = analizar_variante("VAR", variante_sim)
        comparacion = comparar_variantes(base, variante)
        self.assertEqual(comparacion[0]["delta_pnl"], 30)
        self.assertEqual(comparacion[1]["pnl_base"], 0)
        self.assertEqual(comparacion[1]["delta_pnl"], 20)

    def test_no_resetea_capital_por_semana(self):
        trades = [
            trade("A", date(2026, 1, 5), date(2026, 1, 6), 10, 1000),
            # PNL de la segunda semana conserva la asignación cronológica
            # suministrada por la cartera; no se recalcula sobre 10.000.
            trade("B", date(2026, 1, 12), date(2026, 1, 13), 10, 1100),
        ]
        semanas = resumir_semanas(trades)
        self.assertEqual([fila["total_pnl"] for fila in semanas], [1000, 1100])
        self.assertEqual(sum(fila["total_pnl"] for fila in semanas), 2100)


if __name__ == "__main__":
    unittest.main()
