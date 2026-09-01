import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "research_price_cache"
YFINANCE_CACHE_DIR = CACHE_DIR / "yfinance"
COLUMNAS = ("date", "open", "high", "low", "close")


def _fecha(valor):
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def _symbol(symbol):
    return str(symbol or "").strip().upper()


def _cache_path(symbol, cache_dir):
    nombre = re.sub(r"[^A-Z0-9._-]", "_", _symbol(symbol))
    return Path(cache_dir) / f"{nombre}.csv"


def _metadata_path(symbol, cache_dir):
    return _cache_path(symbol, cache_dir).with_suffix(".json")


def _leer_metadata(symbol, cache_dir):
    ruta = _metadata_path(symbol, cache_dir)
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_metadata(symbol, inicio, fin, cache_dir):
    ruta = _metadata_path(symbol, cache_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(
            {"covered_start": str(inicio), "covered_end": str(fin)},
            indent=2,
        ),
        encoding="utf-8",
    )


def leer_cache(symbol, cache_dir=CACHE_DIR):
    ruta = _cache_path(symbol, cache_dir)

    if not ruta.exists():
        return []

    with ruta.open("r", newline="", encoding="utf-8") as archivo:
        filas = []
        for fila in csv.DictReader(archivo):
            try:
                filas.append(
                    {
                        "date": _fecha(fila["date"]),
                        "open": float(fila["open"]),
                        "high": float(fila["high"]),
                        "low": float(fila["low"]),
                        "close": float(fila["close"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

    return sorted(filas, key=lambda fila: fila["date"])


def guardar_cache(symbol, filas, cache_dir=CACHE_DIR):
    ruta = _cache_path(symbol, cache_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        for fila in sorted(filas, key=lambda item: item["date"]):
            escritor.writerow(
                {
                    **fila,
                    "date": str(fila["date"]),
                }
            )


def descargar_yfinance(symbol, start_date, end_date):
    import yfinance as yf

    YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.cache.set_cache_location(str(YFINANCE_CACHE_DIR))

    datos = yf.download(
        symbol,
        start=str(start_date),
        end=str(end_date + timedelta(days=1)),
        auto_adjust=False,
        progress=False,
        actions=False,
        threads=False,
    )

    if datos.empty:
        return []

    if getattr(datos.columns, "nlevels", 1) > 1:
        datos.columns = datos.columns.get_level_values(0)

    filas = []
    for indice, fila in datos.iterrows():
        try:
            filas.append(
                {
                    "date": indice.date(),
                    "open": float(fila["Open"]),
                    "high": float(fila["High"]),
                    "low": float(fila["Low"]),
                    "close": float(fila["Close"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    return filas


def obtener_historico(
    symbol,
    start_date,
    end_date,
    downloader=None,
    cache_dir=CACHE_DIR,
):
    symbol = _symbol(symbol)
    inicio = _fecha(start_date)
    fin = _fecha(end_date)
    cache = leer_cache(symbol, cache_dir)
    metadata = _leer_metadata(symbol, cache_dir)
    cubre_rango = (
        cache
        and metadata.get("covered_start")
        and metadata.get("covered_end")
        and _fecha(metadata["covered_start"]) <= inicio
        and _fecha(metadata["covered_end"]) >= fin
    )
    descargadas = 0

    if not cubre_rango:
        downloader = downloader or descargar_yfinance
        rangos = []
        if not cache:
            rangos.append((inicio, fin))
        else:
            if inicio < cache[0]["date"]:
                rangos.append((inicio, cache[0]["date"] - timedelta(days=1)))
            if fin > cache[-1]["date"]:
                rangos.append((cache[-1]["date"] + timedelta(days=1), fin))
        nuevas = []
        for rango_inicio, rango_fin in rangos:
            nuevas.extend(
                downloader(symbol, rango_inicio, rango_fin) or []
            )
        descargadas = len(nuevas)
        por_fecha = {
            fila["date"]: fila
            for fila in cache
        }
        for fila in nuevas:
            normalizada = dict(fila)
            normalizada["date"] = _fecha(fila["date"])
            por_fecha[normalizada["date"]] = normalizada
        cache = sorted(
            por_fecha.values(),
            key=lambda fila: fila["date"]
        )
        if nuevas:
            guardar_cache(symbol, cache, cache_dir)
        _guardar_metadata(symbol, inicio, fin, cache_dir)

    filtradas = [
        fila
        for fila in cache
        if inicio <= fila["date"] <= fin
    ]
    return filtradas, {
        "symbol": symbol,
        "cache_hit": bool(cubre_rango),
        "filas_cache": len(filtradas),
        "filas_descargadas": descargadas,
    }


def obtener_historicos(
    symbols,
    start_date,
    end_date,
    downloader=None,
    cache_dir=CACHE_DIR,
):
    historicos = {}
    estadisticas = {
        "symbols": 0,
        "cache_hits": 0,
        "filas_cache": 0,
        "filas_descargadas": 0,
        "errores": 0,
    }

    for symbol in sorted({_symbol(valor) for valor in symbols if _symbol(valor)}):
        estadisticas["symbols"] += 1
        try:
            filas, info = obtener_historico(
                symbol,
                start_date,
                end_date,
                downloader=downloader,
                cache_dir=cache_dir,
            )
            historicos[symbol] = filas
            estadisticas["cache_hits"] += int(info["cache_hit"])
            estadisticas["filas_cache"] += info["filas_cache"]
            estadisticas["filas_descargadas"] += info["filas_descargadas"]
        except Exception as exc:
            estadisticas["errores"] += 1
            historicos[symbol] = []
            print(f"{symbol:<8} ERROR HISTORICO: {exc}")

    return historicos, estadisticas
