from collections import defaultdict
from datetime import datetime, timedelta

from database.db import obtener_analyst_snapshots_symbols


HORIZONTES_REVISION = (7, 30)


def _numero(valor):
    if valor is None:
        return None

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _cambio_pct(actual, anterior):
    actual = _numero(actual)
    anterior = _numero(anterior)

    if actual is None or anterior in (None, 0):
        return None

    return (actual / anterior - 1) * 100


def _cambio(actual, anterior):
    actual = _numero(actual)
    anterior = _numero(anterior)

    if actual is None or anterior is None:
        return None

    return actual - anterior


def clasificar_revision_analistas(
    target_change_pct=None,
    eps_change_pct=None,
    consensus_change=None
):
    """Clasificacion contextual; no constituye una recomendacion."""

    disponibles = [
        valor
        for valor in (
            target_change_pct,
            eps_change_pct,
            consensus_change
        )
        if valor is not None
    ]

    if not disponibles:
        return "SIN HISTORICO"

    consenso_no_mejora = (
        consensus_change is None
        or consensus_change <= 0
    )
    consenso_no_empeora = (
        consensus_change is None
        or consensus_change >= 0
    )

    if (
        (
            target_change_pct is not None
            and target_change_pct <= -10
        )
        or (
            eps_change_pct is not None
            and eps_change_pct <= -10
        )
    ) and consenso_no_mejora:
        return "MUY NEGATIVA"

    if (
        (
            target_change_pct is not None
            and target_change_pct >= 10
        )
        or (
            eps_change_pct is not None
            and eps_change_pct >= 10
        )
    ) and consenso_no_empeora:
        return "MUY POSITIVA"

    if (
        (target_change_pct is not None and target_change_pct <= -3)
        or (eps_change_pct is not None and eps_change_pct <= -3)
        or (consensus_change is not None and consensus_change <= -0.25)
    ):
        return "NEGATIVA"

    if (
        (target_change_pct is not None and target_change_pct >= 3)
        or (eps_change_pct is not None and eps_change_pct >= 3)
        or (consensus_change is not None and consensus_change >= 0.25)
    ):
        return "POSITIVA"

    return "ESTABLE"


def _fecha_snapshot(snapshot):
    return datetime.strptime(
        snapshot["snapshot_date"],
        "%Y-%m-%d"
    ).date()


def _calcular_desde_snapshots(symbol, snapshots):
    snapshots = sorted(
        snapshots,
        key=lambda fila: (
            fila["snapshot_date"],
            fila.get("snapshot_time") or "",
            fila.get("id") or 0
        ),
        reverse=True
    )

    if not snapshots:
        return None

    actual = snapshots[0]
    fecha_actual = _fecha_snapshot(actual)
    revision = {
        "symbol": symbol,
        "snapshot_date": actual["snapshot_date"],
    }

    for horizonte in HORIZONTES_REVISION:
        fecha_limite = fecha_actual - timedelta(days=horizonte)
        anterior = next(
            (
                snapshot
                for snapshot in snapshots[1:]
                if _fecha_snapshot(snapshot) <= fecha_limite
            ),
            None
        )
        sufijo = f"_{horizonte}d"

        if anterior is None:
            target = eps = consenso = analistas = None
        else:
            target = _cambio_pct(
                actual.get("target_mean"),
                anterior.get("target_mean")
            )
            eps = _cambio_pct(
                actual.get("eps_next_y"),
                anterior.get("eps_next_y")
            )
            consenso = _cambio(
                actual.get("consensus_score"),
                anterior.get("consensus_score")
            )
            analistas = _cambio(
                actual.get("analyst_count"),
                anterior.get("analyst_count")
            )

        revision[f"comparison_date{sufijo}"] = (
            anterior["snapshot_date"]
            if anterior
            else None
        )
        revision[f"target_mean_change_pct{sufijo}"] = target
        revision[f"consensus_change{sufijo}"] = consenso
        revision[f"eps_next_year_change_pct{sufijo}"] = eps
        revision[f"analyst_count_change{sufijo}"] = analistas
        revision[f"clasificacion{sufijo}"] = (
            clasificar_revision_analistas(
                target,
                eps,
                consenso
            )
        )

    return revision


def calcular_revisiones_symbols(symbols):
    symbols = sorted({
        str(symbol).strip().upper()
        for symbol in symbols
        if symbol
    })
    historicos = defaultdict(list)

    for snapshot in obtener_analyst_snapshots_symbols(symbols):
        historicos[snapshot["symbol"]].append(snapshot)

    return {
        symbol: _calcular_desde_snapshots(
            symbol,
            historicos.get(symbol, [])
        ) or {
            "symbol": symbol,
            "clasificacion_7d": "SIN HISTORICO",
            "clasificacion_30d": "SIN HISTORICO"
        }
        for symbol in symbols
    }


def calcular_revision_symbol(symbol):
    symbol = str(symbol).strip().upper()
    return calcular_revisiones_symbols([symbol])[symbol]
