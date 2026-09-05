# OPTIONS DATA COLLECTION — PHASE 1

## Objetivo

Construir desde ahora un histórico point-in-time de opciones para investigación futura. Esta fase compra información, no opciones.

**NO TRADING · NO SIGNALS · NO BACKTEST YET**

No crea estrategias, señales, carteras paper ni órdenes. El provider solo utiliza clientes de Market Data de Alpaca.

## Cobertura inicial

- SPX: índice S&P 500.
- XSP: Mini-SPX.
- VIX: índice de volatilidad.

Alpaca anunció soporte inicial de contratos SPX/SPXW, XSP, VIX/VIXW y DJX en paper, pero también indicó que los datos de los índices todavía no estaban disponibles en su oferta de Market Data en el momento del anuncio. Por ello el collector conserva errores y valores `NULL`; no sustituye el spot con otra fuente.

## Algoritmo determinista

1. Se descubre la cadena con el endpoint de Option Market Data.
2. Se solicita explícitamente OPRA. Solo ante un error de entitlement se intenta INDICATIVE. El feed solicitado y realmente usado se guarda en cada fila y en el run.
3. Para cada objetivo 7, 14, 30, 60 y 90 DTE se elige la expiración disponible con menor distancia absoluta. Los empates favorecen la fecha más temprana. Una expiración no puede cubrir dos objetivos.
4. Con spot se conservan contratos entre `spot × 0,85` y `spot × 1,15` (`SPOT_BAND`). Si hay más de 31 strikes por expiración, se crean 31 objetivos equidistantes y se elige el strike disponible más cercano. Se conservan calls y puts.
5. Sin spot se usa `NO_SPOT_GRID`, que es solo una limitación de almacenamiento y no una aproximación a ATM. Se toman todos los contratos de las cinco expiraciones si no superan el límite del subyacente.
6. Los límites son 1.000 contratos para SPX, 800 para XSP y 500 para VIX. El presupuesto se reparte aproximadamente por igual entre vencimientos y la capacidad que no utiliza una cadena pequeña se redistribuye de forma determinista.
7. Dentro de cada vencimiento se agrupa por strike, se priorizan pares CALL/PUT y se preservan los strikes mínimo y máximo cuando caben. Un contrato individual solo se selecciona cuando ese strike no tiene pareja. `selection_rank` conserva el orden determinista y `selection_reason` distingue `GRID_ENDPOINT`, `GRID_UNIFORM` y `GRID_REMAINDER`.
8. Sin spot, `underlying_price`, `spot_source`, `spot_timestamp`, `moneyness_pct` y `distance_from_atm_pct` permanecen `NULL`; `spot_available=0`. Nunca se infiere spot ni ATM.

## Campos y calidad

Raw: bid, ask, last, tamaños, timestamps, IV, Greeks, open interest, volumen y feed tal como los entrega Alpaca. Los campos ausentes se guardan como `NULL`. RAW puede conservarse aunque no exista spot.

Derived: DTE, moneyness, distancia ATM, mid, spread absoluto/relativo y calidad. `mid` solo existe cuando bid/ask son numéricos, `bid >= 0` y `ask >= bid`; nunca se sustituye por `last`.

Calidad: `VALID`, `NO_BID`, `NO_ASK`, `CROSSED`, `STALE` o `MISSING`. Una quote con timestamp de otra sesión es `STALE`. Los contratos de mala calidad se conservan. Si toda la cadena pertenece a una sesión anterior, el run es `NO_MARKET_DATA` y no se crea un snapshot nuevo.

## Point-in-time y almacenamiento

Base independiente: `data/options/options_market.db`. Cada ejecución tiene UUID, hora UTC, hora Madrid, fecha de mercado, feed y errores. Los snapshots son append-only entre runs; `UNIQUE(run_id, contract_symbol)` evita duplicados dentro de un retry sin impedir futuros snapshots intradía.

Tablas:

- `option_collection_runs`
- `option_underlying_snapshots`
- `option_snapshots`

No hay retención ni borrado automático.

## Ejecución

```powershell
python -m research.options_data_collector
```

Estado rápido:

```sql
SELECT * FROM option_collection_runs ORDER BY started_at DESC LIMIT 10;
SELECT market_date, underlying, COUNT(*) FROM option_snapshots GROUP BY 1,2;
```

## Horario

22:30 Europe/Madrid suele equivaler a 16:30 New York, después del cierre regular, y entra en la ventana admitida. Durante las semanas en que Europa y EE. UU. cambian el horario de verano en fechas distintas, debe comprobarse la equivalencia. Para capturar quotes cercanas al cierre con menor riesgo de retraso se recomienda aproximadamente **22:05 Madrid**, comprobando siempre el calendario estacional. No se ha modificado `run_daily.bat`.

## Retención estimada

Con spot, el máximo teórico sigue siendo 310 filas por underlying y 930 diarias. Sin spot, el límite conjunto es 2.300: SPX 1.000, XSP 800 y VIX 500.

La captura de Phase 1B `NO_SPOT_GRID` guardó 5.036 filas: SPX 2.486, XSP 1.910 y VIX 640. Phase 1C reduce ese máximo diario a 2.300 filas sin cambiar las cinco expiraciones objetivo ni la semántica del dato raw.

## Limitaciones

- La disponibilidad de SPX/XSP/VIX en Trading API no implica disponibilidad en Market Data.
- OPRA depende de suscripción/entitlement; no se presupone. INDICATIVE contiene quotes modificadas y trades derivados retrasados 15 minutos. No representa precios ejecutables OPRA ni es adecuado para estimar con precisión ejecución o slippage.
- Los snapshots de Alpaca documentan quote, trade, IV y Greeks. Open interest y volumen pueden no estar presentes y se guardan como `NULL`.
- El control de festivos se completa rechazando datos cuya quote no pertenezca a la sesión actual. No se reutilizan quotes anteriores como actuales.
- No se integra todavía con BAT, weekly ni experiment registry.
