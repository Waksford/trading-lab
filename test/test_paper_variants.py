import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from database import db
from market.paper_exit_variants import aplicar_take_profit


def barras(filas):
    return pd.DataFrame(
        filas,
        columns=["market_date", "open", "high", "low", "close"]
    )


class PaperVariantsTest(unittest.TestCase):

    def preparar_db(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "paper_variants.db"
        patcher = patch.object(db, "DB_PATH", ruta)
        patcher.start()
        self.addCleanup(patcher.stop)
        db.inicializar_db()
        db.inicializar_tablas_paper()
        return ruta

    def insertar_scan(self, ruta, market_date):
        conexion = sqlite3.connect(ruta)
        conexion.execute(
            """
            INSERT INTO scans (
                scan_time, market_date, symbol, nombre, precio,
                score, score_version, prioridad_estudio,
                reversal_candidate, reversal_version,
                reversal_priority, reversal_reason
            ) VALUES (?, ?, 'TEST', 'Test', 100, 95, 'v4', 'A',
                      1, 'reversal_v1', 'A', 'Rebote')
            """,
            (market_date + "T18:00:00", market_date)
        )
        conexion.commit()
        conexion.close()

    def test_variantes_solo_desde_fecha_activacion(self):
        ruta = self.preparar_db()
        self.insertar_scan(ruta, "2026-08-24")
        self.insertar_scan(ruta, "2026-08-25")

        db.sincronizar_senales_paper("v4", ("A",), "MOMENTUM")
        db.sincronizar_senales_paper("v4", ("A",), "REVERSAL")

        conexion = db.obtener_conexion()
        filas = conexion.execute(
            """
            SELECT market_date, strategy, variant
            FROM paper_signals
            ORDER BY market_date, strategy, variant
            """
        ).fetchall()
        conexion.close()

        self.assertEqual(
            [tuple(fila) for fila in filas],
            [
                ("2026-08-24", "MOMENTUM", "BASE"),
                ("2026-08-24", "REVERSAL", "BASE"),
                ("2026-08-25", "MOMENTUM", "BASE"),
                ("2026-08-25", "MOMENTUM", "TP25"),
                ("2026-08-25", "REVERSAL", "BASE"),
                ("2026-08-25", "REVERSAL", "TP10"),
            ]
        )

    def resultado_base(self):
        return {
            "fecha_entrada": "2026-08-26",
            "fecha_salida": "2026-09-01",
            "precio_entrada": 100.0,
            "precio_salida": 105.0,
            "retorno": 4.9,
            "retorno_spy": 0.9,
            "exceso_spy": 4.0,
            "max_subida": 6.0,
            "max_caida": -2.0,
            "max_drawdown": -2.0,
        }

    def spy(self):
        return barras([
            (date(2026, 8, 26), 100, 101, 99, 100),
            (date(2026, 8, 27), 100, 102, 99, 101),
            (date(2026, 8, 28), 101, 103, 100, 102),
            (date(2026, 8, 31), 102, 104, 101, 103),
            (date(2026, 9, 1), 103, 105, 102, 104),
        ])

    def test_take_profit_intradia(self):
        activo = barras([
            (date(2026, 8, 26), 100, 105, 98, 102),
            (date(2026, 8, 27), 102, 111, 101, 108),
            (date(2026, 8, 28), 108, 109, 106, 107),
            (date(2026, 8, 31), 107, 108, 105, 106),
            (date(2026, 9, 1), 106, 107, 104, 105),
        ])
        resultado = aplicar_take_profit(
            self.resultado_base(), activo, self.spy(), 10, 0.10
        )
        self.assertEqual(resultado["exit_reason"], "TAKE_PROFIT")
        self.assertEqual(resultado["actual_exit_date"], "2026-08-27")
        self.assertAlmostEqual(resultado["precio_salida"], 110.0)
        self.assertEqual(resultado["holding_sessions_real"], 2)

    def test_resultado_tp_completa_senal_y_admite_filtro(self):
        ruta = self.preparar_db()
        self.insertar_scan(ruta, "2026-08-25")
        db.sincronizar_senales_paper("v4", ("A",), "MOMENTUM")

        conexion = db.obtener_conexion()
        signal_id = conexion.execute(
            "SELECT id FROM paper_signals WHERE variant = 'TP25'"
        ).fetchone()["id"]
        conexion.close()

        resultado = self.resultado_base()
        resultado.update({
            "signal_id": signal_id,
            "horizonte": 5,
            "variant": "TP25",
            "exit_reason": "TAKE_PROFIT",
            "planned_exit_date": "2026-09-01",
            "actual_exit_date": "2026-08-27",
            "holding_sessions_real": 2,
        })
        self.assertEqual(db.guardar_resultado_paper(resultado), 1)

        filas = db.obtener_resultados_paper(
            strategy="MOMENTUM",
            source_score_version="v4",
            variant="TP25"
        )
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["exit_reason"], "TAKE_PROFIT")

        resumen = db.obtener_resumen_paper(variant="TP25")
        self.assertEqual(resumen["senales"][0]["estado"], "COMPLETA")
        self.assertEqual(resumen["resultados"][0]["variant"], "TP25")

    def test_take_profit_respeta_gap(self):
        activo = barras([
            (date(2026, 8, 26), 112, 114, 111, 113),
            (date(2026, 8, 27), 113, 114, 110, 111),
            (date(2026, 8, 28), 111, 112, 109, 110),
            (date(2026, 8, 31), 110, 111, 108, 109),
            (date(2026, 9, 1), 109, 110, 107, 108),
        ])
        resultado = aplicar_take_profit(
            self.resultado_base(), activo, self.spy(), 10, 0.10
        )
        self.assertEqual(resultado["precio_salida"], 112.0)
        self.assertEqual(resultado["holding_sessions_real"], 1)

    def test_sin_toque_conserva_salida_temporal(self):
        activo = barras([
            (date(2026, 8, 26), 100, 104, 98, 102),
            (date(2026, 8, 27), 102, 106, 101, 105),
            (date(2026, 8, 28), 105, 108, 103, 107),
            (date(2026, 8, 31), 107, 109, 105, 108),
            (date(2026, 9, 1), 108, 109, 104, 105),
        ])
        resultado = aplicar_take_profit(
            self.resultado_base(), activo, self.spy(), 10, 0.10
        )
        self.assertEqual(resultado["exit_reason"], "TIME")
        self.assertEqual(resultado["actual_exit_date"], "2026-09-01")
        self.assertEqual(resultado["holding_sessions_real"], 5)


if __name__ == "__main__":
    unittest.main()
