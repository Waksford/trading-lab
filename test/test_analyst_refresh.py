import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from database import db
from refresh_analyst_consensus import (
    actualizar_analyst_consensus,
    obtener_candidatos_actuales,
)


SNAPSHOT_DATE = "2026-08-24"


def crear_snapshot(symbol):
    return {
        "snapshot_time": f"{SNAPSHOT_DATE}T10:00:00",
        "snapshot_date": SNAPSHOT_DATE,
        "symbol": symbol,
        "price_internal": 100.0,
        "target_mean": 120.0,
        "analyst_count": 5,
        "consensus_score": 1.0,
        "source": "YAHOO",
        "created_at": f"{SNAPSHOT_DATE}T10:00:00",
    }


class AnalystRefreshTest(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)

        database_path = (
            Path(self.temporal.name)
            / "analyst_refresh_test.db"
        )

        patcher = patch.object(
            db,
            "DB_PATH",
            database_path
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        db.inicializar_db()
        db.inicializar_tabla_analyst_consensus()

    def ejecutar(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return actualizar_analyst_consensus(
                snapshot_date=SNAPSHOT_DATE,
                **kwargs
            )

    def test_snapshot_existente_no_llama_provider(self):
        db.guardar_analyst_snapshot(
            crear_snapshot("CACHE")
        )
        provider = Mock()

        resumen = self.ejecutar(
            symbols=["CACHE"],
            provider_func=provider,
        )

        provider.assert_not_called()
        self.assertEqual(resumen["actualizados_hoy"], 1)
        self.assertEqual(resumen["consultados"], 0)

    def test_dos_ejecuciones_consultan_solo_la_primera(self):
        provider = Mock(
            side_effect=lambda symbol, price_internal: (
                crear_snapshot(symbol)
            )
        )

        primero = self.ejecutar(
            symbols=["NEW"],
            provider_func=provider,
        )
        segundo = self.ejecutar(
            symbols=["NEW"],
            provider_func=provider,
        )

        self.assertEqual(primero["guardados"], 1)
        self.assertEqual(segundo["consultados"], 0)
        self.assertEqual(provider.call_count, 1)

    def test_error_de_un_ticker_no_detiene_los_demas(self):
        def provider(symbol, price_internal):
            if symbol == "ERROR":
                raise RuntimeError("fallo simulado")
            return crear_snapshot(symbol)

        resumen = self.ejecutar(
            symbols=["ERROR", "OK"],
            provider_func=provider,
        )

        self.assertEqual(resumen["errores"], 1)
        self.assertEqual(resumen["guardados"], 1)
        self.assertIsNotNone(
            db.obtener_ultimo_analyst_snapshot("OK")
        )

    def test_seleccion_momentum_y_reversal(self):
        db.guardar_scan(
            [
                {
                    "symbol": "MOMA",
                    "score_version": "v4",
                    "prioridad_estudio": "A",
                },
                {
                    "symbol": "MOMB",
                    "score_version": "v4",
                    "prioridad_estudio": "B",
                },
                {
                    "symbol": "REV",
                    "score_version": "v4",
                    "prioridad_estudio": "D",
                    "reversal_candidate": 1,
                    "reversal_version": "reversal_v1",
                    "reversal_priority": "A",
                },
                {
                    "symbol": "NO",
                    "score_version": "v4",
                    "prioridad_estudio": "C",
                },
                {
                    "symbol": "OLD",
                    "score_version": "v3",
                    "prioridad_estudio": "A+",
                },
            ],
            market_date="2026-08-22",
            scan_time_override="2026-08-22T23:59:59",
        )

        self.assertEqual(
            obtener_candidatos_actuales(),
            ["MOMA", "MOMB", "REV"]
        )

    def test_symbols_explicitos_se_normalizan(self):
        consultados = []

        def provider(symbol, price_internal):
            consultados.append(symbol)
            return crear_snapshot(symbol)

        resumen = self.ejecutar(
            symbols=[" gwre ", "PD", "gwre"],
            provider_func=provider,
        )

        self.assertEqual(consultados, ["GWRE", "PD"])
        self.assertEqual(resumen["candidatos"], 2)
        self.assertEqual(resumen["guardados"], 2)


if __name__ == "__main__":
    unittest.main()
