import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from database import db
from providers.yahoo_analyst import (
    obtener_consenso_analistas,
)


class FakeTicker:

    def __init__(
        self,
        symbol
    ):
        self.symbol = symbol

    def get_analyst_price_targets(self):
        return {
            "current": 100.0,
            "low": 90.0,
            "high": 150.0,
            "mean": 125.0,
            "median": 120.0,
        }

    def get_recommendations_summary(self):
        return pd.DataFrame(
            [
                {
                    "period": "0m",
                    "strongBuy": 3,
                    "buy": 2,
                    "hold": 4,
                    "sell": 1,
                    "strongSell": 0,
                }
            ]
        )

    def get_recommendations(self):
        return pd.DataFrame()

    def get_earnings_estimate(self):
        return pd.DataFrame(
            {
                "avg": [1.0, 1.2, 4.0, 5.0],
                "growth": [0.1, 0.2, 0.3, 0.4],
                "numberOfAnalysts": [5, 6, 7, 8],
            },
            index=["0q", "+1q", "0y", "+1y"],
        )


class AnalystConsensusTest(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)

        database_path = (
            Path(self.temporal.name)
            / "analyst_test.db"
        )

        patcher = patch.object(
            db,
            "DB_PATH",
            database_path
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_snapshots_y_consensus(self):
        db.inicializar_tabla_analyst_consensus()
        db.inicializar_tabla_analyst_consensus()

        snapshot = obtener_consenso_analistas(
            " test ",
            price_internal=100.0,
            ticker_factory=FakeTicker,
        )

        snapshot["snapshot_time"] = (
            "2026-08-24T10:00:00"
        )
        snapshot["snapshot_date"] = "2026-08-24"
        snapshot["created_at"] = (
            "2026-08-24T10:00:00"
        )

        self.assertEqual(
            snapshot["analyst_count"],
            10
        )
        self.assertAlmostEqual(
            snapshot["consensus_score"],
            0.7
        )
        self.assertAlmostEqual(
            snapshot["upside_mean_pct"],
            25.0
        )
        self.assertAlmostEqual(
            snapshot["upside_median_pct"],
            20.0
        )

        self.assertEqual(
            db.guardar_analyst_snapshot(snapshot),
            1
        )
        self.assertEqual(
            db.guardar_analyst_snapshot(snapshot),
            0
        )

        ultimo = db.obtener_ultimo_analyst_snapshot(
            "test"
        )

        self.assertEqual(
            ultimo["symbol"],
            "TEST"
        )
        self.assertAlmostEqual(
            ultimo["consensus_score"],
            0.7
        )
        self.assertEqual(
            ultimo["eps_analysts_next_y"],
            8
        )

        snapshot_null = {
            "snapshot_time": "2026-08-24T11:00:00",
            "snapshot_date": "2026-08-24",
            "symbol": "NULLS",
            "analyst_count": 0,
            "consensus_score": None,
            "source": "YAHOO",
        }

        self.assertEqual(
            db.guardar_analyst_snapshot(
                snapshot_null
            ),
            1
        )

        ultimo_null = (
            db.obtener_ultimo_analyst_snapshot(
                "NULLS"
            )
        )

        self.assertIsNone(
            ultimo_null["target_mean"]
        )
        self.assertIsNone(
            ultimo_null["consensus_score"]
        )

        recientes = (
            db.obtener_analyst_snapshots_recientes(
                limite=10
            )
        )

        self.assertEqual(
            len(recientes),
            2
        )


if __name__ == "__main__":
    unittest.main()
