from io import BytesIO
import zipfile

import numpy as np
import pandas as pd

from providers.cnmv_funds import extraer_zip_cnmv, importar_csv_manual
from research.funds_analysis import (
    analizar_persistencia, calcular_metricas, estrategias_simples,
)
from research.funds_research import construir_benchmarks, normalizar_fecha_fin


def zip_cnmv():
    mens = b'''<FondMens><FechaDatos>202402</FechaDatos><Entidad><NumeroRegistro>1</NumeroRegistro>
    <Compartimento><Clase><ISIN>ES0000000001</ISIN><VLDiario><VL_Dia1>10</VL_Dia1>
    <VL_Dia28>11</VL_Dia28><VL_Dia30>999</VL_Dia30></VLDiario></Clase></Compartimento>
    </Entidad></FondMens>'''
    registro = b'''<FondRegistro><Entidad><NumeroRegistro>1</NumeroRegistro><Denominacion>FONDO TEST</Denominacion>
    <Compartimento><Clase><DenominacionClase>CLASE A</DenominacionClase><ISIN>ES0000000001</ISIN></Clase></Compartimento>
    <Gestora><DenominacionGestora>GESTORA TEST</DenominacionGestora></Gestora></Entidad></FondRegistro>'''
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("FONDMENS_Documento Explicativo.pdf", b"%PDF-test")
        z.writestr("FONDMENS_202402.XML", mens)
        z.writestr("FONDREGISTRO_202402.XML", registro)
    return buffer.getvalue()


def test_parser_cnmv_usa_ultimo_dia_valido_y_clase_filtrada():
    nav, meta = extraer_zip_cnmv(zip_cnmv(), {"ES0000000001"})
    assert nav.iloc[0]["date"] == "2024-02-28"
    assert nav.iloc[0]["nav"] == 11
    assert meta.iloc[0]["share_class"] == "CLASE A"


def test_csv_manual_no_interpola(tmp_path):
    ruta = tmp_path / "manual.csv"
    pd.DataFrame({"date": ["2024-01-31", "2024-03-31"], "nav": [10, 12]}).to_csv(ruta, index=False)
    datos = importar_csv_manual(ruta, "ES0000000001")
    assert len(datos) == 2
    assert list(datos["date"].dt.month) == [1, 3]


def test_metricas_y_benchmark_usan_ventana_comun():
    fechas = pd.date_range("2019-01-31", periods=72, freq="ME")
    fondo = pd.Series(np.linspace(100, 180, 72), index=fechas)
    benchmark = pd.Series(np.linspace(100, 150, 60), index=fechas[12:])
    m = calcular_metricas(fondo, benchmark)
    assert m["observations"] == 72
    assert str(m["benchmark_common_start"]) == str(fechas[12].date())
    assert 0 <= m["positive_years_pct"] <= 1


def test_walk_forward_no_emite_resultado_sin_horizonte_futuro_completo():
    fechas = pd.date_range("2016-01-31", periods=84, freq="ME")
    series = {
        "A": pd.Series(np.linspace(100, 180, 84), index=fechas),
        "B": pd.Series(np.linspace(100, 150, 84), index=fechas),
        "C": pd.Series(np.linspace(100, 130, 84), index=fechas),
    }
    universo = pd.DataFrame({"isin": list(series), "benchmark": ["BM"] * 3})
    benchmark = {"BM": pd.Series(np.linspace(100, 140, 84), index=fechas)}
    resultado = analizar_persistencia(series, benchmark, universo, horizontes=(12,))
    assert not resultado.empty
    fechas_ranking = pd.to_datetime(resultado["ranking_date"])
    assert all(fechas_ranking <= fechas[-13])


def test_estrategias_seleccionan_solo_con_36_meses_previos():
    fechas = pd.date_range("2016-01-31", periods=96, freq="ME")
    series = {letra: pd.Series(100 * (1 + tasa) ** np.arange(96), index=fechas)
              for letra, tasa in zip("ABCD", (.01, .008, .006, .004))}
    universo = pd.DataFrame({"isin": list(series), "benchmark": ["BM"] * 4})
    benchmarks = {"BM": pd.Series(100 * 1.005 ** np.arange(96), index=fechas)}
    resultado = estrategias_simples(series, benchmarks, universo)
    assert not resultado.empty
    assert resultado["selected_isins"].str.contains("A").any()
    assert pd.to_datetime(resultado["rebalance_date"]).min() >= pd.Timestamp("2018-12-31")


def test_fecha_fin_mensual_se_convierte_a_ultimo_dia():
    assert normalizar_fecha_fin("2025-12") == "2025-12-31"


def test_benchmarks_usan_close_ajustado_y_construyen_60_40(tmp_path, monkeypatch):
    import research.funds_research as modulo
    monkeypatch.setattr(modulo, "CACHE_DIR", tmp_path)
    indice = pd.date_range("2020-01-02", periods=800, freq="B")
    def downloader(symbol):
        factor = 1.001 if symbol == "SPY" else 1.0005
        return pd.DataFrame({"Close": 100 * factor ** np.arange(len(indice))}, index=indice)
    benchmarks, info = construir_benchmarks("2020-01-01", "2022-12-31", downloader=downloader)
    assert "SPY" in benchmarks and "60_40" in benchmarks
    assert info["filas_descargadas"] > 0
    assert (tmp_path / "benchmark_monthly.csv").exists()
