import sqlite3

import pandas as pd

from research.signal_interaction_analysis import incremental_value
from research.signal_interaction_dataset import (
    build_signal_dataset, feature_dictionary, temporal_asof_join,
)
from research.signal_interaction_research import run
from research.signal_interaction_validation import temporal_validation, validate_dataset


def _database(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE paper_signals (id INTEGER, market_date TEXT, scan_time TEXT,
      symbol TEXT, prioridad TEXT, score REAL, sector TEXT, created_at TEXT,
      strategy TEXT, source_score_version TEXT, variant TEXT);
    CREATE TABLE scans (id INTEGER, market_date TEXT, scan_time TEXT, symbol TEXT,
      score_version TEXT, prioridad_estudio TEXT, sector TEXT, sector_benchmark TEXT,
      fortaleza_sector TEXT, riesgo_clasificacion TEXT, score REAL,
      score_tendencia REAL, score_momentum REAL, score_fuerza REAL,
      score_sector REAL, score_continuacion REAL, score_volumen REAL, rsi REAL,
      fuerza_20d REAL, fuerza_60d REAL, fuerza_sector_20d REAL,
      fuerza_sector_60d REAL, distancia_sma20 REAL, distancia_sma50 REAL);
    CREATE TABLE paper_results (signal_id INTEGER, horizonte INTEGER,
      fecha_entrada TEXT, fecha_salida TEXT, holding_sessions_real INTEGER,
      retorno REAL, retorno_spy REAL, exceso_spy REAL, max_subida REAL,
      max_caida REAL, max_drawdown REAL, variant TEXT);
    CREATE TABLE fundamental_analysis (id INTEGER, symbol TEXT, created_at TEXT);
    CREATE TABLE fundamental_classification (fundamental_id INTEGER, symbol TEXT,
      score_fundamental REAL, calidad_fundamental TEXT, crecimiento TEXT,
      rentabilidad TEXT, balance TEXT, valoracion TEXT, created_at TEXT);
    CREATE TABLE analyst_consensus_snapshots (id INTEGER, symbol TEXT,
      snapshot_time TEXT, snapshot_date TEXT, upside_mean_pct REAL,
      consensus_score REAL, analyst_count INTEGER, target_mean REAL,
      eps_next_y REAL, source TEXT);
    CREATE TABLE news_context (id INTEGER, symbol TEXT, market_date TEXT,
      contexto TEXT, fuerza_catalizador TEXT, riesgo_narrativo TEXT,
      num_noticias INTEGER, analyzed_at TEXT);
    CREATE TABLE benchmark_scans (market_date TEXT, symbol TEXT, return_60d REAL);
    """)
    con.execute("INSERT INTO paper_signals VALUES (1,'2020-01-02','2020-01-02 20:00','AAA','A',80,'TECH','2020-01-02 20:01','MOMENTUM','v4','BASE')")
    con.execute("INSERT INTO scans VALUES (1,'2020-01-02','2020-01-02 20:00','AAA','v4','A','TECH','XLK','FUERTE','BAJO',80,20,15,18,8,17,7,55,4,8,3,5,2,4)")
    con.execute("INSERT INTO paper_results VALUES (1,5,'2020-01-03','2020-01-10',5,2,1,1,3,-1,-1.5,'BASE')")
    con.execute("INSERT INTO fundamental_analysis VALUES (1,'AAA','2020-01-02 18:00')")
    con.execute("INSERT INTO fundamental_classification VALUES (1,'AAA',75,'SOLIDA','ALTO','ALTA','SOLIDO','RAZONABLE','2020-01-02 19:00')")
    con.execute("INSERT INTO analyst_consensus_snapshots VALUES (1,'AAA','2020-01-03 10:00','2020-01-03',20,0.5,10,120,6,'YAHOO')")
    con.execute("INSERT INTO news_context VALUES (1,'AAA','2020-01-02','POSITIVO','ALTO','BAJO',2,'2020-01-02 21:00')")
    con.execute("INSERT INTO benchmark_scans VALUES ('2020-01-02','SPY',4.0)")
    con.commit(); con.close()


def test_temporal_join_excludes_future_and_keeps_missing_rows():
    base = pd.DataFrame({"symbol": ["AAA", "BBB"],
                         "signal_time": pd.to_datetime(["2020-01-02", "2020-01-02"])})
    snapshots = pd.DataFrame({"symbol": ["AAA", "AAA"], "value": [1, 99],
                              "available_at": pd.to_datetime(["2020-01-01", "2020-01-03"])})
    result = temporal_asof_join(base, snapshots, ["value", "available_at"])
    assert result.loc[0, "value"] == 1
    assert pd.isna(result.loc[1, "value"])
    assert len(result) == 2


def test_dataset_uses_prior_snapshots_and_same_date_benchmark(tmp_path):
    db = tmp_path / "research.db"; _database(db)
    data = build_signal_dataset(db)
    assert len(data) == 1
    assert data.loc[0, "score_fundamental"] == 75
    assert pd.isna(data.loc[0, "consensus_score"])
    assert pd.isna(data.loc[0, "news_context"])
    assert data.loc[0, "spy_momentum60"] == 4
    assert data.loc[0, "market_regime"] == "RISK_ON"
    assert data.loc[0, "holding_sessions_real_5d"] == 5
    assert data.loc[0, "exceso_spy_5d"] == 1
    assert data.loc[0, "missing_analyst"] == 1
    assert data.loc[0, "missing_news"] == 1
    assert not validate_dataset(data)


def test_research_is_reproducible_and_writes_all_outputs(tmp_path):
    db = tmp_path / "research.db"; _database(db)
    out1, report1 = run(tmp_path / "one", db)
    out2, report2 = run(tmp_path / "two", db)
    assert report1 == report2
    assert set(out1) == set(out2)
    assert len(out1) == 10
    assert (tmp_path / "one" / "signal_interaction_report.txt").exists()


def test_fixed_temporal_split_and_walk_forward_do_not_leak(tmp_path):
    db = tmp_path / "research.db"; _database(db)
    data = build_signal_dataset(db); dictionary = feature_dictionary()
    incremental = incremental_value(data, dictionary)
    assert set(incremental["classification"]) == {"INSUFFICIENT_DATA"}
    walk = temporal_validation(data, dictionary)
    annual = walk[walk["validation"] == "annual_walk_forward"]
    assert set(annual["status"]) == {"INSUFFICIENT_DATA"}
    assert (annual["train_n"] == 0).all()


def test_research_modules_do_not_import_production_runners():
    paths = ["research/signal_interaction_dataset.py",
             "research/signal_interaction_analysis.py",
             "research/signal_interaction_validation.py",
             "research/signal_interaction_research.py"]
    source = "\n".join(open(path, encoding="utf-8").read() for path in paths)
    assert "import weekly_report" not in source
    assert "from weekly_report" not in source
    assert "import paper_portfolios_runner" not in source
    assert "from paper_portfolios_runner" not in source
