"""Provider aislado para los ficheros oficiales FONDREGISTRO/FONDMENS de CNMV."""

from calendar import monthrange
from html import unescape
from io import BytesIO
from pathlib import Path
import re
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd


BASE_URL = "https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "research_funds"


def _descargar(url, timeout=90):
    request = Request(url, headers={"User-Agent": "trading-lab research/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def descubrir_descargas(año, fetcher=None):
    """Devuelve los ZIP mensuales publicados por CNMV para un año."""
    fetcher = fetcher or _descargar
    html = fetcher(f"{BASE_URL}?ejercicio={int(año)}&lang=es").decode("utf-8", "replace")
    patron = re.compile(r'href="([^"]+)"[^>]+title="([^"]+)"[^>]*>\s*<img', re.I)
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
        "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
        "octubre": 10, "noviembre": 11, "diciembre": 12,
    }
    resultado = {}
    for href, titulo in patron.findall(html):
        mes = meses.get(unescape(titulo).strip().lower())
        if mes:
            resultado[f"{int(año):04d}{mes:02d}"] = unescape(href).replace("&amp;", "&")
    return resultado


def _texto(elemento, ruta, defecto=""):
    valor = elemento.findtext(ruta)
    return valor.strip() if valor else defecto


def extraer_zip_cnmv(contenido, isins=None):
    """Extrae último NAV del mes y metadata sin conservar el ZIP completo."""
    filtro = set(isins or [])
    with zipfile.ZipFile(BytesIO(contenido)) as archivo:
        mens_name = next(
            n for n in archivo.namelist()
            if Path(n).name.upper().startswith("FONDMENS") and n.lower().endswith(".xml")
        )
        reg_name = next((
            n for n in archivo.namelist()
            if Path(n).name.upper().startswith("FONDREGISTRO") and n.lower().endswith(".xml")
        ), None)
        mens = ET.fromstring(archivo.read(mens_name))
        periodo = _texto(mens, "FechaDatos")
        año, mes = int(periodo[:4]), int(periodo[4:6])
        ultimo_dia = monthrange(año, mes)[1]
        filas_nav = []
        for entidad in mens.findall("Entidad"):
            registro = _texto(entidad, "NumeroRegistro")
            for clase in entidad.findall("Compartimento/Clase"):
                isin = _texto(clase, "ISIN")
                if filtro and isin not in filtro:
                    continue
                valores = []
                diario = clase.find("VLDiario")
                if diario is not None:
                    for nodo in diario:
                        coincidencia = re.search(r"(\d+)$", nodo.tag)
                        try:
                            dia, nav = int(coincidencia.group(1)), float(nodo.text)
                        except (AttributeError, TypeError, ValueError):
                            continue
                        if 1 <= dia <= ultimo_dia and nav > 0:
                            valores.append((dia, nav))
                if valores:
                    dia, nav = max(valores)
                    filas_nav.append({
                        "date": f"{año:04d}-{mes:02d}-{dia:02d}", "isin": isin,
                        "nav": nav, "cnmv_registration": registro, "source": "CNMV_FONDMENS",
                    })

        metadata = []
        if reg_name:
            registro_xml = ET.fromstring(archivo.read(reg_name))
            for entidad in registro_xml.findall("Entidad"):
                for clase in entidad.findall("Compartimento/Clase"):
                    isin = _texto(clase, "ISIN")
                    if filtro and isin not in filtro:
                        continue
                    metadata.append({
                        "isin": isin,
                        "fund_name": _texto(entidad, "Denominacion"),
                        "cnmv_registration": _texto(entidad, "NumeroRegistro"),
                        "share_class": _texto(clase, "DenominacionClase"),
                        "management_company": _texto(entidad, "Gestora/DenominacionGestora"),
                    })
    return pd.DataFrame(filas_nav), pd.DataFrame(metadata)


def importar_csv_manual(path, isin=None):
    """Fallback explícito: CSV con date/nav y, si procede, isin."""
    datos = pd.read_csv(path)
    requeridas = {"date", "nav"}
    if not requeridas.issubset(datos.columns):
        raise ValueError("El CSV manual debe contener date y nav")
    if "isin" not in datos.columns:
        if not isin:
            raise ValueError("Falta isin en el CSV y en el argumento")
        datos["isin"] = isin
    datos["date"] = pd.to_datetime(datos["date"], errors="raise")
    datos["nav"] = pd.to_numeric(datos["nav"], errors="raise")
    datos = datos[datos["nav"] > 0].copy()
    datos["source"] = "MANUAL_CSV"
    return datos.sort_values(["isin", "date"]).drop_duplicates(["isin", "date"], keep="last")


def obtener_nav_cnmv(isins, inicio="2016-01", fin=None, refresh=False,
                      cache_dir=CACHE_DIR, fetcher=None):
    """Descarga/cachea extractos mensuales CNMV para los ISIN solicitados."""
    cache_dir = Path(cache_dir)
    period_dir = cache_dir / "cnmv_monthly"
    period_dir.mkdir(parents=True, exist_ok=True)
    inicio_p = pd.Period(inicio, freq="M")
    fin_p = pd.Period(fin or pd.Timestamp.today().strftime("%Y-%m"), freq="M")
    filas, metadata = [], []
    for año in range(inicio_p.year, fin_p.year + 1):
        enlaces = descubrir_descargas(año, fetcher=fetcher)
        for periodo, url in sorted(enlaces.items()):
            p = pd.Period(periodo, freq="M")
            if p < inicio_p or p > fin_p:
                continue
            destino = period_dir / f"{periodo}.csv"
            meta_destino = period_dir / f"{periodo}_metadata.csv"
            if refresh or not destino.exists():
                nav, meta = extraer_zip_cnmv((fetcher or _descargar)(url), isins)
                nav.to_csv(destino, index=False)
                meta.to_csv(meta_destino, index=False)
            nav = pd.read_csv(destino)
            if not nav.empty:
                filas.append(nav[nav["isin"].isin(isins)])
            if meta_destino.exists():
                meta = pd.read_csv(meta_destino)
                if not meta.empty:
                    metadata.append(meta[meta["isin"].isin(isins)])
    nav = pd.concat(filas, ignore_index=True) if filas else pd.DataFrame(columns=["date", "isin", "nav", "source"])
    meta = pd.concat(metadata, ignore_index=True) if metadata else pd.DataFrame()
    if not nav.empty:
        nav["date"] = pd.to_datetime(nav["date"])
        nav = nav.sort_values(["isin", "date"]).drop_duplicates(["isin", "date"], keep="last")
    if not meta.empty:
        meta = meta.drop_duplicates("isin", keep="last")
    return nav, meta
