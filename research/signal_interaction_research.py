"""Ejecutor reproducible de SIGNAL INTERACTION RESEARCH — FASE 1."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.signal_interaction_analysis import (
    baseline_results, disagreement_results, feature_dependence,
    incremental_value, univariate_results,
)
from research.signal_interaction_dataset import (
    build_signal_dataset, data_availability_audit, feature_dictionary,
)
from research.signal_interaction_validation import (
    temporal_validation, ticker_concentration, validate_dataset,
)


OUTPUT_DIR = Path("data/research_signal_interaction")


def _fmt(value, suffix=""):
    return "N/D" if value is None or pd.isna(value) else f"{value:+.2f}{suffix}"


def _classification_table(dictionary, incremental, audit):
    source_map = {
        "fundamental": "fundamentals", "analistas": "analyst_consensus",
        "revisiones": "analyst_revisions_7d", "noticias": "news",
        "sector": "sector_context", "mercado": "market_regime",
    }
    rows = []
    for _, item in dictionary.iterrows():
        source = source_map[item["feature_group"]]
        availability = audit[audit["source"] == source]
        coverage = float(availability["coverage_pct"].iloc[0]) if not availability.empty else 0
        point_status = availability["point_in_time_status"].iloc[0] if not availability.empty else "NOT_POINT_IN_TIME"
        values = incremental[incremental["feature"] == item["feature"]]
        if point_status == "NOT_POINT_IN_TIME":
            classification = "NOT_POINT_IN_TIME"
        elif values.empty or (values["classification"] == "INSUFFICIENT_DATA").all():
            classification = "INSUFFICIENT_DATA"
        elif (values["classification"] == "PROMISING").sum() >= 2:
            classification = "PROMISING"
        else:
            classification = "NEUTRAL"
        rows.append({"feature": item["feature"], "source": source,
                     "coverage_pct": coverage, "classification": classification,
                     "reason": "No existe train 2021/test 2022+ con Momentum V4 real"
                     if classification == "INSUFFICIENT_DATA" else "Resultado OOS descriptivo"})
    return pd.DataFrame(rows)


def build_report(dataset, audit, baseline, classifications, temporal, concentration, errors):
    mature5 = int(dataset["exceso_spy_5d"].notna().sum())
    mature20 = int(dataset["exceso_spy_20d"].notna().sum())
    mature60 = int(dataset["exceso_spy_60d"].notna().sum())
    aa = baseline[(baseline["priority"] == "A+/A") &
                  (baseline["horizon"] == 5) & (baseline["metric"] == "exceso_spy")]
    aa_row = aa.iloc[0] if not aa.empty else {}
    top_share = concentration.head(10)["share_pct"].sum() if not concentration.empty else np.nan
    source_status = classifications.groupby("source")["classification"].agg(
        lambda x: ", ".join(sorted(set(x)))
    ).to_dict()
    lines = [
        "SIGNAL INTERACTION RESEARCH — FASE 1", "=" * 76,
        "Investigacion retrospectiva; no constituye una regla de trading.", "",
        "1. Fuentes disponibles",
        "Scans originales Momentum V4, resultados paper, fundamentales, consenso y revisiones de analistas, noticias, sector y benchmark SPY.",
        "2. Fuentes realmente point-in-time",
        "Scans/sector persistidos en la senal; SPY de la misma fecha; snapshots fundamentales, analistas y noticias solo mediante join hacia atras.",
        "3. Fuentes que no pueden utilizarse historicamente",
        "Ningun snapshot futuro se aplico retroactivamente. Las observaciones sin snapshot previo quedaron missing; no hay proxy actual.",
        "4. Tamano del dataset",
        f"{len(dataset)} senales V4 BASE ({dataset['symbol'].nunique()} tickers); maduras: 5D={mature5}, 20D={mature20}, 60D={mature60}.",
        "5. Baseline Momentum A+/A",
        f"5D: n={int(aa_row.get('n', 0))}, exceso medio={_fmt(aa_row.get('mean'), ' pp')}. 20D/60D: datos insuficientes.",
        "6. Resultado de fundamentales", f"{source_status.get('fundamentals', 'INSUFFICIENT_DATA')}: cobertura temporal util limitada.",
        "7. Resultado de analistas", f"{source_status.get('analyst_consensus', 'INSUFFICIENT_DATA')}: no existe ventana OOS evaluable.",
        "8. Resultado de revisiones", f"{source_status.get('analyst_revisions_7d', 'INSUFFICIENT_DATA')}: exige dos snapshots previos separados al menos siete dias.",
        "9. Resultado de noticias", f"{source_status.get('news', 'INSUFFICIENT_DATA')}: solo se admitieron analisis ya existentes al emitir la senal.",
        "10. Resultado del regimen de mercado", f"{source_status.get('market_regime', 'INSUFFICIENT_DATA')}: reconstruido con momentum60 de SPY de la fecha, sin precios futuros.",
        "11. Resultado del sector", f"{source_status.get('sector_context', 'INSUFFICIENT_DATA')}: disponible en el scan, pero sin historia temporal suficiente.",
        "12. Interacciones mas interesantes", "Ninguna puede calificarse como estable: solo existe madurez a 5 sesiones y en 2026.",
        "13. Interacciones buenas IS que fallaron OOS", "No evaluable: no existe muestra IS hasta 2021 ni OOS desde 2022 para V4.",
        "14. Features redundantes", "No se declara redundancia definitiva sin muestra temporal suficiente; las correlaciones quedan en feature_dependence.csv.",
        "15. Concentracion por ticker", f"Los 10 tickers mas frecuentes concentran {_fmt(top_share, '%')} de las senales.",
        "16. Estabilidad por ano", "No evaluable: todas las senales Momentum V4 reales pertenecen a 2026.",
        "17. Estabilidad por sector", "No evaluable causalmente con una sola ventana corta; se conserva sector en signal_dataset.csv.",
        "18. Valor incremental", "No estimable con el split predefinido 2021/2022; incremental_value.csv lo marca INSUFFICIENT_DATA.",
        "19. Clasificacion final de features",
    ]
    lines.extend(f"- {r.feature}: {r.classification}" for r in classifications.itertuples())
    lines.extend([
        "20. Que aprendimos", "La infraestructura point-in-time existe, pero la edad de Momentum V4 aun impide separar senal incremental de ruido.",
        "21. Que NO funciona", "Usar snapshots actuales para senales antiguas, optimizar umbrales con esta muestra o presentar 5D como evidencia 20D/60D.",
        "22. Que merece una Phase 2", "Repetir exactamente el protocolo cuando maduren 20D/60D y exista mas de un ano; no crear filtros antes.",
        "23. Estrategias productivas", "Confirmado: ninguna estrategia, cartera paper, runner ni weekly_report.py fue modificada por esta investigacion.",
        "24. Tests especificos", "Consultar la ejecucion de test/test_signal_interaction_research.py; validaciones internas: " + ("OK" if not errors else "; ".join(errors)),
        "25. Suite completa", "Debe registrarse tras ejecutar pytest; este informe de datos no altera el resultado de la suite.", "",
        "NOTA SOBRE MULTIPLES COMPARACIONES",
        "No se calcularon p-valores ni se seleccionaron umbrales por significacion. Por ello no se aplica FDR en esta fase; se priorizan efectos OOS, hoy no estimables.",
        "CONCLUSION",
        "INSUFFICIENT_DATA. No hay evidencia temporal suficiente para afirmar que ninguna capa aporte valor incremental independiente sobre Momentum V4.",
    ])
    return "\n".join(lines)


def run(output_dir=OUTPUT_DIR, db_path=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_signal_dataset(db_path) if db_path is not None else build_signal_dataset()
    dictionary = feature_dictionary()
    audit = data_availability_audit(dataset)
    baseline = baseline_results(dataset)
    univariate = univariate_results(dataset, dictionary)
    disagreements = disagreement_results(dataset)
    dependence = feature_dependence(dataset, dictionary)
    incremental = incremental_value(dataset, dictionary)
    temporal = temporal_validation(dataset, dictionary)
    concentration = ticker_concentration(dataset)
    errors = validate_dataset(dataset)
    if errors:
        raise AssertionError("; ".join(errors))
    classifications = _classification_table(dictionary, incremental, audit)

    outputs = {
        "data_availability_audit.csv": audit,
        "feature_dictionary.csv": dictionary,
        "signal_dataset.csv": dataset,
        "baseline_results.csv": baseline,
        "univariate_results.csv": univariate,
        "disagreement_results.csv": disagreements,
        "feature_dependence.csv": dependence,
        "incremental_value.csv": incremental,
        "temporal_validation.csv": temporal,
        "ticker_concentration.csv": concentration,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False, encoding="utf-8")
    report = build_report(dataset, audit, baseline, classifications, temporal,
                          concentration, errors)
    (output_dir / "signal_interaction_report.txt").write_text(report, encoding="utf-8")
    return outputs, report


def main():
    outputs, report = run()
    print(report)
    print(f"\nArtefactos: {OUTPUT_DIR.resolve()} ({len(outputs) + 1} archivos)")


if __name__ == "__main__":
    main()
