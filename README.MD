# Trading Lab

Laboratorio de análisis cuantitativo para acciones de Estados Unidos. El proyecto descarga datos de mercado, calcula indicadores técnicos, clasifica oportunidades, conserva el histórico en SQLite y genera seguimiento paper e informes semanales.

> Este software es una herramienta de investigación. Sus resultados no constituyen recomendaciones de compra o venta y el Paper Portfolio Live no ejecuta órdenes reales.

## Componentes principales

- **Momentum V4** (`scoring/momentum_v4.py`): score técnico principal para detectar fortaleza y clasificar activos por prioridad.
- **Reversal V1** (`scoring/reversal_v1.py`): estrategia independiente para buscar posibles rebotes. No se mezcla con Momentum en un único score.
- **Paper Tracking** (`paper_simulator.py`): estudia qué ocurrió después de señales individuales en distintos horizontes y variantes de salida.
- **Paper Portfolio Live** (`paper_portfolio_live.py`): simula una cartera continua, con cash, posiciones abiertas/cerradas, costes, equity, exposición y benchmark SPY.
- **Informe semanal** (`weekly_report.py`): resume radar, fundamentales, analistas, noticias, Paper Tracking y Paper Portfolio Live.
- **Persistencia** (`database/db.py`): crea y consulta las tablas SQLite utilizadas por todo el sistema.

### Carteras forward/paper

- **MOMENTUM_LIVE**: estrategia experimental de acciones basada en Momentum V4.
- **REVERSAL_LIVE**: estrategia experimental Reversal V1, independiente de Momentum.
- **ETF_TOP2_CANDIDATE** (`paper_etf_forward.py`): candidata ETF congelada en validacion forward/paper; Top-2 diversificado mensual con filtro cash. **No es ETF V1 oficial**.
- **SPY_BUY_HOLD**: benchmark pasivo que compra SPY una vez y mantiene.
- **BALANCED_60_40**: benchmark SPY/IEF con asignacion 60/40 y rebalanceo mensual.
- **DEFENSIVE_CANDIDATE**: candidata forward congelada. Mensualmente mantiene SHY
  cuando el momentum60 de SPY es negativo y SPY en caso contrario. No es
  Defensive V1 productivo.
- **SHY_BUY_HOLD**: benchmark defensivo pasivo que compra SHY una vez y mantiene.

Las siete se valoran diariamente y se comparan en el informe semanal solo sobre
la ventana comun iniciada el **2026-09-02**. Las tres carteras nuevas parten de
$10,000, aplican costes paper y no envian ordenes reales.

Defensive Candidate y SHY Buy & Hold se activan el 2026-09-02. Defensive espera
la primera senal mensual valida posterior; SHY compra en la apertura siguiente.

`paper_portfolios_runner.py` es el unico orquestador diario de esta capa. Descarga
un dataset compartido y ejecuta por separado las carteras de acciones y el motor
ETF/benchmarks. `main.py` sigue limitado al scanner. Los benchmarks no dependen
de que el scanner o Paper Tracking hayan terminado correctamente; cada cartera
informa su propio estado y un fallo no impide intentar las restantes.

La versión V3 permanece en la base como histórico. Momentum V4 es la versión técnica activa.

## Flujo diario

En Windows, `run_daily.bat` activa `.venv` y ejecuta secuencialmente:

1. `main.py`: construye el radar y guarda el scan.
2. `paper_simulator.py`: actualiza el seguimiento de señales.
3. `paper_portfolio_live.py`: actualiza las carteras continuas.
4. `news_analyzer.py`: incorpora contexto de noticias.

Cada etapa depende del éxito de la anterior. La salida queda en `data/trading_YYYY-MM-DD.log`; los logs de más de 90 días se eliminan mediante el propio script.

El flujo semanal se ejecuta con `run_weekly.bat`, que llama a `weekly_report.py` y escribe `data/weekly.log`. Si el envío de correo está habilitado, el informe utiliza la configuración SMTP del entorno.

## Estructura

```text
analysis/       Análisis de eventos, fundamentales, noticias y rendimiento
database/       Acceso y esquema compatible de SQLite
market/         Universo, scanner, sectores, indicadores y variantes de salida
notifications/  Envío opcional del informe por correo
providers/      Proveedores externos, como consenso de analistas
research/       Backtests, diagnósticos y análisis experimentales
scoring/        Momentum V4 y Reversal V1
test/           Pruebas unitarias
tools/          Utilidades de mantenimiento y auditoría
data/           Base SQLite, logs y artefactos locales (no versionados)
```

## Requisitos

- Windows para utilizar directamente los archivos `.bat`.
- Python 3 con un entorno virtual.
- Cuenta y credenciales de Alpaca para las descargas que las requieren.

Dependencias principales detectadas en el código:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install alpaca-py numpy pandas python-dotenv requests yfinance
```

Actualmente el repositorio no contiene un archivo de dependencias fijadas. Conviene añadir `requirements.txt` o `pyproject.toml` antes de preparar una instalación reproducible.

## Configuración

Crea un archivo `.env` local en la raíz. No lo subas al repositorio.

```dotenv
ALPACA_API_KEY=tu_clave
ALPACA_SECRET_KEY=tu_secreto

EMAIL_ENABLED=false
SMTP_HOST=smtp.ejemplo.com
SMTP_PORT=587
SMTP_USER=usuario
SMTP_PASSWORD=secreto
EMAIL_FROM=origen@ejemplo.com
EMAIL_TO=destino@ejemplo.com
```

Con `EMAIL_ENABLED=false` no se envían correos. Las variables SMTP solo son necesarias si se activa el envío.

## Ejecución

Desde la raíz del proyecto:

```powershell
# Radar diario completo
.\run_daily.bat

# Informe semanal (puede enviar correo si está habilitado)
.\run_weekly.bat

# Radar manual
.\.venv\Scripts\python.exe main.py

# Reconstrucción para una fecha de mercado
.\.venv\Scripts\python.exe main.py --market-date YYYY-MM-DD
```

Los scripts `.bat` contienen actualmente una ruta absoluta al proyecto. Si se clona en otra ubicación, hay que actualizar la línea `cd /d` de ambos archivos.

## Base de datos y datos locales

La base principal es `data/trading.db`. Contiene histórico y estado de las simulaciones, por lo que debe conservarse y respaldarse fuera de Git.

- No borrar `data/trading.db`.
- No editar manualmente el esquema sin revisar compatibilidad histórica.
- Antes de cambiar `database/db.py`, revisar todos sus consumidores.
- En cambios SQL, comprobar que columnas y placeholders coincidan.

El `.gitignore` excluye la base, sus archivos auxiliares, logs y demás contenido generado dentro de `data/`.

## Tests

La suite usa `unittest` y bases temporales en las pruebas que necesitan persistencia:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py"
```

Después de modificar Python, puede comprobarse la sintaxis de los archivos afectados con:

```powershell
.\.venv\Scripts\python.exe -m py_compile ruta\al\archivo.py
```

Las pruebas y herramientas de `research/` pueden ser más costosas o requerir datos externos; deben ejecutarse de forma consciente según el análisis que se quiera validar.

## Investigación ETF

La fase exploratoria de ETFs vive exclusivamente en `research/` y no define un score ni una cartera productiva:

```powershell
.\.venv\Scripts\python.exe -m research.etf_factor_analysis
.\.venv\Scripts\python.exe -m research.etf_factor_analysis --start 2018-01-01 --end 2025-12-31
.\.venv\Scripts\python.exe -m research.etf_factor_analysis --horizon 20 --refresh-cache
```

Los resultados compactos se guardan en `data/research_etf/`. El histórico OHLCV ajustado usa caché incremental. El dataset completo es reconstruible y solo se guarda al añadir `--save-dataset`, porque puede superar 100 MB.

La Fase 2 estudia rotación simple entre representantes de clases de activos, con carteras continuas, costes y métricas ajustadas a riesgo:

```powershell
.\.venv\Scripts\python.exe -m research.etf_rotation_analysis
.\.venv\Scripts\python.exe -m research.etf_rotation_analysis --start 2016-01-01 --end 2025-12-31
```

Esta investigación tampoco crea una estrategia ETF productiva. Sus CSVs de resultados, periodos y curvas de equity se guardan en `data/research_etf/`.

La Fase 3 congela las tres finalistas de rotación y valida años, crisis, duración de drawdowns, rolling returns, block bootstrap, concentración y experiencia operativa:

```powershell
.\.venv\Scripts\python.exe -m research.etf_final_validation
```

La salida es descriptiva y no selecciona automáticamente una ganadora ni crea ETF V1.

## Investigacion Defensive

La investigacion Defensive permanece aislada de produccion. Compara cinco reglas
simples de risk-off y cinco decisiones defensivas usando SPY como placeholder
cuando el modulo no esta activo:

```powershell
.\.venv\Scripts\python.exe -m research.defensive_analysis --start 2016-01-01 --end 2026-09-02
```

Los CSV se guardan en `data/research_defensive/`. Este analisis no crea Defensive
V1, no registra carteras paper y no modifica ninguna estrategia existente.

## Criterios de mantenimiento

- Hacer cambios pequeños y localizados.
- No eliminar funciones sin revisar todos sus usos.
- Mantener compatibilidad con el histórico SQLite.
- Mantener Momentum V4 y Reversal V1 como estrategias separadas.
- No mezclar Paper Tracking con Paper Portfolio Live.
- No versionar credenciales, bases productivas, logs ni entornos virtuales.
