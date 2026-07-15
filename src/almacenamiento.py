"""
Almacenamiento en JSON con TRAZABILIDAD (rúbrica: "Almacenamiento correcto").

Genera:
  - Un dataset COMBINADO `datos/dataset_<fecha>.json` con metadatos del estudio
    (contexto, problemática, objetivo) y todos los registros.
  - Un archivo POR RED `datos/<red>_<fecha>.json` para inspección individual.

Cada registro conserva: fuente, consulta, texto, autor, fecha, url y métricas.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from . import config
from .modelos import Registro
from .utilidades import log


def _asegurar_dir(ruta: str) -> None:
    os.makedirs(ruta, exist_ok=True)


def deduplicar(registros: list[Registro]) -> list[Registro]:
    """Elimina duplicados por id_unico (una opinión puede salir en varias
    consultas)."""
    vistos: set[str] = set()
    unicos: list[Registro] = []
    for r in registros:
        clave = r.id_unico()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos


def resumen_por_fuente(registros: list[Registro]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for r in registros:
        conteo[r.fuente] = conteo.get(r.fuente, 0) + 1
    return conteo


def _escribir_json(ruta: str, contenido: dict) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)


def _nombre_seguro(texto: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in texto).strip("_").lower()


def listar_datasets() -> list[str]:
    """Rutas de los datasets combinados disponibles, del más viejo al más
    reciente (por fecha de modificación)."""
    if not os.path.isdir(config.DIR_DATOS):
        return []
    archivos = [
        os.path.join(config.DIR_DATOS, f)
        for f in os.listdir(config.DIR_DATOS)
        if f.startswith("dataset_") and f.endswith(".json")
    ]
    return sorted(archivos, key=os.path.getmtime)


def cargar_dataset(ruta: str | None = None) -> dict:
    """
    Carga un dataset combinado generado por `guardar()` (Práctica 06), para
    usarlo como entrada del análisis de sentimientos (Práctica 07).
    Si no se especifica ruta, toma el más reciente en datos/.
    """
    if ruta is None:
        disponibles = listar_datasets()
        if not disponibles:
            raise FileNotFoundError(
                f"No hay ningún 'dataset_*.json' en {config.DIR_DATOS}/. "
                "Corre primero la Práctica 06 (python3 main.py) o usa el "
                "dataset de prueba con --archivo datos/dataset_prueba.json"
            )
        ruta = disponibles[-1]
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar(registros: list[Registro]) -> dict:
    """
    Guarda el dataset combinado y un archivo JSON por red.
    Devuelve un resumen con rutas y conteos.
    """
    _asegurar_dir(config.DIR_DATOS)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")

    dicts = [r.como_dict() for r in registros]
    conteo = resumen_por_fuente(registros)

    # --- Dataset combinado ---
    ruta_combinado = os.path.join(config.DIR_DATOS, f"dataset_{marca}.json")
    _escribir_json(ruta_combinado, {
        "contexto": config.CONTEXTO,
        "problematica": config.PROBLEMATICA,
        "objetivo": config.OBJETIVO,
        "generado_en": datetime.now().isoformat(),
        "total_registros": len(dicts),
        "registros_por_fuente": conteo,
        "registros": dicts,
    })
    log.info("Dataset combinado: %s (%d registros)", ruta_combinado, len(dicts))

    # --- Un JSON por red ---
    archivos_fuente: dict[str, str] = {}
    for fuente in conteo:
        registros_fuente = [d for d in dicts if d["fuente"] == fuente]
        ruta = os.path.join(config.DIR_DATOS,
                            f"{_nombre_seguro(fuente)}_{marca}.json")
        _escribir_json(ruta, {
            "fuente": fuente,
            "problematica": config.PROBLEMATICA,
            "generado_en": datetime.now().isoformat(),
            "total_registros": len(registros_fuente),
            "registros": registros_fuente,
        })
        archivos_fuente[fuente] = ruta
        log.info("  -> %s (%d registros)", ruta, len(registros_fuente))

    return {
        "combinado": ruta_combinado,
        "por_fuente": archivos_fuente,
        "total": len(dicts),
    }
