import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from database import db
from paper_etf_forward import (
    preparar_panel_forward,
    procesar_carteras_etf_forward,
    seleccion_etf_paper,
)
from research.etf_rotation_analysis import (
    REPRESENTATIVES,
    ranking_fecha,
    seleccionar_etfs,
)


class PaperEtfForwardTest(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        patcher = patch.object(db, "DB_PATH", Path(temporal.name) / "forward.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.inicializar_db()
        db.inicializar_tablas_paper_portfolio()
        self.historicos = self._historicos()

    @staticmethod
    def _historicos():
        fechas = pd.bdate_range("2025-10-01", "2026-10-02")
        resultado = {}
        for indice, item in enumerate(REPRESENTATIVES):
            # Different deterministic trends ensure a stable, non-tied ranking.
            crecimiento = 0.00015 + indice * 0.000035
            close = 100 * np.exp(np.arange(len(fechas)) * crecimiento)
            resultado[item.symbol] = pd.DataFrame({
                "market_date": fechas.date,
                "open": close * 1.001,
                "high": close * 1.003,
                "low": close * 0.997,
                "close": close,
                "volume": 1_000_000,
            })
        return resultado

    def test_selector_es_exactamente_el_de_research(self):
        _, panel = preparar_panel_forward(self.historicos)
        fecha = pd.Timestamp("2026-09-02")
        ranking, pesos = seleccion_etf_paper(panel, fecha)
        esperado = seleccionar_etfs(
            ranking_fecha(panel, fecha), "G_diversified_top2", cash_filter=True
        )
        self.assertEqual(list(pesos), esperado)
        self.assertLessEqual(len(pesos), 2)
        self.assertEqual(len({ranking.set_index("symbol").at[s, "group"] for s in pesos}), len(pesos))
        if pesos:
            self.assertTrue(all(abs(p - 1 / len(pesos)) < 1e-12 for p in pesos.values()))

    def test_next_open_costes_benchmarks_valoracion_e_idempotencia(self):
        procesar_carteras_etf_forward(self.historicos, date(2026, 9, 4))
        conexion = db.obtener_conexion()
        carteras = {r["name"]: dict(r) for r in conexion.execute(
            "SELECT * FROM paper_portfolios WHERE portfolio_type='FORWARD_ETF'"
        )}
        for nombre in ("ETF_TOP2_CANDIDATE", "SPY_BUY_HOLD", "BALANCED_60_40", "SHY_BUY_HOLD"):
            rebalances = conexion.execute(
                "SELECT * FROM paper_portfolio_rebalances WHERE portfolio_id=?",
                (carteras[nombre]["id"],)
            ).fetchall()
            self.assertEqual(len(rebalances), 1)
            self.assertEqual(rebalances[0]["signal_date"], "2026-09-02")
            self.assertEqual(rebalances[0]["execution_date"], "2026-09-03")
            self.assertGreater(rebalances[0]["costs"], 0)
            self.assertGreaterEqual(carteras[nombre]["current_cash"], 0)
            self.assertEqual(conexion.execute(
                "SELECT COUNT(*) FROM paper_portfolio_equity WHERE portfolio_id=?",
                (carteras[nombre]["id"],)
            ).fetchone()[0], 3)
        spy_holdings = conexion.execute(
            "SELECT symbol FROM paper_portfolio_holdings WHERE portfolio_id=?",
            (carteras["SPY_BUY_HOLD"]["id"],)
        ).fetchall()
        self.assertEqual([r["symbol"] for r in spy_holdings], ["SPY"])
        shy_holdings = conexion.execute(
            "SELECT symbol FROM paper_portfolio_holdings WHERE portfolio_id=?",
            (carteras["SHY_BUY_HOLD"]["id"],)
        ).fetchall()
        self.assertEqual([r["symbol"] for r in shy_holdings], ["SHY"])
        self.assertEqual(conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_rebalances WHERE portfolio_id=?",
            (carteras["DEFENSIVE_CANDIDATE"]["id"],)
        ).fetchone()[0], 0)
        balance = {r["symbol"]: r for r in conexion.execute(
            "SELECT * FROM paper_portfolio_holdings WHERE portfolio_id=?",
            (carteras["BALANCED_60_40"]["id"],)
        )}
        self.assertEqual(set(balance), {"SPY", "IEF"})
        valores = {s: r["shares"] * r["entry_price"] for s, r in balance.items()}
        self.assertAlmostEqual(valores["SPY"] / sum(valores.values()), 0.6, places=6)
        operaciones_antes = conexion.execute("SELECT COUNT(*) FROM paper_portfolio_trades").fetchone()[0]
        conexion.close()

        procesar_carteras_etf_forward(self.historicos, date(2026, 9, 4))
        conexion = db.obtener_conexion()
        self.assertEqual(conexion.execute("SELECT COUNT(*) FROM paper_portfolio_trades").fetchone()[0], operaciones_antes)
        conexion.close()

    def test_rebalanceo_solo_en_siguiente_apertura_del_fin_de_mes(self):
        procesar_carteras_etf_forward(self.historicos, date(2026, 10, 2))
        conexion = db.obtener_conexion()
        for nombre in ("ETF_TOP2_CANDIDATE", "BALANCED_60_40"):
            fechas = conexion.execute(
                """SELECT signal_date, execution_date FROM paper_portfolio_rebalances r
                   JOIN paper_portfolios p ON p.id=r.portfolio_id WHERE p.name=?
                   ORDER BY execution_date""", (nombre,)
            ).fetchall()
            self.assertEqual([(r[0], r[1]) for r in fechas], [
                ("2026-09-02", "2026-09-03"), ("2026-09-30", "2026-10-01")
            ])
        spy_count = conexion.execute(
            """SELECT COUNT(*) FROM paper_portfolio_rebalances r JOIN paper_portfolios p
               ON p.id=r.portfolio_id WHERE p.name='SPY_BUY_HOLD'"""
        ).fetchone()[0]
        self.assertEqual(spy_count, 1)
        conexion.close()

    def test_error_de_features_etf_no_bloquea_benchmarks(self):
        with patch("paper_etf_forward.construir_panel_features", side_effect=RuntimeError("features")):
            estados = procesar_carteras_etf_forward(
                self.historicos, date(2026, 9, 4)
            )
        self.assertFalse(estados["ETF_TOP2_CANDIDATE"]["ok"])
        self.assertTrue(estados["SPY_BUY_HOLD"]["ok"])
        self.assertTrue(estados["BALANCED_60_40"]["ok"])

    def test_error_defensive_no_bloquea_shy(self):
        with patch("paper_etf_forward.construir_features", side_effect=RuntimeError("defensive")):
            estados = procesar_carteras_etf_forward(
                self.historicos, date(2026, 9, 4)
            )
        self.assertFalse(estados["DEFENSIVE_CANDIDATE"]["ok"])
        self.assertTrue(estados["SHY_BUY_HOLD"]["ok"])

    def test_error_shy_no_bloquea_defensive(self):
        # Missing SHY prevents only its benchmark; Defensive has no monthly
        # execution yet and can still be valued in cash.
        sin_shy = dict(self.historicos)
        sin_shy.pop("SHY")
        estados = procesar_carteras_etf_forward(sin_shy, date(2026, 9, 4))
        self.assertFalse(estados["SHY_BUY_HOLD"]["ok"])
        self.assertTrue(estados["DEFENSIVE_CANDIDATE"]["ok"])


if __name__ == "__main__":
    unittest.main()
