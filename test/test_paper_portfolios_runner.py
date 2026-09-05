import unittest
from unittest.mock import patch

import paper_portfolios_runner as runner


class PaperPortfoliosRunnerTest(unittest.TestCase):

    def test_un_fallo_no_impide_intentar_todas_las_carteras(self):
        llamadas = []

        def acciones(_, fecha_hasta=None, nombres=None, incluir_forward=True):
            nombre = next(iter(nombres))
            llamadas.append(nombre)
            if nombre == "MOMENTUM_LIVE":
                raise RuntimeError("fallo controlado")

        forward = {
            "ETF_TOP2_CANDIDATE": {"ok": True, "error": None},
            "SPY_BUY_HOLD": {"ok": True, "error": None},
            "BALANCED_60_40": {"ok": True, "error": None},
            "DEFENSIVE_CANDIDATE": {"ok": True, "error": None},
            "SHY_BUY_HOLD": {"ok": True, "error": None},
        }
        with patch.object(runner, "procesar_paper_portfolios", side_effect=acciones), \
             patch.object(runner, "procesar_carteras_etf_forward", return_value=forward):
            estados = runner.ejecutar_motores({"SPY": object()})

        self.assertEqual(llamadas, ["MOMENTUM_LIVE", "REVERSAL_LIVE"])
        self.assertFalse(estados["MOMENTUM_LIVE"]["ok"])
        self.assertTrue(estados["REVERSAL_LIVE"]["ok"])
        self.assertTrue(estados["SPY_BUY_HOLD"]["ok"])

    def test_resumen_incluye_cinco_estados_y_equity(self):
        estados = {
            nombre: {"ok": True, "error": None}
            for nombre in runner.ALL_PAPER_PORTFOLIOS
        }
        carteras = [
            {"name": nombre, "current_cash": 10_000, "equity": {"equity": 9_999}}
            for nombre in runner.ALL_PAPER_PORTFOLIOS
        ]
        salida = "\n".join(runner.generar_resumen_estados(estados, carteras))
        for nombre in runner.ALL_PAPER_PORTFOLIOS:
            self.assertIn(nombre, salida)
        self.assertEqual(salida.count("  OK"), 7)
        self.assertIn("equity=$  9,999.00", salida)


if __name__ == "__main__":
    unittest.main()
