from pathlib import Path

import pandas as pd

from reporting.weekly_charts import generar_graficos_weekly, normalizar_curvas_comunes
from reporting.weekly_html import generar_html_weekly
from weekly_report import (
    clasificar_estado_portfolio,
    guardar_preview_weekly,
    portfolios_elegibles_highlights,
    estrategias_operativas,
)


def datos_minimos():
    nombres = [
        "MOMENTUM_LIVE", "REVERSAL_LIVE", "ETF_TOP2_CANDIDATE",
        "DEFENSIVE_CANDIDATE", "SPY_BUY_HOLD", "BALANCED_60_40",
        "SHY_BUY_HOLD",
    ]
    portfolios = []
    for nombre in nombres:
        benchmark = nombre in {"SPY_BUY_HOLD", "BALANCED_60_40", "SHY_BUY_HOLD"}
        portfolios.append({
            "name": nombre, "label": nombre, "benchmark": benchmark,
            "equity": 10_050, "return": 0.5, "maxdd": -1.0,
            "excess": 0.1, "status": "BENCHMARK" if benchmark else "EARLY",
            "operational": True,
            "objective": "Objetivo de prueba", "open_count": 1, "cash": 100,
            "defensive_state": "RISK_ON", "position": "SPY",
            "spy_momentum60": 0.03, "last_rebalance": "2026-09-02",
        })
    return {
        "meta": {"generated": "02/09/2026", "market_date": "2026-09-02",
                 "score_version": "v4", "scans": 7},
        "overview": {"a_plus": 1, "a": 2, "b": 3, "c": 4, "d": 5,
                     "assets": 15, "news_positive": 2, "news_mixed": 1,
                     "news_negative": 1, "fund_excellent": 1,
                     "fund_solid": 2, "fund_weak": 1},
        "weekly_context": "Contexto prudente.", "portfolios": portfolios,
        "persistent": ["AAA 7/7 scans"], "improving": ["BBB +6 -> 80/100"],
        "events": ["CCC | EVENTO"], "top_candidates": [],
        "paper_tracking": [{"title": "Momentum", "rows": [{
            "horizon": "5D", "n": 10, "return": 1.0, "excess": .5, "beat": 60,
        }]}],
        "highlights": [("Mayor rentabilidad", "Candidato validado")],
        "plain_text": "INFORME ORIGINAL COMPLETO", "charts": {},
    }


def test_html_contiene_dashboard_siete_carteras_y_texto_original():
    html = generar_html_weekly(datos_minimos())
    assert html.startswith("<!doctype html>")
    assert html.count("Objetivo de prueba") == 4
    assert "COMPARATIVA DE CARTERAS" in html
    assert "Resultados fuera de muestra (OOS)" in html
    assert "DEFENSIVE_CANDIDATE" in html and "RIESGO ACTIVO · SPY" in html
    assert "INFORME ORIGINAL COMPLETO" in html
    assert "suficiente historial" in html


def test_curvas_exigen_fecha_base_exacta_y_normalizan_a_10000(tmp_path):
    curvas = {
        "valida": pd.Series([9_000, 9_900], index=["2026-09-02", "2026-09-03"]),
        "sin_base": pd.Series([10_100], index=["2026-09-03"]),
    }
    normalizadas = normalizar_curvas_comunes(curvas)
    assert list(normalizadas) == ["valida"]
    assert normalizadas["valida"].iloc[0] == 10_000
    rutas = generar_graficos_weekly(curvas, tmp_path)
    assert Path(rutas["equity"]).exists()
    assert Path(rutas["return_drawdown"]).exists()


def test_fallo_de_grafico_se_degrada_sin_excepcion(tmp_path, monkeypatch):
    import reporting.weekly_charts as charts
    monkeypatch.setattr(
        charts,
        "normalizar_curvas_comunes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fallo simulado"))
    )
    resultado = charts.generar_graficos_weekly({}, tmp_path)
    assert resultado["equity"] is None
    assert "fallo simulado" in resultado["error"]


def test_estado_usa_benchmark_comun_y_no_etiqueta_estable_muestra_corta():
    cartera = {"name": "MOMENTUM_LIVE", "common_return_pct": -6}
    assert clasificar_estado_portfolio(cartera, 10, 0) == "EARLY"
    assert clasificar_estado_portfolio(cartera, 25, -1) == "WEAK"
    assert clasificar_estado_portfolio({"name": "SPY_BUY_HOLD"}, 0, None) == "BENCHMARK"


def test_sin_primera_ejecucion_es_early_y_no_es_elegible_para_highlight():
    cartera = {"name": "DEFENSIVE_CANDIDATE", "common_return_pct": 0.0}
    assert clasificar_estado_portfolio(cartera, 80, 0.0, False) == "EARLY"
    portfolios = [
        {"name": "DEFENSIVE_CANDIDATE", "operational": False,
         "return": 0.0, "maxdd": 0.0},
        {"name": "MOMENTUM_LIVE", "operational": True,
         "return": -1.0, "maxdd": -2.0},
    ]
    assert [p["name"] for p in portfolios_elegibles_highlights(portfolios)] == [
        "MOMENTUM_LIVE"
    ]
    portfolios[0]["benchmark"] = False
    portfolios[1]["benchmark"] = False
    assert [p["name"] for p in estrategias_operativas(portfolios)] == [
        "MOMENTUM_LIVE"
    ]


def test_defensive_sin_operar_muestra_espera_y_cash():
    datos = datos_minimos()
    defensive = next(p for p in datos["portfolios"] if p["name"] == "DEFENSIVE_CANDIDATE")
    defensive.update({
        "status": "EARLY",
        "operational": False,
        "defensive_state": "WAITING FIRST MONTHLY SIGNAL",
        "position": "100% CASH",
        "last_rebalance": "WAITING FIRST MONTHLY SIGNAL",
    })
    html = generar_html_weekly(datos)
    assert "PENDIENTE DE LA PRIMERA SEÑAL MENSUAL" in html
    assert "100% efectivo" in html


def test_html_no_muestra_rotulos_ingleses_prohibidos():
    html = generar_html_weekly(datos_minimos())
    prohibidos = [
        "Highest Return", "Lowest Drawdown", "What Happened This Week",
        "Top Candidates", "Waiting First Monthly Signal",
        "Current allocation", "Benchmark", "Weekly Report",
        "Portfolio Scoreboard", "Strategy Details", "How to Read",
        "Buy & Hold", "Not available", "Forward / OOS results",
    ]
    for texto_ingles in prohibidos:
        assert texto_ingles.lower() not in html.lower()


def test_preview_reemplaza_cid(tmp_path, monkeypatch):
    import weekly_report
    monkeypatch.setattr(weekly_report, "__file__", str(tmp_path / "weekly_report.py"))
    imagen = tmp_path / "data" / "reports" / "weekly_equity.png"
    imagen.parent.mkdir(parents=True)
    imagen.write_bytes(b"png")
    destino = guardar_preview_weekly(
        '<img src="cid:weekly_equity">', {"charts": {"equity": imagen}}
    )
    assert 'src="weekly_equity.png"' in destino.read_text(encoding="utf-8")
