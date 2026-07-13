"""
Almacenamiento con TRAZABILIDAD (rúbrica: "Almacenamiento correcto").

Persiste el dataset en dos formatos complementarios:
  - JSON: estructura completa, ideal para reprocesar en el proyecto final.
  - CSV : tabular, ideal para inspección rápida y herramientas de análisis.

Cada registro conserva: fuente, consulta, texto, autor, fecha, url y métricas.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from . import config
from .modelos import Registro
from .utilidades import log

# Columnas del CSV. Las métricas se serializan como JSON en una sola columna
# para no perder información variable entre fuentes.
COLUMNAS_CSV = [
    "id_unico", "fuente", "consulta", "texto", "autor",
    "fecha_publicacion", "url", "idioma", "metricas", "extraido_en",
]


def _asegurar_dir(ruta: str) -> None:
    os.makedirs(ruta, exist_ok=True)


def deduplicar(registros: list[Registro]) -> list[Registro]:
    """Elimina duplicados por id_unico (una misma opinión puede aparecer en
    varias consultas)."""
    vistos: set[str] = set()
    unicos: list[Registro] = []
    for r in registros:
        clave = r.id_unico()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos


def guardar(registros: list[Registro], etiqueta: str = "") -> dict:
    """
    Guarda los registros en JSON y CSV con marca de tiempo.
    Devuelve un resumen con las rutas y el conteo.
    """
    _asegurar_dir(config.DIR_DATOS)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufijo = f"_{etiqueta}" if etiqueta else ""
    base = os.path.join(config.DIR_DATOS, f"dataset{sufijo}_{marca}")

    ruta_json = f"{base}.json"
    ruta_csv = f"{base}.csv"

    dicts = [r.como_dict() for r in registros]

    # --- JSON ---
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump({
            "problematica": config.PROBLEMATICA,
            "generado_en": datetime.now().isoformat(),
            "total_registros": len(dicts),
            "registros": dicts,
        }, f, ensure_ascii=False, indent=2)

    # --- CSV ---
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_CSV, extrasaction="ignore")
        writer.writeheader()
        for d in dicts:
            fila = dict(d)
            fila["metricas"] = json.dumps(d.get("metricas", {}), ensure_ascii=False)
            writer.writerow(fila)

    log.info("Dataset guardado: %s (%d registros)", ruta_json, len(dicts))
    log.info("Dataset guardado: %s", ruta_csv)
    return {"json": ruta_json, "csv": ruta_csv, "total": len(dicts)}


def resumen_por_fuente(registros: list[Registro]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for r in registros:
        conteo[r.fuente] = conteo.get(r.fuente, 0) + 1
    return conteo
