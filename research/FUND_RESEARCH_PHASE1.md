# Fund Research — Phase 1

Investigación aislada de fondos españoles. No crea señales, portfolios ni cambios en el flujo diario.

## Fuentes

- CNMV `FONDREGISTRO`: identificación del fondo, gestora, registro, clases e ISIN.
- CNMV `FONDMENS`: valores liquidativos diarios; se conserva únicamente el último NAV disponible de cada mes.
- Yahoo Finance: proxies ETF con precios ajustados por dividendos (`auto_adjust=True`).
- CSV manual opcional: columnas `date`, `nav` e `isin`; nunca se interpola.

La CNMV publica los ficheros por periodo en:
`https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual`

## Decisiones metodológicas

- Frecuencia mensual, sin OHLC ficticio y sin rellenar meses ausentes.
- Una sola clase por fondo. En Cobas se usa clase C por disponer de continuidad oficial desde 2017; en Magallanes se usa clase E salvo Microcaps, donde se usa clase B.
- Ventana objetivo desde enero de 2016 hasta el último mes oficial completo disponible.
- Comparaciones directas únicamente en ventanas comunes fondo/benchmark.
- Proxies: `URTH` global, `VGK` Europa, `EWP` España, `IEF` renta fija intermedia y una serie `60_40` mensual de SPY/IEF.
- SPY y 60/40 se conservan como referencias generales, no como benchmark indiscriminado.
- Train: hasta 2021-12-31. Test: desde 2022-01-01.
- Los NAV ya descuentan gastos internos; no se restan de nuevo comisiones de gestión.

## Sesgos

El experimento presenta **survivorship bias** porque parte de fondos existentes en la actualidad. No se han reconstruido fondos liquidados o fusionados. También existe selection bias por concentrar el universo en gestoras españolas conocidas. Los rankings walk-forward evitan usar datos futuros, pero no eliminan esos dos sesgos.

La posible ventaja fiscal de los traspasos de fondos elegibles para inversores españoles no se modela y queda como consideración futura sujeta a la normativa aplicable.

## Ejecución

```powershell
python -m research.funds_research --start 2016-01 --end 2026-05
```

Todos los resultados se escriben exclusivamente en `data/research_funds/`.
