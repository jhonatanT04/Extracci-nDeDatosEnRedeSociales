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
DIR_DATOS_RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datos")


def resumen_por_fuente_y_sentimiento(
    resultados: list[RegistroSentimiento],
) -> dict[str, dict[str, int]]:
    """Genera un resumen agregado: {fuente: {sentimiento: conteo}}."""
    resumen: dict[str, dict[str, int]] = {}
    for r in list(resultados):
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

    Guarda tanto en practica7/datos como en ../datos (raíz del proyecto)
    para que todo el resto del proyecto pueda consumir los sentimientos.
    """
    os.makedirs(DIR_DATOS, exist_ok=True)
    os.makedirs(DIR_DATOS_RAIZ, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_p7 = os.path.join(DIR_DATOS, f"sentimientos_{marca}.json")
    ruta_raiz = os.path.join(DIR_DATOS_RAIZ, f"sentimientos_{marca}.json")

    resumen = resumen_por_fuente_y_sentimiento(resultados)
    contenido = {
        "problematica": problematica,
        "generado_en": datetime.now().isoformat(),
        "total_registros": len(resultados),
        "resumen_por_fuente": resumen,
        "registros": [r.como_dict() for r in resultados],
    }
    
    with open(ruta_p7, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)

    try:
        with open(ruta_raiz, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Si no se puede escribir en la raíz por algún motivo, se conserva en practica7/datos

    return {"ruta": ruta_p7, "ruta_raiz": ruta_raiz, "resumen": resumen, "total": len(resultados)}


def listar_datasets(directorio: str | None = None) -> list[str]:
    """Rutas de los datasets combinados disponibles, del más viejo al más
    reciente (por fecha de modificación).

    Busca tanto en 'datos' de la raíz del proyecto (donde Práctica 06 exporta
    los JSON reales) como en 'practica7/datos'. Prioriza datasets reales
    sobre 'dataset_prueba.json'.
    """
    if directorio is not None:
        directorios = [directorio] if os.path.isdir(directorio) else []
    else:
        directorios = [d for d in [DIR_DATOS_RAIZ, DIR_DATOS] if os.path.isdir(d)]

    archivos_reales = []
    archivos_prueba = []

    for d in directorios:
        for f in os.listdir(d):
            if f.startswith("dataset_") and f.endswith(".json"):
                ruta = os.path.join(d, f)
                if f == "dataset_prueba.json":
                    archivos_prueba.append(ruta)
                else:
                    archivos_reales.append(ruta)

    if archivos_reales:
        return sorted(archivos_reales, key=os.path.getmtime)
    return sorted(archivos_prueba, key=os.path.getmtime)


def cargar_dataset(ruta: str | None = None) -> dict:
    """Carga un dataset combinado generado por la Práctica 06.

    Si no se especifica ruta, toma el más reciente y real de datos/ (o raíz/datos/).
    Si se especifica un nombre o ruta, la resuelve de forma inteligente.
    """
    if ruta is None:
        disponibles = listar_datasets()
        if not disponibles:
            raise FileNotFoundError(
                f"No hay ningún 'dataset_*.json' en {DIR_DATOS}/ ni en {DIR_DATOS_RAIZ}/. "
                "Corre primero la Práctica 06 (python3 main.py) o usa el "
                "dataset de prueba con --archivo datos/dataset_prueba.json"
            )
        ruta = disponibles[-1]
    else:
        # Resolver ruta si se pasó un nombre relativo que esté en DIR_DATOS o DIR_DATOS_RAIZ
        if not os.path.exists(ruta):
            candidatos = [
                os.path.join(DIR_DATOS, os.path.basename(ruta)),
                os.path.join(DIR_DATOS_RAIZ, os.path.basename(ruta)),
                os.path.join(DIR_DATOS_RAIZ, ruta),
            ]
            for cand in candidatos:
                if os.path.exists(cand):
                    ruta = cand
                    break

    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)
