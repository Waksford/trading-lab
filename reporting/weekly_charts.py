"""Charts for the common forward window used by the weekly report."""

from pathlib import Path

import pandas as pd


COMMON_START = "2026-09-02"


def normalizar_curvas_comunes(curvas, common_start=COMMON_START):
    """Normalize only series with an exact baseline on the common start date."""
    normalizadas = {}
    inicio = pd.Timestamp(common_start)
    for nombre, serie in curvas.items():
        valores = pd.Series(serie).copy()
        valores.index = pd.to_datetime(valores.index)
        valores = valores.sort_index()
        if inicio not in valores.index or valores.at[inicio] <= 0:
            continue
        valores = valores.loc[inicio:].dropna()
        normalizadas[nombre] = valores / valores.iloc[0] * 10_000
    return normalizadas


def generar_graficos_weekly(curvas, output_dir, common_start=COMMON_START):
    """Create at most two charts; failures are returned instead of propagated."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rutas = {"equity": None, "return_drawdown": None, "error": None}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        normalizadas = normalizar_curvas_comunes(curvas, common_start)
        if not normalizadas:
            return rutas

        equity_path = output_dir / "weekly_equity.png"
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for nombre, serie in normalizadas.items():
            ax.plot(serie.index, serie.values, linewidth=1.8, label=nombre)
        ax.set_title("Evolución de 10.000 $ — Ventana común fuera de muestra")
        ax.set_ylabel("Valor de la cartera ($)")
        ax.grid(True, alpha=0.2)
        ax.legend(fontsize=8, ncol=2, frameon=False)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(equity_path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        rutas["equity"] = equity_path

        puntos = []
        for nombre, serie in normalizadas.items():
            retorno = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
            maxdd = (serie / serie.cummax() - 1).min() * 100
            puntos.append((nombre, maxdd, retorno))
        scatter_path = output_dir / "weekly_return_drawdown.png"
        fig, ax = plt.subplots(figsize=(8, 4.8))
        for nombre, maxdd, retorno in puntos:
            ax.scatter(maxdd, retorno, s=48)
            ax.annotate(nombre, (maxdd, retorno), xytext=(5, 4),
                        textcoords="offset points", fontsize=8)
        ax.axhline(0, color="#94a3b8", linewidth=.8)
        ax.axvline(0, color="#94a3b8", linewidth=.8)
        ax.set_title("Rentabilidad frente a caída máxima — Ventana común")
        ax.set_xlabel("Caída máxima (%) — cuanto más cerca de 0, menor caída")
        ax.set_ylabel("Rentabilidad (%)")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(scatter_path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        rutas["return_drawdown"] = scatter_path
    except Exception as exc:
        rutas["error"] = str(exc)
    return rutas
