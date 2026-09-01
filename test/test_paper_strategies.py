import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db


class PaperStrategiesTest(unittest.TestCase):

    def test_migra_y_separa_momentum_reversal(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        database_path = Path(temporal.name) / "paper_test.db"
        patcher = patch.object(db, "DB_PATH", database_path)
        patcher.start()
        self.addCleanup(patcher.stop)

        db.inicializar_db()

        conexion = sqlite3.connect(database_path)
        conexion.execute(
        """
        CREATE TABLE paper_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_date TEXT NOT NULL,
            scan_time TEXT,
            symbol TEXT NOT NULL,
            nombre TEXT,
            score INTEGER,
            score_version TEXT,
            prioridad TEXT,
            perfil TEXT,
            sector TEXT,
            sector_benchmark TEXT,
            precio_senal REAL,
            alertas TEXT,
            estado TEXT NOT NULL DEFAULT 'PENDIENTE',
            created_at TEXT NOT NULL,
            UNIQUE(market_date, symbol, score_version)
        )
        """
    )
        conexion.execute(
        """
        INSERT INTO paper_signals (
            market_date, symbol, score, score_version,
            prioridad, estado, created_at
        )
        VALUES ('2026-01-02', 'OLD', 90, 'v3',
                'B', 'PENDIENTE', '2026-01-02T12:00:00')
        """
    )
        conexion.execute(
        """
        INSERT INTO scans (
            scan_time, market_date, symbol, nombre,
            precio, score, score_version, prioridad_estudio,
            reversal_candidate, reversal_version,
            reversal_priority, reversal_reason
        )
        VALUES (
            '2026-01-03T12:00:00', '2026-01-03', 'TEST', 'Test',
            10.0, 96, 'v4', 'A',
            1, 'reversal_v1', 'A', 'Rebote'
        )
        """
    )
        conexion.commit()
        conexion.close()

        db.inicializar_tablas_paper()
        db.inicializar_tablas_paper()

        self.assertEqual(
            db.sincronizar_senales_paper(
                score_version="v4",
                prioridades=("A+", "A", "B"),
                strategy="MOMENTUM"
            ),
            1
        )

        self.assertEqual(
            db.sincronizar_senales_paper(
                score_version="v4",
                prioridades=("A",),
                strategy="REVERSAL"
            ),
            1
        )

        resumen_v4 = db.obtener_resumen_paper(
            strategy="MOMENTUM",
            source_score_version="v4"
        )

        resumen_v3 = db.obtener_resumen_paper(
            strategy="MOMENTUM",
            source_score_version="v3"
        )

        self.assertEqual(
            sum(
                fila["cantidad"]
                for fila in resumen_v4["senales"]
            ),
            1
        )

        self.assertEqual(
            sum(
                fila["cantidad"]
                for fila in resumen_v3["senales"]
            ),
            1
        )

        conexion = db.obtener_conexion()
        historica = conexion.execute(
        """
        SELECT strategy, source_score_version
        FROM paper_signals
        WHERE symbol = 'OLD'
        """
    ).fetchone()
        estrategias = conexion.execute(
        """
        SELECT strategy, score_version, source_score_version, prioridad
        FROM paper_signals
        WHERE symbol = 'TEST'
          AND market_date = '2026-01-03'
        ORDER BY strategy
        """
    ).fetchall()
        conexion.close()

        self.assertEqual(
            tuple(historica),
            ("MOMENTUM", "v3")
        )
        self.assertEqual(
            [tuple(fila) for fila in estrategias],
            [
                ("MOMENTUM", "v4", "v4", "A"),
                ("REVERSAL", "reversal_v1", "v4", "A")
            ]
        )


if __name__ == "__main__":
    unittest.main()
