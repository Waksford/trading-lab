import unittest

from weekly_report import generar_lineas_paper_portfolio_live


def posicion(symbol, retorno, capital=1000):
    return {
        "symbol": symbol,
        "capital_allocated": capital,
        "shares": 10,
        "last_price": capital * (1 + retorno / 100) / 10
    }


class WeeklyPaperPortfolioLiveTest(unittest.TestCase):

    def cartera(self, abiertas=None, cierres=None):
        cierres = cierres or []
        return {
            "strategy": "MOMENTUM",
            "current_cash": 5000,
            "equity": {
                "equity": 9940.75,
                "return_pct": -0.5925,
                "spy_return_pct": 0.595,
                "exposure_pct": 70.4
            },
            "max_drawdown_pct": -0.96,
            "pnl_realizado": 38,
            "abiertas": abiertas or [],
            "cerradas": len(cierres),
            "ultimos_cierres": cierres
        }

    def test_pnl_orden_limites_y_sin_duplicados(self):
        abiertas = [
            posicion("P2", -5), posicion("M1", 10), posicion("P1", -10),
            posicion("M3", 2), posicion("P3", -2), posicion("M2", 5),
            posicion("EXTRA", 1)
        ]
        lineas = generar_lineas_paper_portfolio_live(self.cartera(abiertas))
        salida = "\n".join(lineas)
        self.assertIn("P&L realizado: $38.00", salida)
        self.assertIn("P&L no realizado: $10.00", salida)
        self.assertIn(
            "Cash: $5,000.00 | Invertido: $7,000.00 | Exposicion: 70.4%",
            salida
        )
        inicio_mejores = lineas.index("Mejores abiertas:")
        inicio_peores = lineas.index("Peores abiertas:")
        mejores = [linea.split()[0] for linea in lineas[inicio_mejores + 1:inicio_peores]]
        peores = [linea.split()[0] for linea in lineas[inicio_peores + 1:]]
        self.assertEqual(mejores, ["M1", "M2", "M3"])
        self.assertEqual(peores, ["P1", "P2", "P3"])
        self.assertTrue(set(mejores).isdisjoint(peores))

    def test_pocas_abiertas_no_se_repiten_y_sin_cierres(self):
        lineas = generar_lineas_paper_portfolio_live(
            self.cartera([posicion("ONE", 1), posicion("TWO", -1)])
        )
        salida = "\n".join(lineas)
        self.assertEqual(salida.count("ONE"), 1)
        self.assertEqual(salida.count("TWO"), 1)
        self.assertNotIn("Peores abiertas:", lineas)
        self.assertNotIn("Ultimos cierres:", lineas)

    def test_cierres_ordenados_y_limitados(self):
        cierres = [
            {
                "symbol": f"C{i}", "actual_exit_date": f"2026-08-{i:02d}",
                "return_pct": i, "exit_reason": "TIME", "pnl": i
            }
            for i in range(1, 8)
        ]
        lineas = generar_lineas_paper_portfolio_live(self.cartera(cierres=cierres))
        inicio = lineas.index("Ultimos cierres:")
        mostrados = [linea.split()[0] for linea in lineas[inicio + 1:]]
        self.assertEqual(mostrados, ["C7", "C6", "C5", "C4", "C3"])

    def test_sin_posiciones_abiertas(self):
        lineas = generar_lineas_paper_portfolio_live(self.cartera())
        self.assertIn("P&L no realizado: $0.00", "\n".join(lineas))
        self.assertIn("Invertido: $0.00", "\n".join(lineas))
        self.assertNotIn("Mejores abiertas:", lineas)
        self.assertNotIn("Peores abiertas:", lineas)


if __name__ == "__main__":
    unittest.main()
