"""Investigación histórica de factores ETF, sin score ni integración productiva.

Sesgos conocidos: el universo es una selección de ETFs que existen hoy (survivorship
bias). Las features usan exclusivamente datos disponibles al cierre de la señal. La
entrada se realiza en la apertura de la sesión siguiente y los umbrales de las
combinaciones son fijos o percentiles transversales conocidos en esa misma fecha.
Los quintiles son descriptivos de toda la muestra y no deben interpretarse como
umbrales validados fuera de muestra.
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_universe import ETF_UNIVERSE, validate_universe


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "research_etf"
CACHE_DIR = OUTPUT_DIR / "price_cache"
HORIZONS = (5, 20, 60)
FACTOR_FEATURES = (
    "momentum20", "momentum60", "momentum120", "rs20", "rs60", "rs120",
    "volatility20", "distance_sma20", "drawdown60",
)


def calcular_rsi(close, period=14):
    delta = close.diff()
    ganancias = delta.clip(lower=0)
    perdidas = -delta.clip(upper=0)
    media_ganancias = ganancias.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    media_perdidas = perdidas.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = media_ganancias / media_perdidas.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((media_perdidas == 0) & (media_ganancias > 0), 100.0)
    return rsi.mask((media_perdidas == 0) & (media_ganancias == 0), 50.0)


def calcular_features_precios(datos, spy_close):
    """Calcula features contemporáneas; nunca desplaza datos futuros hacia atrás."""
    df = datos.sort_index().copy()
    close = df["close"].astype(float)
    spy = spy_close.reindex(df.index).astype(float)
    retornos_diarios = close.pct_change()

    for ventana in (20, 50, 200):
        df[f"sma{ventana}"] = close.rolling(ventana, min_periods=ventana).mean()
        df[f"price_gt_sma{ventana}"] = close > df[f"sma{ventana}"]
        df[f"distance_sma{ventana}"] = (close / df[f"sma{ventana}"] - 1) * 100
    df["sma20_gt_sma50"] = df["sma20"] > df["sma50"]
    df["sma50_gt_sma200"] = df["sma50"] > df["sma200"]

    for ventana in (5, 20, 60, 120):
        df[f"momentum{ventana}"] = close.pct_change(ventana) * 100
    df["rsi14"] = calcular_rsi(close)

    for ventana in (20, 60, 120):
        spy_retorno = spy.pct_change(ventana) * 100
        df[f"rs{ventana}"] = df[f"momentum{ventana}"] - spy_retorno
        df[f"drawdown{ventana}"] = (close / close.rolling(ventana).max() - 1) * 100
    for ventana in (20, 60):
        df[f"volatility{ventana}"] = (
            retornos_diarios.rolling(ventana).std(ddof=1) * np.sqrt(252) * 100
        )

    volumen = df["volume"].astype(float) if "volume" in df else pd.Series(np.nan, index=df.index)
    df["avg_volume20"] = volumen.rolling(20).mean()
    df["avg_dollar_volume20"] = (close * volumen).rolling(20).mean()
    return df


def agregar_outcomes(datos, spy, horizons=HORIZONS):
    """Entrada next-open y salida al cierre de la h-ésima sesión posterior."""
    df = datos.copy()
    spy_alineado = spy.reindex(df.index)
    entry = df["open"].shift(-1)
    spy_entry = spy_alineado["open"].shift(-1)
    df["entry_date"] = pd.Series(df.index, index=df.index).shift(-1)
    df["entry_price"] = entry

    for horizonte in horizons:
        exit_close = df["close"].shift(-horizonte)
        spy_exit = spy_alineado["close"].shift(-horizonte)
        df[f"future_return_{horizonte}"] = (exit_close / entry - 1) * 100
        df[f"spy_future_return_{horizonte}"] = (spy_exit / spy_entry - 1) * 100
        df[f"future_excess_{horizonte}"] = (
            df[f"future_return_{horizonte}"] - df[f"spy_future_return_{horizonte}"]
        )
        maximos = pd.concat(
            [df["high"].shift(-paso) for paso in range(1, horizonte + 1)], axis=1
        ).max(axis=1)
        minimos = pd.concat(
            [df["low"].shift(-paso) for paso in range(1, horizonte + 1)], axis=1
        ).min(axis=1)
        df[f"mfe_{horizonte}"] = (maximos / entry - 1) * 100
        df[f"mae_{horizonte}"] = (minimos / entry - 1) * 100
        incompleto = df["close"].shift(-horizonte).isna()
        df.loc[incompleto, [
            f"future_return_{horizonte}", f"spy_future_return_{horizonte}",
            f"future_excess_{horizonte}", f"mfe_{horizonte}", f"mae_{horizonte}"
        ]] = np.nan
    return df


def clasificar_quintiles(serie, grupos=5):
    """Devuelve Q1..Q5; tolera empates y datos insuficientes."""
    resultado = pd.Series(pd.NA, index=serie.index, dtype="object")
    validos = serie.dropna()
    if len(validos) < grupos:
        return resultado
    ranked = validos.rank(method="average", pct=True)
    codigos = np.minimum(np.ceil(ranked * grupos).astype(int), grupos)
    resultado.loc[validos.index] = [f"Q{codigo}" for codigo in codigos]
    return resultado


def _normalizar_descarga(datos):
    if datos.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if getattr(datos.columns, "nlevels", 1) > 1:
        datos.columns = datos.columns.get_level_values(0)
    columnas = {str(col).lower().replace(" ", "_"): col for col in datos.columns}
    renombradas = {}
    for destino, candidatos in {
        "open": ("open",), "high": ("high",), "low": ("low",),
        "close": ("close",), "volume": ("volume",),
    }.items():
        for candidato in candidatos:
            if candidato in columnas:
                renombradas[columnas[candidato]] = destino
                break
    df = datos.rename(columns=renombradas)[list(renombradas.values())].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def obtener_precios(symbol, start, end, refresh=False, cache_dir=CACHE_DIR, downloader=None):
    """Caché incremental por ETF de OHLCV ajustado."""
    cache_dir = Path(cache_dir)
    ruta = cache_dir / f"{symbol}.csv"
    metadata_path = cache_dir / f"{symbol}.json"
    cache = pd.DataFrame()
    metadata = {}
    if ruta.exists() and not refresh:
        cache = pd.read_csv(ruta, parse_dates=["date"]).set_index("date").sort_index()
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                metadata = {}
    inicio = pd.Timestamp(start)
    fin = pd.Timestamp(end)
    cubre_peticion = (
        metadata.get("covered_start") and metadata.get("covered_end")
        and pd.Timestamp(metadata["covered_start"]) <= inicio
        and pd.Timestamp(metadata["covered_end"]) >= fin
    )
    necesita = refresh or cache.empty or not cubre_peticion
    if necesita:
        if downloader is None:
            import yfinance as yf
            yfinance_cache = cache_dir / ".yfinance"
            yfinance_cache.mkdir(parents=True, exist_ok=True)
            yf.cache.set_cache_location(str(yfinance_cache))
            downloader = lambda ticker, desde, hasta: yf.download(
                ticker, start=str(desde.date()), end=str((hasta + timedelta(days=1)).date()),
                auto_adjust=True, actions=False, progress=False, threads=False,
            )
        rangos = [(inicio, fin)] if cache.empty or refresh else []
        if not cache.empty and not refresh:
            if cache.index.min() > inicio:
                rangos.append((inicio, cache.index.min() - timedelta(days=1)))
            if cache.index.max() < fin:
                rangos.append((cache.index.max() + timedelta(days=1), fin))
        piezas = [cache] if not refresh else []
        for desde, hasta in rangos:
            if desde <= hasta:
                piezas.append(_normalizar_descarga(downloader(symbol, desde, hasta)))
        cache = pd.concat(piezas).sort_index()
        cache = cache[~cache.index.duplicated(keep="last")]
        if not cache.empty:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache.rename_axis("date").to_csv(ruta)
        cache_dir.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps({"covered_start": str(inicio.date()), "covered_end": str(fin.date())}),
            encoding="utf-8",
        )
    if cache.empty:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], name="date"),
        )
    return cache.loc[(cache.index >= inicio) & (cache.index <= fin)].copy()


def construir_dataset(historicos, start, end, horizons=HORIZONS):
    spy = historicos.get("SPY", pd.DataFrame())
    if spy.empty:
        raise ValueError("SPY es obligatorio como benchmark")
    filas = []
    catalogo = {etf.symbol: etf for etf in ETF_UNIVERSE}
    for symbol, precios in historicos.items():
        if symbol not in catalogo or precios.empty:
            continue
        features = calcular_features_precios(precios, spy["close"])
        completo = agregar_outcomes(features, spy, horizons)
        completo["symbol"] = symbol
        completo["name"] = catalogo[symbol].name
        completo["category"] = catalogo[symbol].category
        completo["signal_date"] = completo.index
        completo = completo.loc[(completo.index >= pd.Timestamp(start)) & (completo.index <= pd.Timestamp(end))]
        filas.append(completo.reset_index(drop=True))
    if not filas:
        return pd.DataFrame()
    dataset = pd.concat(filas, ignore_index=True)
    dataset = dataset.dropna(subset=["sma200", "momentum120", "entry_price"])
    dataset["rs60_rank"] = dataset.groupby("signal_date")["rs60"].rank(pct=True)
    dataset["volatility20_rank"] = dataset.groupby("signal_date")["volatility20"].rank(pct=True)
    return dataset.sort_values(["signal_date", "symbol"]).reset_index(drop=True)


def _estadisticas(grupo, horizonte):
    retorno = grupo[f"future_return_{horizonte}"].dropna()
    base = grupo.loc[retorno.index]
    if retorno.empty:
        return None
    exceso = base[f"future_excess_{horizonte}"]
    return {
        "n": len(retorno), "mean_return": retorno.mean(), "median_return": retorno.median(),
        "mean_spy": base[f"spy_future_return_{horizonte}"].mean(),
        "mean_excess": exceso.mean(), "win_rate": (retorno > 0).mean() * 100,
        "beat_spy": (exceso > 0).mean() * 100, "mean_mae": base[f"mae_{horizonte}"].mean(),
    }


def analizar_factores(dataset, features=FACTOR_FEATURES, horizons=HORIZONS, min_category_n=30):
    resultados = []
    for feature in features:
        ambitos = [("ALL", "ALL", dataset)]
        ambitos.extend(
            ("CATEGORY", categoria, grupo)
            for categoria, grupo in dataset.groupby("category") if len(grupo) >= min_category_n
        )
        for scope, categoria, ambito in ambitos:
            quintiles = clasificar_quintiles(ambito[feature])
            for quintil in ("Q1", "Q2", "Q3", "Q4", "Q5"):
                grupo = ambito.loc[quintiles == quintil]
                for horizonte in horizons:
                    stats = _estadisticas(grupo, horizonte)
                    if stats:
                        resultados.append({
                            "feature": feature, "scope": scope, "category": categoria,
                            "group": quintil, "horizon": horizonte, **stats,
                        })
    return pd.DataFrame(resultados)


def mascaras_combinaciones(dataset):
    tendencia_fuerte = dataset["price_gt_sma200"] & dataset["sma50_gt_sma200"]
    return {
        "A_price_sma200_rs60": dataset["price_gt_sma200"] & (dataset["rs60"] > 0),
        "B_trend_rs60_mom60": dataset["price_gt_sma200"] & (dataset["rs60"] > 0) & (dataset["momentum60"] > 0),
        "C_sma_stack_rs60": tendencia_fuerte & (dataset["rs60"] > 0),
        "D_trend_top_rs_low_vol": tendencia_fuerte & (dataset["rs60_rank"] >= .75) & (dataset["volatility20_rank"] < .75),
        "E_momentum_not_extended": (dataset["momentum60"] > 0) & (dataset["distance_sma20"].between(-2, 5)),
        "F_full_trend": dataset["price_gt_sma20"] & dataset["sma20_gt_sma50"] & dataset["sma50_gt_sma200"],
        "G_rs20_rs60_positive": (dataset["rs20"] > 0) & (dataset["rs60"] > 0),
        "H_trend_shallow_drawdown": tendencia_fuerte & (dataset["drawdown60"] > -5),
    }


def analizar_combinaciones(dataset, horizons=HORIZONS, min_category_n=30):
    resultados = []
    for nombre, mascara in mascaras_combinaciones(dataset).items():
        seleccionado = dataset.loc[mascara]
        ambitos = [("ALL", "ALL", seleccionado)]
        ambitos.extend(
            ("CATEGORY", categoria, grupo)
            for categoria, grupo in seleccionado.groupby("category") if len(grupo) >= min_category_n
        )
        for scope, categoria, grupo in ambitos:
            for horizonte in horizons:
                stats = _estadisticas(grupo, horizonte)
                if stats:
                    resultados.append({
                        "combination": nombre, "scope": scope, "category": categoria,
                        "horizon": horizonte, **stats,
                    })
    return pd.DataFrame(resultados)


def analizar_correlaciones(historicos, ventana=90, threshold=.90):
    cierres = pd.concat(
        {symbol: df["close"] for symbol, df in historicos.items() if not df.empty}, axis=1
    ).sort_index()
    retornos = cierres.pct_change(fill_method=None).tail(ventana)
    matriz = retornos.corr(min_periods=max(20, ventana // 2))
    categorias = {etf.symbol: etf.category for etf in ETF_UNIVERSE}
    filas = []
    for indice, a in enumerate(matriz.columns):
        for b in matriz.columns[indice + 1:]:
            correlacion = matriz.at[a, b]
            if pd.notna(correlacion):
                filas.append({
                    "symbol_a": a, "symbol_b": b, "correlation": correlacion,
                    "category_a": categorias.get(a), "category_b": categorias.get(b),
                    "very_high": correlacion >= threshold,
                })
    return pd.DataFrame(filas).sort_values("correlation", ascending=False)


def resumir_correlaciones_categoria(correlaciones):
    mismas = correlaciones[
        correlaciones["category_a"] == correlaciones["category_b"]
    ]
    if mismas.empty:
        return pd.DataFrame(columns=["category", "pairs", "mean_correlation", "very_high_pairs"])
    return mismas.groupby("category_a").agg(
        pairs=("correlation", "size"),
        mean_correlation=("correlation", "mean"),
        very_high_pairs=("very_high", "sum"),
    ).reset_index().rename(columns={"category_a": "category"})


def analizar_buy_hold(historicos):
    """Comparación descriptiva del periodo disponible de cada ETF contra SPY."""
    spy = historicos["SPY"].dropna(subset=["close"])
    catalogo = {etf.symbol: etf for etf in ETF_UNIVERSE}
    filas = []
    for symbol, datos in historicos.items():
        datos = datos.dropna(subset=["close"])
        comunes = datos.index.intersection(spy.index)
        if len(comunes) < 2:
            continue
        etf_return = (datos.loc[comunes[-1], "close"] / datos.loc[comunes[0], "close"] - 1) * 100
        spy_return = (spy.loc[comunes[-1], "close"] / spy.loc[comunes[0], "close"] - 1) * 100
        filas.append({
            "symbol": symbol, "category": catalogo[symbol].category,
            "start_date": comunes[0], "end_date": comunes[-1], "sessions": len(comunes),
            "etf_return": etf_return, "spy_return": spy_return,
            "excess_vs_spy": etf_return - spy_return,
        })
    return pd.DataFrame(filas).sort_values("excess_vs_spy", ascending=False)


def imprimir_informe(dataset, factores, combinaciones, correlaciones, buy_hold, start, end):
    print("\nETF FACTOR RESEARCH")
    print("=" * 84)
    print(f"Periodo de señales: {start} a {end}")
    print(f"ETFs con datos: {dataset['symbol'].nunique()} | Observaciones: {len(dataset):,}")
    print("Entrada: siguiente apertura | Benchmark: SPY | Sin score ETF")
    for feature in FACTOR_FEATURES:
        print(f"\n{feature}")
        tabla = factores[(factores["feature"] == feature) & (factores["scope"] == "ALL")]
        for _, fila in tabla.iterrows():
            print(
                f"  {fila['group']} {int(fila['horizon']):>2}D | n={int(fila['n']):>6} | "
                f"Ret {fila['mean_return']:+.2f}% | Exc {fila['mean_excess']:+.2f}pp | "
                f"Win {fila['win_rate']:.1f}% | Beat {fila['beat_spy']:.1f}%"
            )
    print("\nTOP COMBINACIONES POR EXCESO 20D")
    top = combinaciones[(combinaciones["scope"] == "ALL") & (combinaciones["horizon"] == 20)]
    for _, fila in top.nlargest(10, "mean_excess").iterrows():
        print(f"  {fila['combination']:<30} n={int(fila['n']):>6} | Exc {fila['mean_excess']:+.2f}pp | Ret {fila['mean_return']:+.2f}%")
    altas = correlaciones[correlaciones["very_high"]]
    print(f"\nCorrelaciones últimas 90 sesiones: {len(altas)} pares >= 0.90")
    for _, fila in altas.head(15).iterrows():
        print(f"  {fila['symbol_a']:<5} {fila['symbol_b']:<5} {fila['correlation']:.3f}")
    print("\nBUY & HOLD VS SPY")
    for _, fila in buy_hold.head(10).iterrows():
        print(
            f"  {fila['symbol']:<5} Ret {fila['etf_return']:+.1f}% | "
            f"SPY {fila['spy_return']:+.1f}% | Exc {fila['excess_vs_spy']:+.1f}pp"
        )
    print("\nLIMITACIONES: survivorship bias; análisis in-sample descriptivo; no incluye costes, slippage ni validación walk-forward.")


def parse_args():
    parser = argparse.ArgumentParser(description="Investigación histórica de factores ETF")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--horizon", type=int, choices=HORIZONS)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument(
        "--save-dataset", action="store_true",
        help="Guarda el dataset reconstruible (puede superar 100 MB)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    validate_universe()
    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    descarga_inicio = start - timedelta(days=400)
    historicos = {}
    for indice, etf in enumerate(ETF_UNIVERSE, start=1):
        print(f"Precios ETF {indice}/{len(ETF_UNIVERSE)}: {etf.symbol}")
        historicos[etf.symbol] = obtener_precios(
            etf.symbol, descarga_inicio, end, refresh=args.refresh_cache
        )
    horizons = (args.horizon,) if args.horizon else HORIZONS
    dataset = construir_dataset(historicos, start, end, horizons)
    if dataset.empty:
        raise RuntimeError("No se pudo construir el dataset ETF")
    factores = analizar_factores(dataset, horizons=horizons)
    combinaciones = analizar_combinaciones(dataset, horizons=horizons)
    correlaciones = analizar_correlaciones(historicos)
    correlaciones_categoria = resumir_correlaciones_categoria(correlaciones)
    buy_hold = analizar_buy_hold(historicos)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.save_dataset:
        dataset.to_csv(OUTPUT_DIR / "etf_feature_dataset.csv", index=False)
    factores.to_csv(OUTPUT_DIR / "etf_factor_results.csv", index=False)
    combinaciones.to_csv(OUTPUT_DIR / "etf_combination_results.csv", index=False)
    correlaciones.to_csv(OUTPUT_DIR / "etf_correlations.csv", index=False)
    correlaciones_categoria.to_csv(OUTPUT_DIR / "etf_correlation_category_summary.csv", index=False)
    buy_hold.to_csv(OUTPUT_DIR / "etf_buy_hold.csv", index=False)
    imprimir_informe(dataset, factores, combinaciones, correlaciones, buy_hold, args.start, args.end)


if __name__ == "__main__":
    main()
