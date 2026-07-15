"""
Almacenamiento de resultados de análisis de sentimientos (Práctica 07).

Guarda un JSON que relaciona cada texto original con su clasificación y su
fuente (trazabilidad), más un resumen agregado por fuente y por sentimiento,
insumo directo para la visualización y el storytelling del proyecto final.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from . import config
from .modelos_sentimiento import RegistroSentimiento


def resumen_por_fuente_y_sentimiento(
    resultados: list[RegistroSentimiento],
) -> dict[str, dict[str, int]]:
    resumen: dict[str, dict[str, int]] = {}
    for r in resultados:
        resumen.setdefault(r.fuente, {}).setdefault(r.sentimiento, 0)
        resumen[r.fuente][r.sentimiento] += 1
    return resumen


def guardar(resultados: list[RegistroSentimiento], problematica: str = "") -> dict:
    os.makedirs(config.DIR_DATOS, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(config.DIR_DATOS, f"sentimientos_{marca}.json")

    resumen = resumen_por_fuente_y_sentimiento(resultados)
    contenido = {
        "problematica": problematica,
        "generado_en": datetime.now().isoformat(),
        "total_registros": len(resultados),
        "resumen_por_fuente": resumen,
        "registros": [r.como_dict() for r in resultados],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)

    return {"ruta": ruta, "resumen": resumen, "total": len(resultados)}
