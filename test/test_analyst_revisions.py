import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis.analyst_revisions import (
    calcular_revision_symbol,
    clasificar_revision_analistas
)
from database import db


class AnalystRevisionsTest(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        ruta = Path(self.temporal.name) / "analyst_revisions.db"
        patcher = patch.object(db, "DB_PATH", ruta)
        patcher.start()
        self.addCleanup(patcher.stop)
        db.inicializar_tabla_analyst_consensus()

    def guardar(
        self,
        fecha,
        target=None,
        consenso=None,
        eps=None,
        analistas=None,
        symbol="TEST"
    ):
        db.guardar_analyst_snapshot({
            "snapshot_time": fecha + "T12:00:00",
            "snapshot_date": fecha,
            "symbol": symbol,
            "target_mean": target,
            "consensus_score": consenso,
            "eps_next_y": eps,
            "analyst_count": analistas,
            "source": "YAHOO"
        })

    def test_horizontes_y_snapshot_anterior_mas_cercano(self):
        self.guardar("2026-07-25", 70, 0.1, 1.0, 2)
        self.guardar("2026-07-26", 80, 0.2, 1.2, 3)
        self.guardar("2026-08-18", 100, 0.5, 2.0, 4)
        self.guardar("2026-08-19", 105, 0.6, 2.1, 5)
        self.guardar("2026-08-25", 110, 0.8, 2.4, 7)

        revision = calcular_revision_symbol("TEST")

        self.assertEqual(revision["comparison_date_7d"], "2026-08-18")
        self.assertEqual(revision["comparison_date_30d"], "2026-07-26")
        self.assertAlmostEqual(revision["target_mean_change_pct_7d"], 10)
        self.assertAlmostEqual(revision["target_mean_change_pct_30d"], 37.5)
        self.assertAlmostEqual(revision["eps_next_year_change_pct_7d"], 20)
        self.assertAlmostEqual(revision["consensus_change_7d"], 0.3)
        self.assertEqual(revision["analyst_count_change_7d"], 3)

    def test_sin_historico_y_lectura_no_modifica_db(self):
        self.guardar("2026-08-25", 110, 0.8, 2.4, 7)
        conexion = db.obtener_conexion()
        antes = conexion.execute(
            "SELECT COUNT(*) FROM analyst_consensus_snapshots"
        ).fetchone()[0]
        conexion.close()

        revision = calcular_revision_symbol("TEST")

        conexion = db.obtener_conexion()
        despues = conexion.execute(
            "SELECT COUNT(*) FROM analyst_consensus_snapshots"
        ).fetchone()[0]
        conexion.close()
        self.assertEqual(revision["clasificacion_7d"], "SIN HISTORICO")
        self.assertEqual(revision["clasificacion_30d"], "SIN HISTORICO")
        self.assertEqual(antes, despues)

    def test_clasificaciones_y_datos_parciales(self):
        self.assertEqual(
            clasificar_revision_analistas(4, None, None),
            "POSITIVA"
        )
        self.assertEqual(
            clasificar_revision_analistas(-4, None, None),
            "NEGATIVA"
        )
        self.assertEqual(
            clasificar_revision_analistas(1, None, 0.1),
            "ESTABLE"
        )
        self.assertEqual(
            clasificar_revision_analistas(None, None, None),
            "SIN HISTORICO"
        )
        self.assertEqual(
            clasificar_revision_analistas(None, 12, 0),
            "MUY POSITIVA"
        )
        self.assertEqual(
            clasificar_revision_analistas(None, -12, 0),
            "MUY NEGATIVA"
        )


if __name__ == "__main__":
    unittest.main()
