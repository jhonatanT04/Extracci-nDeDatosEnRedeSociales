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

from modelos_sentimiento import RegistroSentimiento

DIR_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")


def resumen_por_fuente_y_sentimiento(
    resultados: list[RegistroSentimiento],
) -> dict[str, dict[str, int]]:
    """Genera un resumen agregado: {fuente: {sentimiento: conteo}}."""
    resumen: dict[str, dict[str, int]] = {}
    for r in resultados:
        resumen.setdefault(r.fuente, {}).setdefault(r.sentimiento, 0)
        resumen[r.fuente][r.sentimiento] += 1
    return resumen


def guardar(resultados: list[RegistroSentimiento], problematica: str = "") -> dict:
    """Guarda los resultados en un archivo JSON con trazabilidad completa.

    El archivo incluye:
    - Problemática del estudio
    - Marca temporal de generación
    - Resumen agregado por fuente y sentimiento
    - Lista completa de registros clasificados
    """
    os.makedirs(DIR_DATOS, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(DIR_DATOS, f"sentimientos_{marca}.json")

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


def listar_datasets(directorio: str | None = None) -> list[str]:
    """Rutas de los datasets combinados disponibles, del más viejo al más
    reciente (por fecha de modificación)."""
    d = directorio or DIR_DATOS
    if not os.path.isdir(d):
        return []
    archivos = [
        os.path.join(d, f)
        for f in os.listdir(d)
        if f.startswith("dataset_") and f.endswith(".json")
    ]
    return sorted(archivos, key=os.path.getmtime)


def cargar_dataset(ruta: str | None = None) -> dict:
    """Carga un dataset combinado generado por la Práctica 06.

    Si no se especifica ruta, toma el más reciente en datos/.
    """
    if ruta is None:
        disponibles = listar_datasets()
        if not disponibles:
            raise FileNotFoundError(
                f"No hay ningún 'dataset_*.json' en {DIR_DATOS}/. "
                "Corre primero la Práctica 06 (python3 main.py) o usa el "
                "dataset de prueba con --archivo datos/dataset_prueba.json"
            )
        ruta = disponibles[-1]
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)
