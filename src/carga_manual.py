"""
Lectura y normalización de los datos recolectados manualmente.

Cada red tiene un CSV en `datos_manuales/`. Aquí se lee ese CSV, se limpia el
texto y se convierte cada fila en un `Registro` trazable. Es la parte que los
extractores ejecutan EN PARALELO (una red por hilo).

Formato del CSV (sólo `texto` es obligatorio; el resto es opcional):
    texto, consulta, autor, fecha, url, likes, comentarios, compartidos, vistas
"""

from __future__ import annotations

import csv
import os

from . import config
from .modelos import Registro
from .utilidades import limpiar_texto, log

# Columnas numéricas que van al diccionario de métricas.
_COLS_METRICAS = ["likes", "comentarios", "compartidos", "vistas"]


def _a_entero(valor: str) -> int:
    try:
        return int(float(str(valor).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def cargar_csv(nombre_fuente: str) -> list[Registro]:
    """Lee el CSV de una red y devuelve sus registros normalizados."""
    ruta = os.path.join(config.DIR_MANUAL, config.ARCHIVOS_FUENTE[nombre_fuente])
    if not os.path.exists(ruta):
        log.warning("[%s] No existe el archivo %s. Créalo a partir de la "
                    "plantilla. Se omite esta fuente.", nombre_fuente, ruta)
        return []

    registros: list[Registro] = []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        for i, fila in enumerate(lector, start=2):  # fila 1 = encabezado
            texto = limpiar_texto((fila.get("texto") or ""), quitar_urls=True)
            if not texto:
                continue  # salta filas vacías o de ejemplo sin texto
            metricas = {c: _a_entero(fila.get(c, 0)) for c in _COLS_METRICAS}
            registros.append(Registro(
                fuente=nombre_fuente,
                consulta=(fila.get("consulta") or "").strip() or config.CONSULTA_POR_DEFECTO,
                texto=texto,
                autor=(fila.get("autor") or "").strip(),
                fecha_publicacion=(fila.get("fecha") or "").strip(),
                url=(fila.get("url") or "").strip(),
                metricas=metricas,
            ))
    return registros
