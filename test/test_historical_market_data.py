import tempfile
import unittest
from datetime import date

from research.historical_market_data import obtener_historico


class HistoricalMarketDataTest(unittest.TestCase):

    def test_cache_evitan_descarga_repetida_incluso_fin_no_habil(self):
        llamadas = []

        def downloader(symbol, inicio, fin):
            llamadas.append((symbol, inicio, fin))
            return [
                {
                    "date": date(2026, 1, 2),
                    "open": 100,
                    "high": 102,
                    "low": 99,
                    "close": 101,
                }
            ]

        with tempfile.TemporaryDirectory() as cache_dir:
            primera, info_primera = obtener_historico(
                "AAA", date(2026, 1, 1), date(2026, 1, 4),
                downloader=downloader, cache_dir=cache_dir,
            )
            segunda, info_segunda = obtener_historico(
                "AAA", date(2026, 1, 1), date(2026, 1, 4),
                downloader=downloader, cache_dir=cache_dir,
            )

        self.assertEqual(len(llamadas), 1)
        self.assertEqual(primera, segunda)
        self.assertFalse(info_primera["cache_hit"])
        self.assertTrue(info_segunda["cache_hit"])


if __name__ == "__main__":
    unittest.main()
