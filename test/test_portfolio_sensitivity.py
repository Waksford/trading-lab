import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from research.portfolio_sensitivity import (
    clasificar_muestra,
    clasificar_robustez,
    exportar_csv,
    generar_escenarios,
    imprimir_informe,
    resumir_por_strategy_holding,
)


def simulador_falso(resultados, **kwargs):
    retorno = kwargs["top"] + kwargs["max_positions"] / 10 + kwargs["holding"] / 10
    return {
        "capital_inicial": kwargs["capital"],
        "capital_final": kwargs["capital"] * (1 + retorno / 100),
        "retorno_total_pct": retorno,
        "spy_return_pct": 1.0,
        "exceso_spy_pct": retorno - 1,
        "max_drawdown_pct": -5.0,
        "win_rate_pct": 60.0,
        "operaciones": 30,
        "retorno_medio_trade_pct": 1.0,
        "retorno_mediana_trade_pct": 0.8,
        "exposicion_media_pct": 70.0,
        "max_posiciones_simultaneas": kwargs["max_positions"],
        "periodo_inicio": "2026-01-01",
        "periodo_fin": "2026-02-01",
    }


class PortfolioSensitivityTest(unittest.TestCase):

    def setUp(self):
        self.resultados = {
            (strategy, holding): []
            for strategy in ("momentum", "reversal")
            for holding in (5, 20)
        }

    def test_genera_36_combinaciones_sin_duplicados_y_ordenadas(self):
        filas = generar_escenarios(self.resultados, {"SPY": []}, simulador_falso)
        claves = [
            (f["strategy"], f["holding"], f["top"], f["max_positions"])
            for f in filas
        ]
        self.assertEqual(len(claves), 36)
        self.assertEqual(len(set(claves)), 36)
        self.assertEqual(claves, sorted(claves))

    def test_sample_quality(self):
        self.assertEqual(clasificar_muestra(19), "MUY BAJA")
        self.assertEqual(clasificar_muestra(20), "BAJA")
        self.assertEqual(clasificar_muestra(50), "MEDIA")
        self.assertEqual(clasificar_muestra(100), "BUENA")

    def test_resumen_strategy_holding(self):
        filas = generar_escenarios(self.resultados, {"SPY": []}, simulador_falso)
        resumen = resumir_por_strategy_holding(filas)
        self.assertEqual(len(resumen), 4)
        self.assertTrue(all(fila["escenarios"] == 9 for fila in resumen))

    def test_robustez_tres_etiquetas(self):
        base = {
            "exceso_spy_pp": 2, "retorno_pct": 3,
            "max_drawdown_pct": -10, "trades": 100,
        }
        self.assertEqual(clasificar_robustez([base] * 9), "ROBUSTO")
        mixto = [dict(base, exceso_spy_pp=(-1 if i < 4 else 2)) for i in range(9)]
        self.assertEqual(clasificar_robustez(mixto), "MIXTO")
        debil = [dict(base, retorno_pct=-1, exceso_spy_pp=-2) for _ in range(9)]
        self.assertEqual(clasificar_robustez(debil), "DEBIL")

    def test_informe_no_selecciona_mejor_estrategia(self):
        filas = generar_escenarios(self.resultados, {"SPY": []}, simulador_falso)
        cobertura = {
            (s, h): {"con_resultado_futuro": 1, "senales_reconstruidas": 2}
            for s in ("momentum", "reversal") for h in (5, 20)
        }
        salida = io.StringIO()
        with redirect_stdout(salida):
            imprimir_informe(
                filas, cobertura,
                {"cache_hits": 1, "symbols": 1, "filas_descargadas": 0},
            )
        texto = salida.getvalue().lower()
        self.assertIn("research / in-sample", texto)
        self.assertNotIn("mejor estrategia", texto)

    def test_csv_solo_se_crea_al_invocar_exportacion(self):
        filas = generar_escenarios(self.resultados, {"SPY": []}, simulador_falso)
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "sensibilidad.csv"
            self.assertFalse(ruta.exists())
            exportar_csv(filas, ruta)
            self.assertTrue(ruta.exists())
            self.assertEqual(len(ruta.read_text(encoding="utf-8").splitlines()), 37)


if __name__ == "__main__":
    unittest.main()
