import io
import unittest
from contextlib import redirect_stdout

from research.portfolio_whatif import (
    calcular_max_drawdown,
    calcular_benchmark_spy,
    clave_ranking,
    construir_indice_resultados_futuros,
    filtrar_resultados,
    imprimir_resumen,
    evaluar_senal_historica,
    parsear_fecha,
    reconstruir_senales_research,
    simular_cartera,
)


def resultado(
    symbol,
    signal_date,
    entry_date,
    exit_date,
    entry_price=100.0,
    exit_price=110.0,
    prioridad="A",
    score=90,
    strategy="MOMENTUM",
):
    return {
        "signal_id": hash(
            (symbol, signal_date, entry_date, exit_date)
        ),
        "symbol": symbol,
        "strategy": strategy,
        "source_score_version": "v4",
        "score_version": (
            "reversal_v1"
            if strategy == "REVERSAL"
            else "v4"
        ),
        "prioridad": prioridad,
        "score": score,
        "horizonte": 20,
        "market_date": signal_date,
        "fecha_entrada": entry_date,
        "fecha_salida": exit_date,
        "precio_entrada": entry_price,
        "precio_salida": exit_price,
    }


class PortfolioWhatIfTest(unittest.TestCase):

    def barras(self, cantidad=65, symbol=None):
        from datetime import date, timedelta
        inicio = date(2026, 1, 2)
        return [
            {
                "date": inicio + timedelta(days=indice),
                "open": 100 + indice,
                "high": 102 + indice,
                "low": 98 + indice,
                "close": 101 + indice,
            }
            for indice in range(cantidad)
        ]

    def scan_momentum(self, symbol="AAA"):
        return {
            "symbol": symbol,
            "market_date": "2026-01-01",
            "prioridad_estudio": "D",
            "tendencia": "FUERTE ALCISTA",
            "rsi": 67,
            "fuerza_20d": 20,
            "fuerza_60d": 35,
            "fuerza_sector_20d": 12,
            "fuerza_sector_60d": 25,
            "distancia_sma20": 12,
            "volumen_relativo": 2,
            "volatilidad": "ALTA",
        }

    def scan_reversal(self, symbol="REV"):
        return {
            "symbol": symbol,
            "market_date": "2026-01-01",
            "prioridad_estudio": "A+",
            "tendencia": "BAJISTA FUERTE",
            "rsi": 30,
            "fuerza_20d": -20,
            "fuerza_60d": -30,
            "fuerza_sector_20d": -20,
            "fuerza_sector_60d": -20,
            "distancia_sma20": -15,
            "volumen_relativo": 0.1,
            "volatilidad": "MUY ALTA",
        }

    def test_costes_entrada_y_salida(self):
        simulacion = simular_cartera(
            [
                resultado(
                    "AAA",
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-30",
                )
            ],
            capital=1000,
            strategy="momentum",
            holding=20,
            max_positions=1,
            cost_pct=1.0,
        )

        self.assertAlmostEqual(
            simulacion["capital_final"],
            1078.11
        )
        self.assertAlmostEqual(
            simulacion["trades"][0]["return_pct"],
            7.811
        )

    def test_no_supera_max_positions_y_no_duplica_symbol(self):
        datos = [
            resultado("AAA", "2026-01-01", "2026-01-02", "2026-01-20"),
            resultado("BBB", "2026-01-01", "2026-01-02", "2026-01-10"),
            resultado("AAA", "2026-01-09", "2026-01-10", "2026-02-06"),
            resultado("CCC", "2026-01-09", "2026-01-10", "2026-02-06"),
            resultado("DDD", "2026-01-09", "2026-01-10", "2026-02-06"),
        ]

        simulacion = simular_cartera(
            datos,
            capital=1000,
            strategy="momentum",
            holding=20,
            top=5,
            max_positions=2,
            cost_pct=0,
        )

        self.assertLessEqual(
            simulacion["max_posiciones_simultaneas"],
            2
        )
        entradas_aaa = [
            trade
            for trade in simulacion["trades"]
            if trade["symbol"] == "AAA"
        ]
        self.assertEqual(len(entradas_aaa), 1)
        self.assertIn(
            "CCC",
            {trade["symbol"] for trade in simulacion["trades"]}
        )

    def test_libera_y_reinvierte_capital(self):
        datos = [
            resultado("AAA", "2026-01-01", "2026-01-02", "2026-01-10"),
            resultado("BBB", "2026-01-09", "2026-01-10", "2026-02-06"),
        ]
        simulacion = simular_cartera(
            datos,
            capital=1000,
            strategy="momentum",
            holding=20,
            max_positions=1,
            cost_pct=0,
        )

        self.assertEqual(simulacion["operaciones"], 2)
        self.assertAlmostEqual(
            simulacion["trades"][1]["capital_allocated"],
            1100.0
        )
        self.assertAlmostEqual(
            simulacion["capital_final"],
            1210.0
        )

    def test_max_drawdown_equity_curve(self):
        curva = [
            {"equity": 100.0},
            {"equity": 120.0},
            {"equity": 90.0},
            {"equity": 110.0},
        ]
        self.assertAlmostEqual(
            calcular_max_drawdown(curva),
            -25.0
        )

    def test_ranking_momentum(self):
        datos = [
            {"symbol": "A", "prioridad": "A", "score": 99},
            {"symbol": "B", "prioridad": "A+", "score": 90},
            {"symbol": "C", "prioridad": "A+", "score": 95},
        ]
        orden = sorted(
            datos,
            key=lambda fila: clave_ranking(fila, "momentum")
        )
        self.assertEqual(
            [fila["symbol"] for fila in orden],
            ["C", "B", "A"]
        )

    def test_ranking_reversal(self):
        datos = [
            {"symbol": "A", "score": 40},
            {"symbol": "B", "score": 60},
        ]
        orden = sorted(
            datos,
            key=lambda fila: clave_ranking(fila, "reversal")
        )
        self.assertEqual(
            [fila["symbol"] for fila in orden],
            ["B", "A"]
        )

    def test_no_look_ahead(self):
        invalido = resultado(
            "FUTURE",
            "2026-01-03",
            "2026-01-02",
            "2026-01-30",
        )
        valido = resultado(
            "VALID",
            "2026-01-01",
            "2026-01-02",
            "2026-01-30",
        )

        filtrados = filtrar_resultados(
            [invalido, valido],
            "momentum",
            20
        )

        self.assertEqual(
            [fila["symbol"] for fila in filtrados],
            ["VALID"]
        )

    def test_research_recalcula_v4_y_reutiliza_resultado(self):
        futuro = resultado(
            "AAA",
            "2026-01-01",
            "2026-01-02",
            "2026-01-30",
            entry_price=50,
            exit_price=60,
            prioridad="D",
            score=1,
        )
        senales, metadata = reconstruir_senales_research(
            [self.scan_momentum()],
            [futuro],
            "momentum",
            20
        )

        self.assertEqual(metadata["senales_reconstruidas"], 1)
        self.assertEqual(metadata["con_resultado_futuro"], 1)
        self.assertEqual(senales[0]["prioridad"], "A+")
        self.assertEqual(senales[0]["score"], 100)
        self.assertEqual(senales[0]["precio_entrada"], 50)
        self.assertEqual(senales[0]["precio_salida"], 60)

    def test_research_reversal_usa_regla_oficial(self):
        futuro = resultado(
            "REV",
            "2026-01-01",
            "2026-01-02",
            "2026-01-30",
            strategy="MOMENTUM",
        )
        senales, metadata = reconstruir_senales_research(
            [self.scan_reversal()],
            [futuro],
            "reversal",
            20
        )

        self.assertEqual(metadata["senales_reconstruidas"], 1)
        self.assertEqual(senales[0]["strategy"], "REVERSAL")
        self.assertEqual(senales[0]["score_version"], "reversal_v1")
        self.assertEqual(senales[0]["prioridad"], "A")

    def test_resultados_futuros_duplicados(self):
        primero = resultado(
            "AAA", "2026-01-01", "2026-01-02", "2026-01-30"
        )
        primero["id"] = 1
        segundo = dict(primero)
        segundo["id"] = 2
        segundo["precio_salida"] = 120

        indice, diagnostico = construir_indice_resultados_futuros(
            [segundo, primero],
            20
        )

        self.assertEqual(
            indice[("AAA", "2026-01-01", 20)]["id"],
            1
        )
        self.assertEqual(diagnostico["duplicados_resultado"], 1)
        self.assertEqual(diagnostico["duplicados_inconsistentes"], 1)

    def test_etiqueta_research_in_sample(self):
        simulacion = simular_cartera(
            [],
            strategy="momentum",
            holding=20
        )
        salida = io.StringIO()

        with redirect_stdout(salida):
            imprimir_resumen(
                simulacion,
                mode="research",
                metadata={
                    "senales_reconstruidas": 0,
                    "con_resultado_futuro": 0,
                    "duplicados_resultado": 0,
                    "duplicados_inconsistentes": 0,
                }
            )

        texto = salida.getvalue()
        self.assertIn("PORTFOLIO WHAT-IF - RESEARCH", texto)
        self.assertIn("in-sample", texto)
        self.assertIn("No representa validacion out-of-sample", texto)

    def test_ohlc_entrada_siguiente_y_salida_sesion_cinco(self):
        senal = {
            "symbol": "AAA", "market_date": "2026-01-01",
            "strategy": "MOMENTUM", "source_score_version": "v4",
            "score_version": "v4", "prioridad": "A", "score": 90,
        }
        evaluada, estado = evaluar_senal_historica(senal, self.barras(), 5)
        self.assertEqual(estado, "completa")
        self.assertEqual(evaluada["fecha_entrada"], "2026-01-02")
        self.assertEqual(evaluada["fecha_salida"], "2026-01-06")
        self.assertEqual(evaluada["precio_entrada"], 100)
        self.assertEqual(evaluada["precio_salida"], 105)
        self.assertAlmostEqual(evaluada["mfe_pct"], 6.0)
        self.assertAlmostEqual(evaluada["mae_pct"], -2.0)

    def test_ohlc_desfase_20_y_60_sesiones(self):
        senal = {
            "symbol": "AAA", "market_date": "2026-01-01",
            "strategy": "MOMENTUM", "source_score_version": "v4",
            "score_version": "v4", "prioridad": "A", "score": 90,
        }
        veinte, _ = evaluar_senal_historica(senal, self.barras(), 20)
        sesenta, _ = evaluar_senal_historica(senal, self.barras(), 60)
        self.assertEqual(veinte["precio_salida"], 120)
        self.assertEqual(sesenta["precio_salida"], 160)

    def test_mark_to_market_refleja_cierre_intermedio(self):
        candidato = resultado(
            "AAA", "2026-01-01", "2026-01-02", "2026-01-04",
            entry_price=100, exit_price=100,
        )
        barras = [
            {"date": "2026-01-02", "open": 100, "high": 100, "low": 100, "close": 100},
            {"date": "2026-01-03", "open": 100, "high": 100, "low": 50, "close": 50},
            {"date": "2026-01-04", "open": 50, "high": 100, "low": 50, "close": 100},
        ]
        simulacion = simular_cartera(
            [candidato], capital=1000, strategy="momentum", holding=20,
            max_positions=1, cost_pct=0, historicos={"AAA": barras},
            spy_bars=barras,
        )
        self.assertAlmostEqual(simulacion["max_drawdown_pct"], -50.0)
        self.assertTrue(simulacion["mtm_real"])

    def test_benchmark_spy_aplica_coste_en_ambos_lados(self):
        barras = [
            {"date": "2026-01-02", "open": 100, "high": 100, "low": 100, "close": 100},
            {"date": "2026-01-03", "open": 110, "high": 110, "low": 110, "close": 110},
        ]
        benchmark = calcular_benchmark_spy(
            barras,
            parsear_fecha("2026-01-02"),
            parsear_fecha("2026-01-03"),
            1000,
            1.0,
        )
        self.assertAlmostEqual(benchmark["capital_final"], 1078.11)


if __name__ == "__main__":
    unittest.main()
