import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from database import db
from paper_etf_forward import (
    _objetivo,
    preparar_panel_forward,
    procesar_carteras_etf_forward,
)
from research.defensive_analysis import construir_features, detectar_risk_off
from research.etf_rotation_analysis import REPRESENTATIVES


class PaperDefensiveCandidateTest(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        patcher = patch.object(db, "DB_PATH", Path(temporal.name) / "defensive.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.inicializar_db()
        db.inicializar_tablas_paper_portfolio()
        self.historicos = self._datos()

    @staticmethod
    def _datos():
        fechas = pd.bdate_range("2025-09-01", "2026-12-02")
        resultado = {}
        for item in REPRESENTATIVES:
            close = np.linspace(100, 110, len(fechas))
            if item.symbol == "SPY":
                close = np.linspace(100, 130, len(fechas))
                sep = (fechas >= "2026-09-01") & (fechas <= "2026-09-30")
                close[sep] = np.linspace(close[np.where(sep)[0][0]], 80, sep.sum())
                oct_on = fechas >= "2026-10-01"
                close[oct_on] = np.linspace(82, 150, oct_on.sum())
            resultado[item.symbol] = pd.DataFrame({
                "market_date": fechas.date, "open": close * 1.001,
                "high": close * 1.01, "low": close * .99,
                "close": close, "volume": 1_000_000,
            })
        return resultado

    def test_target_paper_equivale_a_research_en_risk_on_y_risk_off(self):
        datos, panel = preparar_panel_forward(self.historicos)
        features = construir_features(datos)
        features["SPY"]["close"] = datos["SPY"]["close"]
        cartera = {"name": "DEFENSIVE_CANDIDATE"}
        for fecha in (pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-30")):
            pesos, auditoria, _ = _objetivo(cartera, panel, fecha, features)
            research_off = detectar_risk_off(
                features["SPY"], "SPY_MOM60_NEGATIVE"
            ).at[fecha]
            esperado = "SHY" if research_off else "SPY"
            self.assertEqual(list(pesos), [esperado])
            self.assertEqual(auditoria[0]["state"], "RISK_OFF" if research_off else "RISK_ON")

    def test_activacion_transiciones_no_change_costes_e_idempotencia(self):
        procesar_carteras_etf_forward(self.historicos, date(2026, 12, 2))
        conexion = db.obtener_conexion()
        cartera = conexion.execute(
            "SELECT * FROM paper_portfolios WHERE name='DEFENSIVE_CANDIDATE'"
        ).fetchone()
        decisiones = conexion.execute(
            "SELECT * FROM paper_portfolio_rebalances WHERE portfolio_id=? ORDER BY signal_date",
            (cartera["id"],),
        ).fetchall()
        self.assertEqual(decisiones[0]["signal_date"], "2026-09-30")
        self.assertEqual(decisiones[0]["execution_date"], "2026-10-01")
        self.assertEqual(json.loads(decisiones[0]["selected_json"]), ["SHY"])
        self.assertEqual(json.loads(decisiones[1]["selected_json"]), ["SHY"])
        self.assertEqual(decisiones[1]["cash_reason"], "NO_CHANGE")
        self.assertEqual(json.loads(decisiones[2]["selected_json"]), ["SPY"])
        trades = conexion.execute(
            "SELECT side, symbol, trade_date FROM paper_portfolio_trades WHERE portfolio_id=? ORDER BY id",
            (cartera["id"],),
        ).fetchall()
        self.assertEqual([(r[0], r[1]) for r in trades[:3]], [
            ("BUY", "SHY"), ("SELL", "SHY"), ("BUY", "SPY")
        ])
        self.assertGreater(cartera["total_costs"], 0)
        self.assertGreaterEqual(cartera["current_cash"], 0)
        trade_count = len(trades)
        equity_count = conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_equity WHERE portfolio_id=?", (cartera["id"],)
        ).fetchone()[0]
        conexion.close()
        procesar_carteras_etf_forward(self.historicos, date(2026, 12, 2))
        conexion = db.obtener_conexion()
        self.assertEqual(conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_trades WHERE portfolio_id=?", (cartera["id"],)
        ).fetchone()[0], trade_count)
        self.assertEqual(conexion.execute(
            "SELECT COUNT(*) FROM paper_portfolio_equity WHERE portfolio_id=?", (cartera["id"],)
        ).fetchone()[0], equity_count)
        conexion.close()


if __name__ == "__main__":
    unittest.main()
