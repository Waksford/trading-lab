import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from database import db
from paper_portfolio_live import procesar_paper_portfolios


SESIONES = [
    date(2026, 8, 26), date(2026, 8, 27), date(2026, 8, 28),
    date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2),
    date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 8),
    date(2026, 9, 9), date(2026, 9, 10)
]


def historico(precio=100.0, cierres=None):
    cierres = cierres or [precio] * len(SESIONES)
    return pd.DataFrame({
        "market_date": SESIONES,
        "open": [precio] * len(SESIONES),
        "high": [max(precio, cierre) for cierre in cierres],
        "low": [min(precio, cierre) for cierre in cierres],
        "close": cierres
    })


class PaperPortfolioLiveTest(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "portfolio_live.db"
        patcher = patch.object(db, "DB_PATH", ruta)
        patcher.start()
        self.addCleanup(patcher.stop)
        db.inicializar_db()
        db.inicializar_tablas_paper()
        db.inicializar_tablas_paper_portfolio()

    def senal(
        self,
        symbol,
        fecha="2026-08-25",
        strategy="MOMENTUM",
        prioridad="A",
        score=90
    ):
        conexion = db.obtener_conexion()
        conexion.execute(
            """
            INSERT INTO paper_signals (
                market_date, symbol, score, score_version, strategy,
                source_score_version, variant, prioridad, estado, created_at
            ) VALUES (?, ?, ?, ?, ?, 'v4', 'BASE', ?, 'PENDIENTE', ?)
            """,
            (
                fecha, symbol, score,
                "v4" if strategy == "MOMENTUM" else "reversal_v1",
                strategy, prioridad, fecha + "T20:00:00"
            )
        )
        conexion.commit()
        conexion.close()

    def procesar(self, symbols, precios=None):
        precios = precios or {}
        datos = {"SPY": historico(100, [100 + i for i in range(len(SESIONES))])}
        for symbol in symbols:
            datos[symbol] = historico(
                precios.get(symbol, 100),
                precios.get(symbol + "_closes")
            )
        return procesar_paper_portfolios(datos)

    def posiciones(self, cartera):
        conexion = db.obtener_conexion()
        filas = conexion.execute(
            """
            SELECT p.* FROM paper_portfolio_positions p
            JOIN paper_portfolios c ON c.id = p.portfolio_id
            WHERE c.name = ? ORDER BY p.entry_date, p.id
            """,
            (cartera,)
        ).fetchall()
        conexion.close()
        return [dict(fila) for fila in filas]

    def test_inicio_ranking_top_sizing_y_separacion(self):
        self.senal("OLD", "2026-08-24", score=999)
        for symbol, prioridad, score in (
            ("A_LOW", "A", 99), ("PLUS_LOW", "A+", 80),
            ("PLUS_HIGH", "A+", 95), ("A_TWO", "A", 98),
            ("A_THREE", "A", 97), ("SIXTH", "A", 96)
        ):
            self.senal(symbol, prioridad=prioridad, score=score)
        self.senal("REV", strategy="REVERSAL", prioridad="A", score=70)

        self.procesar({
            "OLD", "A_LOW", "PLUS_LOW", "PLUS_HIGH", "A_TWO",
            "A_THREE", "SIXTH", "REV"
        })
        momentum = self.posiciones("MOMENTUM_LIVE")
        reversal = self.posiciones("REVERSAL_LIVE")

        self.assertEqual(
            [fila["symbol"] for fila in momentum],
            ["PLUS_HIGH", "PLUS_LOW", "A_LOW", "A_TWO", "A_THREE"]
        )
        self.assertEqual(len(momentum), 5)
        self.assertNotIn("OLD", [fila["symbol"] for fila in momentum])
        self.assertEqual(momentum[0]["entry_date"], "2026-08-26")
        self.assertAlmostEqual(momentum[0]["capital_allocated"], 1000)
        self.assertEqual([fila["symbol"] for fila in reversal], ["REV"])

    def test_salida_costes_equity_drawdown_benchmark_e_idempotencia(self):
        self.senal("WIN")
        cierres = [100, 105, 103, 102, 110] + [110] * 6
        self.procesar({"WIN"}, {"WIN_closes": cierres})
        posiciones = self.posiciones("MOMENTUM_LIVE")
        self.assertEqual(posiciones[0]["status"], "CLOSED")
        self.assertEqual(posiciones[0]["actual_exit_date"], "2026-09-01")
        self.assertEqual(posiciones[0]["exit_reason"], "TIME")
        self.assertAlmostEqual(
            posiciones[0]["return_pct"],
            ((110 * (1 - 0.0005)) / (100 * (1 + 0.0005)) - 1) * 100
        )

        conexion = db.obtener_conexion()
        antes = conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_equity"
        ).fetchone()[0]
        cash = conexion.execute(
            "SELECT current_cash FROM paper_portfolios WHERE name='MOMENTUM_LIVE'"
        ).fetchone()[0]
        equity = conexion.execute(
            """
            SELECT * FROM paper_portfolio_equity e
            JOIN paper_portfolios p ON p.id=e.portfolio_id
            WHERE p.name='MOMENTUM_LIVE' ORDER BY market_date DESC LIMIT 1
            """
        ).fetchone()
        conexion.close()
        self.assertGreater(cash, 10000)
        self.assertIsNotNone(equity["spy_return_pct"])
        self.assertLessEqual(equity["drawdown_pct"], 0)
        resumen = db.obtener_resumen_paper_portfolios()
        momentum = next(
            cartera for cartera in resumen
            if cartera["strategy"] == "MOMENTUM"
        )
        self.assertAlmostEqual(momentum["pnl_realizado"], posiciones[0]["pnl"])

        self.procesar({"WIN"}, {"WIN_closes": cierres})
        conexion = db.obtener_conexion()
        despues = conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_equity"
        ).fetchone()[0]
        posiciones_count = conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_positions"
        ).fetchone()[0]
        conexion.close()
        self.assertEqual(antes, despues)
        self.assertEqual(posiciones_count, 1)

    def test_max_positions_symbol_duplicado_y_reutiliza_cash(self):
        symbols = set()
        for dia, fecha in enumerate(("2026-08-25", "2026-08-26", "2026-09-01")):
            for indice in range(5):
                symbol = "DUP" if dia == 1 and indice == 0 else f"S{dia}{indice}"
                if dia == 0 and indice == 0:
                    symbol = "DUP"
                symbols.add(symbol)
                self.senal(symbol, fecha=fecha, score=100 - indice)
        self.procesar(symbols)
        posiciones = self.posiciones("MOMENTUM_LIVE")
        self.assertEqual(sum(f["symbol"] == "DUP" for f in posiciones), 1)
        self.assertLessEqual(
            sum(f["status"] == "OPEN" for f in posiciones),
            10
        )
        self.assertTrue(any(f["entry_date"] == "2026-09-02" for f in posiciones))
        conexion = db.obtener_conexion()
        cash = conexion.execute(
            "SELECT current_cash FROM paper_portfolios WHERE name='MOMENTUM_LIVE'"
        ).fetchone()[0]
        conexion.close()
        self.assertGreaterEqual(cash, 0)

    def test_capital_cero_no_abre(self):
        self.senal("ZERO")
        conexion = db.obtener_conexion()
        conexion.execute(
            """
            UPDATE paper_portfolios SET current_cash=0, initial_capital=10000
            WHERE name='MOMENTUM_LIVE'
            """
        )
        conexion.commit()
        conexion.close()
        self.procesar({"ZERO"})
        self.assertEqual(self.posiciones("MOMENTUM_LIVE"), [])


if __name__ == "__main__":
    unittest.main()
