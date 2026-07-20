"""Generador de storytelling: interpretación cualitativa automática de los
resultados de clasificación de sentimientos.

No es un simple recuento — construye un texto narrativo que:
  - identifica el sentimiento predominante y lo contextualiza con % y n,
  - compara el comportamiento entre redes sociales (dónde se concentra el
    rechazo/aprobación, cuál es más neutral/informativa),
  - pondera por interacción (likes) para distinguir una opinión aislada de
    una que resuena con la audiencia,
  - cita 1-2 justificaciones reales del LLM como evidencia textual.

Es determinístico (basado en reglas sobre las cifras agregadas), no vuelve a
llamar a un LLM: así siempre está disponible sin costo ni latencia extra al
terminar un job, y es reproducible.
"""

from __future__ import annotations

SENTIMIENTOS_POSITIVOS = {"positivo"}
SENTIMIENTOS_NEGATIVOS = {"negativo"}

ETIQUETAS = {
    "positivo": "positivo",
    "negativo": "negativo",
    "neutral": "neutral",
    "mixto": "mixto",
    "no_clasificable": "no clasificable",
}


def _pct(parte: int, total: int) -> float:
    return round((parte / total) * 100, 1) if total else 0.0


def _dominante(conteo: dict) -> tuple[str, int]:
    return max(conteo.items(), key=lambda kv: kv[1])


def generar_storytelling(dataset: dict) -> dict:
    """Recibe el dict de un `sentimientos_*.json` (con `registros` y
    `resumen_por_fuente`) y devuelve un dict con:
        - resumen_global: {sentimiento: n}
        - narrativa: lista de párrafos (str) en español
        - hallazgos: lista corta de bullets con los datos más citables
    """
    registros = dataset.get("registros", [])
    resumen_por_fuente = dataset.get("resumen_por_fuente", {})
    total = len(registros)

    if total == 0:
        return {
            "resumen_global": {},
            "narrativa": ["No hay registros clasificados todavía para generar un análisis."],
            "hallazgos": [],
        }

    resumen_global: dict[str, int] = {}
    for r in registros:
        s = r.get("sentimiento", "no_clasificable")
        resumen_global[s] = resumen_global.get(s, 0) + 1

    sent_dom, n_dom = _dominante(resumen_global)
    pct_dom = _pct(n_dom, total)

    pct_positivo = _pct(resumen_global.get("positivo", 0), total)
    pct_negativo = _pct(resumen_global.get("negativo", 0), total)

    problematica = dataset.get("problematica", "el tema consultado")

    parrafos = []

    # Párrafo 1: panorama general
    parrafos.append(
        f"Sobre {total} opiniones analizadas respecto a «{problematica}», el "
        f"sentimiento predominante es **{ETIQUETAS.get(sent_dom, sent_dom)}** "
        f"({n_dom} de {total}, {pct_dom}%). En conjunto, un {pct_positivo}% de "
        f"las opiniones son favorables y un {pct_negativo}% son de rechazo, lo "
        f"que da una idea del balance general de la conversación pública."
    )

    # Párrafo 2: comparación entre fuentes
    if len(resumen_por_fuente) > 1:
        filas = []
        for fuente, conteo in resumen_por_fuente.items():
            total_fuente = sum(conteo.values())
            if total_fuente == 0:
                continue
            dom_fuente, n_dom_fuente = _dominante(conteo)
            filas.append((fuente, dom_fuente, _pct(n_dom_fuente, total_fuente), total_fuente))

        if filas:
            mas_negativa = max(
                (f for f in filas if f[1] in SENTIMIENTOS_NEGATIVOS),
                key=lambda f: f[2],
                default=None,
            )
            mas_positiva = max(
                (f for f in filas if f[1] in SENTIMIENTOS_POSITIVOS),
                key=lambda f: f[2],
                default=None,
            )

            frase_fuentes = ", ".join(
                f"**{f[0]}** ({f[3]} opiniones) se inclina hacia {ETIQUETAS.get(f[1], f[1])} "
                f"({f[2]}%)"
                for f in filas
            )
            parrafo2 = f"Al comparar por red social: {frase_fuentes}."
            if mas_negativa and mas_positiva and mas_negativa[0] != mas_positiva[0]:
                parrafo2 += (
                    f" El contraste más marcado está entre **{mas_negativa[0]}**, "
                    f"donde domina el rechazo, y **{mas_positiva[0]}**, con una "
                    f"postura más favorable — evidencia de que la percepción del "
                    f"tema no es uniforme entre plataformas, sino que varía según "
                    f"la audiencia y el formato de cada red."
                )
            parrafos.append(parrafo2)

    # Párrafo 3: ponderación por interacción (likes) — opinión aislada vs viral
    registros_con_likes = [
        r for r in registros if (r.get("metricas") or {}).get("likes", 0)
    ]
    if registros_con_likes:
        top = sorted(
            registros_con_likes,
            key=lambda r: (r.get("metricas") or {}).get("likes", 0),
            reverse=True,
        )[:5]
        conteo_top = {}
        for r in top:
            s = r.get("sentimiento", "no_clasificable")
            conteo_top[s] = conteo_top.get(s, 0) + 1
        sent_top, _ = _dominante(conteo_top)
        parrafos.append(
            f"Ponderando por interacción (likes), las opiniones con más "
            f"respaldo de la audiencia son mayoritariamente de sentimiento "
            f"**{ETIQUETAS.get(sent_top, sent_top)}**, lo que sugiere que ese "
            f"punto de vista no solo es frecuente sino también el que más "
            f"resuena entre otros usuarios."
        )

    # Párrafo 4: evidencia textual (justificaciones del LLM)
    ejemplos = [
        r for r in registros
        if r.get("sentimiento") == sent_dom and r.get("justificacion")
    ][:2]
    if ejemplos:
        citas = " ".join(
            f'«{e["justificacion"].strip()}»' for e in ejemplos
        )
        parrafos.append(
            f"Como evidencia textual de este patrón, el modelo justificó "
            f"algunas de estas clasificaciones así: {citas}"
        )

    hallazgos = [
        f"{n_dom} de {total} opiniones ({pct_dom}%) son de sentimiento {ETIQUETAS.get(sent_dom, sent_dom)}.",
        f"{pct_positivo}% positivo vs. {pct_negativo}% negativo en el total del corpus.",
    ]
    for fuente, conteo in resumen_por_fuente.items():
        total_fuente = sum(conteo.values())
        if total_fuente == 0:
            continue
        dom_fuente, n_dom_fuente = _dominante(conteo)
        hallazgos.append(
            f"{fuente}: predomina {ETIQUETAS.get(dom_fuente, dom_fuente)} "
            f"({_pct(n_dom_fuente, total_fuente)}% de {total_fuente} opiniones)."
        )

    return {
        "resumen_global": resumen_global,
        "narrativa": parrafos,
        "hallazgos": hallazgos,
    }
