"""Renderizado HTML compatible con correo para el informe semanal."""

from html import escape


COLORS = {
    "EARLY": ("#dbeafe", "#1d4ed8"), "WATCH": ("#fef3c7", "#92400e"),
    "WEAK": ("#fee2e2", "#b91c1c"), "STABLE": ("#dcfce7", "#166534"),
    "BENCHMARK": ("#e5e7eb", "#4b5563"),
}

STATUS_LABELS = {
    "EARLY": "DATOS INSUFICIENTES",
    "WATCH": "EN OBSERVACIÓN",
    "WEAK": "DÉBIL",
    "STABLE": "ESTABLE",
    "BENCHMARK": "REFERENCIA",
}

DEFENSIVE_LABELS = {
    "RISK_ON": "RIESGO ACTIVO · SPY",
    "RISK_OFF": "MODO DEFENSIVO · SHY",
    "PENDING": "PENDIENTE DE LA PRIMERA SEÑAL MENSUAL",
    "WAITING FIRST MONTHLY SIGNAL": "PENDIENTE DE LA PRIMERA SEÑAL MENSUAL",
}

HIGHLIGHT_LABELS = {
    "Highest Return": "Mayor rentabilidad",
    "Lowest Drawdown": "Menor caída máxima",
    "Largest Drawdown": "Mayor caída máxima",
    "Best Risk/Return": "Mejor equilibrio rentabilidad/riesgo",
    "Least Mature Strategy": "Estrategia con menos datos",
}


def _e(value):
    return escape(str(value if value is not None else "N/A"))


def _money(value):
    return "N/A" if value is None else f"${float(value):,.2f}"


def _pct(value, suffix="%"):
    return "N/A" if value is None else f"{float(value):+.2f}{suffix}"


def _badge(status):
    bg, fg = COLORS.get(status, COLORS["EARLY"])
    label = STATUS_LABELS.get(status, status)
    return f'<span style="background:{bg};color:{fg};padding:4px 8px;border-radius:12px;font-size:11px;font-weight:bold">{_e(label)}</span>'


def _section(title, body, subtitle=None):
    sub = f'<p style="margin:4px 0 16px;color:#64748b;font-size:13px">{_e(subtitle)}</p>' if subtitle else ""
    return (f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
            f'padding:22px;margin:18px 0"><h2 style="margin:0;color:#0f172a;font-size:20px">'
            f'{_e(title)}</h2>{sub}{body}</div>')


def _overview(datos):
    o = datos["overview"]
    cards = [
        ("Prioridad alta", f"{o['a_plus'] + o['a']}", f"A+ {o['a_plus']} · A {o['a']}"),
        ("Radar", f"{o['assets']}", f"B {o['b']} · C/D {o['c'] + o['d']}"),
        ("Noticias", f"{o['news_positive']} positivas", f"{o['news_mixed']} mixtas · {o['news_negative']} negativas"),
        ("Fundamentales", f"{o['fund_excellent']} excelentes", f"{o['fund_solid']} sólidos · {o['fund_weak']} débiles"),
    ]
    html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="8"><tr>'
    for title, value, note in cards:
        html += (f'<td valign="top" style="width:25%;border:1px solid #e2e8f0;border-radius:8px;padding:14px">'
                 f'<div style="font-size:12px;color:#64748b;text-transform:uppercase">{_e(title)}</div>'
                 f'<div style="font-size:24px;font-weight:bold;color:#0f172a;margin:6px 0">{_e(value)}</div>'
                 f'<div style="font-size:12px;color:#64748b">{_e(note)}</div></td>')
    html += '</tr></table><div style="border-left:4px solid #3b82f6;background:#eff6ff;padding:12px 14px;margin-top:14px;color:#334155">'
    html += _e(datos["weekly_context"]) + "</div>"
    return _section("RESUMEN DEL MERCADO Y DEL RADAR", html)


def _scoreboard(datos):
    rows = ""
    for benchmark, titulo in ((False, "ESTRATEGIAS"), (True, "REFERENCIAS")):
        rows += (f'<tr><td colspan="6" style="padding:9px 10px;background:#eef2f7;'
                 f'color:#475569;font-size:11px;font-weight:bold;letter-spacing:1px">{titulo}</td></tr>')
        for p in (p for p in datos["portfolios"] if p["benchmark"] is benchmark):
            etiqueta = ' <span style="color:#64748b;font-size:10px">REFERENCIA</span>' if p["benchmark"] else ""
            color = "#166534" if (p["return"] or 0) >= 0 else "#b91c1c"
            rows += (f'<tr><td style="padding:10px;border-bottom:1px solid #e2e8f0"><b>{_e(p["label"])}</b>{etiqueta}</td>'
                     f'<td align="right" style="padding:10px;border-bottom:1px solid #e2e8f0">{_money(p["equity"])}</td>'
                     f'<td align="right" style="padding:10px;border-bottom:1px solid #e2e8f0;color:{color}">{_pct(p["return"])}</td>'
                     f'<td align="right" style="padding:10px;border-bottom:1px solid #e2e8f0">{_pct(p["maxdd"])}</td>'
                     f'<td align="right" style="padding:10px;border-bottom:1px solid #e2e8f0">{_pct(p["excess"], "pp")}</td>'
                     f'<td align="center" style="padding:10px;border-bottom:1px solid #e2e8f0">{_badge(p["status"])}</td></tr>')
    table = ('<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">'
             '<tr style="background:#f8fafc;color:#475569"><th align="left" style="padding:10px">Cartera</th>'
             '<th align="right">Capital</th><th align="right">Rentabilidad</th><th align="right">Caída máx.</th>'
             '<th align="right">Exceso vs. SPY</th><th>Estado</th></tr>' + rows + '</table>')
    rules = ('<p style="font-size:12px;color:#64748b;line-height:1.55">'
             '<b>Reglas de estado:</b> DATOS INSUFICIENTES = menos de 20 observaciones comunes; '
             'DÉBIL = al menos 20 observaciones, rentabilidad igual o inferior a -5% y exceso igual o inferior a -3 pp; '
             'ESTABLE = al menos 60 observaciones, rentabilidad no negativa y exceso no inferior a -1 pp; '
             'en los demás casos, EN OBSERVACIÓN. Son etiquetas descriptivas, no señales de inversión.</p>')
    return _section("COMPARATIVA DE CARTERAS", table + rules,
                    "Rentabilidad, caída máxima y exceso usan únicamente la ventana común desde el 02/09/2026. N/A indica que no existe una base común exacta.")


def _strategy_cards(datos):
    html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="10">'
    estrategias = [p for p in datos["portfolios"] if not p["benchmark"]]
    for index in range(0, len(estrategias), 2):
        html += "<tr>"
        for p in estrategias[index:index+2]:
            extra = ""
            if p["name"] == "DEFENSIVE_CANDIDATE":
                estado = DEFENSIVE_LABELS.get(p.get("defensive_state"), p.get("defensive_state"))
                posicion = "100% efectivo" if p.get("position") == "100% CASH" else p.get("position")
                ultima = DEFENSIVE_LABELS.get(p.get("last_rebalance"), p.get("last_rebalance"))
                extra = (f'<div style="margin-top:8px;color:#475569">Modo actual: <b>{_e(estado)}</b> · '
                         f'Asignación actual: {_e(posicion)}<br>Momentum de SPY a 60 sesiones: {_pct(p.get("spy_momentum60"))}<br>'
                         f'Última decisión mensual: {_e(ultima)}</div>')
            html += (f'<td valign="top" style="width:50%;border:1px solid #e2e8f0;border-radius:8px;padding:16px">'
                     f'<div style="font-weight:bold;font-size:16px;color:#0f172a">{_e(p["label"])} {_badge(p["status"])}</div>'
                     f'<p style="color:#64748b;min-height:34px">{_e(p["objective"])}</p>'
                     f'<b>{_money(p["equity"])}</b> · Rentabilidad {_pct(p["return"])} · Caída máxima {_pct(p["maxdd"])}<br>'
                     f'<span style="color:#64748b">Posiciones {p["open_count"]} · Efectivo {_money(p["cash"])}</span>{extra}</td>')
        if len(estrategias[index:index+2]) == 1:
            html += '<td style="width:50%"></td>'
        html += "</tr>"
    html += "</table>"
    return _section("DETALLE DE ESTRATEGIAS", html)


def _charts(datos):
    charts = datos.get("charts", {})
    blocks = ""
    for key, title, cid in (
        ("equity", "Evolución de 10.000 $", "weekly_equity"),
        ("return_drawdown", "Rentabilidad frente a caída máxima", "weekly_return_drawdown"),
    ):
        if charts.get(key):
            src = charts.get(f"{key}_src", f"cid:{cid}")
            blocks += f'<h3 style="color:#334155">{_e(title)}</h3><img src="{_e(src)}" alt="{_e(title)}" style="display:block;width:100%;max-width:820px;height:auto;border:0">'
        else:
            blocks += f'<div style="padding:16px;background:#f8fafc;color:#64748b;margin:10px 0">{_e(title)} no disponible: todavía no hay suficiente historial con una fecha inicial común.</div>'
    blocks += '<p style="font-size:12px;color:#64748b">Las carteras situadas más arriba generan mayor rentabilidad; las situadas más cerca del 0% de caída máxima han sufrido descensos menores.</p>'
    return _section("EVOLUCIÓN DEL CAPITAL Y MAPA DE RIESGO", blocks)


def _week(datos):
    def block(title, rows):
        content = "<br>".join(_e(row) for row in rows) or "No hay datos relevantes esta semana."
        return f'<td valign="top" style="width:33%;padding:12px;border:1px solid #e2e8f0"><b>{_e(title)}</b><p style="line-height:1.7;color:#475569">{content}</p></td>'
    html = '<table width="100%" cellpadding="0" cellspacing="8"><tr>'
    html += block("MÁS PERSISTENTES", datos["persistent"])
    html += block("MAYORES MEJORAS", datos["improving"])
    html += block("EVENTOS RECIENTES", datos["events"])
    html += "</tr></table>"
    return _section("QUÉ HA OCURRIDO ESTA SEMANA", html)


def _ideas(datos):
    html = ""
    for idea in datos["top_candidates"]:
        html += (f'<div style="border:1px solid #e2e8f0;border-left:4px solid #3b82f6;border-radius:8px;padding:15px;margin:10px 0">'
                 f'<div style="font-size:17px;font-weight:bold">{_e(idea["symbol"])} '
                 f'<span style="float:right;color:#1d4ed8">{_e(idea["priority"])} · {idea["score"]}/100</span></div>'
                 f'<table width="100%" style="font-size:13px;margin-top:10px;color:#475569">'
                 f'<tr><td width="110"><b>Técnico</b></td><td>{_e(idea["technical"])}</td></tr>'
                 f'<tr><td><b>Fundamental</b></td><td>{_e(idea["fundamental"])}</td></tr>'
                 f'<tr><td><b>Analistas</b></td><td>{_e(idea["analysts"])}</td></tr>'
                 f'<tr><td><b>Noticias</b></td><td>{_e(idea["news"])}</td></tr>'
                 f'<tr><td><b>Lectura conjunta</b></td><td>{_e(idea["reading"])}</td></tr></table></div>')
    return _section("CANDIDATOS DESTACADOS", html or "<p>No hay candidatos A+/A esta semana.</p>")


def _tracking(datos):
    html = ('<div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:12px;margin:12px 0">'
            '<b>Resultados fuera de muestra (OOS)</b><br>Resultados obtenidos después de congelar las reglas de la estrategia. '
            'Son especialmente importantes porque no se utilizaron para diseñarla. Una muestra pequeña todavía no permite extraer conclusiones firmes.</div>')
    for group in datos["paper_tracking"]:
        rows = ""
        for r in group["rows"]:
            rows += (f'<tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">{_e(r["horizon"])}</td>'
                     f'<td align="right" style="padding:8px;border-bottom:1px solid #e2e8f0"><b>{_e(r["n"])}</b></td>'
                     f'<td align="right" style="padding:8px;border-bottom:1px solid #e2e8f0">{_pct(r["return"])}</td>'
                     f'<td align="right" style="padding:8px;border-bottom:1px solid #e2e8f0">{_pct(r["excess"], "pp")}</td>'
                     f'<td align="right" style="padding:8px;border-bottom:1px solid #e2e8f0">{_pct(r["beat"], "%")}</td></tr>')
        html += (f'<h3 style="color:#334155">{_e(group["title"])}</h3><table width="100%" style="border-collapse:collapse;font-size:13px">'
                 '<tr style="background:#f8fafc"><th align="left" style="padding:8px">Horizonte</th><th align="right">n</th>'
                 '<th align="right">Rentabilidad media</th><th align="right">Exceso vs. SPY</th><th align="right">Supera a SPY</th></tr>' + rows + '</table>')
    return _section("VALIDACIÓN DE SEÑALES", html)


def _highlights(datos):
    items = datos.get("highlights", [])
    if not items:
        return _section(
            "DATOS DESTACADOS DEL LABORATORIO",
            '<p style="color:#64748b">Todavía no hay suficiente historial operativo dentro de la ventana común.</p>',
            "Comparaciones descriptivas del laboratorio; no son recomendaciones de inversión."
        )
    html = '<table width="100%" cellpadding="8"><tr>'
    for title, value in items:
        html += f'<td style="border:1px solid #e2e8f0"><span style="color:#64748b">{_e(HIGHLIGHT_LABELS.get(title, title))}</span><br><b>{_e(value)}</b></td>'
    html += "</tr></table>"
    return _section("DATOS DESTACADOS DEL LABORATORIO", html, "Comparaciones descriptivas del laboratorio; no son recomendaciones de inversión.")


def _how_to_read():
    terms = [
        ("Rentabilidad", "Variación porcentual del capital de la cartera."),
        ("Max Drawdown (caída máxima)", "La mayor pérdida experimentada desde un máximo anterior."),
        ("Exceso frente a SPY", "Cuánto mejor o peor se comportó la cartera frente a SPY durante exactamente el mismo periodo."),
        ("OOS / fuera de muestra", "Datos obtenidos después de congelar las reglas de una estrategia."),
        ("SPY", "Referencia de renta variable estadounidense."),
        ("60/40", "Referencia clásica compuesta por un 60% de acciones y un 40% de bonos."),
        ("SHY", "Referencia defensiva de deuda del Tesoro estadounidense a corto plazo."),
        ("Riesgo activo", "Defensive Candidate mantiene SPY."),
        ("Modo defensivo", "Defensive Candidate se refugia en SHY."),
        ("n", "Tamaño de la muestra. Una muestra pequeña implica una incertidumbre elevada."),
    ]
    html = "".join(f'<p style="margin:7px 0"><b>{_e(k)}:</b> {_e(v)}</p>' for k, v in terms)
    return _section("CÓMO INTERPRETAR ESTE INFORME", html)


def _detalle_tecnico_en_espanol(texto):
    """Traduce rótulos heredados solo para la copia visible dentro del HTML."""
    reemplazos = {
        "PAPER TRACKING": "VALIDACIÓN DE SEÑALES",
        "PAPER PORTFOLIOS": "CARTERAS SIMULADAS",
        "Yahoo Analyst Consensus": "Consenso de analistas de Yahoo",
        "Paper Tracking": "Validación de señales",
        "Paper Portfolio Live": "Carteras simuladas continuas",
        "Momentum V4 paper": "Momentum V4 simulado",
        "Reversal V1 paper": "Reversal V1 simulado",
        "News analizadas": "Noticias analizadas",
        "News POSITIVO": "Noticias POSITIVAS",
        "Performance": "Rendimiento",
        "Target": "Precio objetivo",
        "Score analizado": "Puntuación analizada",
        "Score v4": "Puntuación v4",
        "Scans comparables analizados": "Análisis comparables realizados",
        "scans comparables": "análisis comparables",
        "scans": "análisis",
        "Buy & Hold": "comprar y mantener",
        "Portfolio": "Cartera",
        "Equity": "Capital",
        "Return": "Rentabilidad",
        "Cash": "Efectivo",
        "100% cash": "100% efectivo",
        "Posicion: cash": "Posición: efectivo",
    }
    for original, traducido in reemplazos.items():
        texto = texto.replace(original, traducido)
    return texto


def generar_html_weekly(datos):
    """Render a complete dashboard while retaining the full text as technical detail."""
    meta = datos["meta"]
    body = (_overview(datos) + _scoreboard(datos) + _charts(datos) + _highlights(datos)
            + _week(datos) + _ideas(datos) + _tracking(datos) + _strategy_cards(datos)
            + _how_to_read()
            + _section("DETALLE DE CARTERAS Y MÉTRICAS TÉCNICAS",
                       f'<pre style="white-space:pre-wrap;font-family:Consolas,monospace;font-size:11px;line-height:1.45;color:#334155">{_e(_detalle_tecnico_en_espanol(datos["plain_text"]))}</pre>',
                       "A continuación se conserva el informe técnico completo, con todas sus métricas y muestras."))
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>@media only screen and (max-width:620px){{table,tbody,tr,td{{max-width:100%!important}} td{{font-size:12px!important}}}}</style></head>
<body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#1e293b">
<div style="display:none;max-height:0;overflow:hidden">Informe semanal del laboratorio de investigación y carteras simuladas.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 8px">
<div style="max-width:900px;text-align:left"><div style="background:#0f172a;color:white;padding:28px;border-radius:10px">
<div style="font-size:13px;letter-spacing:2px;color:#93c5fd">TRADING LAB</div><h1 style="margin:6px 0;font-size:30px">Informe semanal</h1>
<div style="color:#cbd5e1;font-size:13px">Generado: {_e(meta["generated"])} · Sesión de mercado: {_e(meta["market_date"])} · Versión del score: {_e(meta["score_version"])} · {_e(meta["scans"])} análisis comparables</div>
<p style="margin:14px 0 0;color:#93c5fd">Laboratorio de investigación y carteras simuladas — sin dinero real</p></div>{body}
<div style="background:#0f172a;color:#cbd5e1;padding:20px;border-radius:10px;font-size:12px;line-height:1.6">
<b style="color:white">Solo investigación y simulación. No se ejecutan órdenes reales.</b><br>
Este informe identifica activos y sistemas para estudiarlos con mayor profundidad. No constituye una recomendación de compra o venta.</div>
</div></td></tr></table></body></html>'''
