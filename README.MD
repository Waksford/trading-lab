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

## Criterios de mantenimiento

- Hacer cambios pequeños y localizados.
- No eliminar funciones sin revisar todos sus usos.
- Mantener compatibilidad con el histórico SQLite.
- Mantener Momentum V4 y Reversal V1 como estrategias separadas.
- No mezclar Paper Tracking con Paper Portfolio Live.
- No versionar credenciales, bases productivas, logs ni entornos virtuales.

