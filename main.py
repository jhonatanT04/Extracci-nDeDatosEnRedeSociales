#!/usr/bin/env python3
"""
Punto de entrada de la práctica:
"Extracción PARALELA de datos desde redes sociales / fuentes digitales".

Uso:
    python3 main.py                # extracción paralela + guardado
    python3 main.py --benchmark    # además compara secuencial vs paralelo
    python3 main.py --secuencial   # sólo modo secuencial (comparación)

Autores: <completar con los integrantes del grupo>
Asignatura: Computación Paralela — UPS
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime

from src import config
from src.almacenamiento import deduplicar, guardar, resumen_por_fuente
from src.controlador import ControladorParalelo
from src.extractores import EXTRACTORES_DISPONIBLES
from src.utilidades import log


def encabezado():
    linea = "=" * 70
    print(linea)
    print("  EXTRACCIÓN PARALELA DE DATOS EN REDES SOCIALES")
    print(linea)
    print(f"Problemática:\n  {config.PROBLEMATICA}\n")
    print(f"Objetivo:\n  {config.OBJETIVO}\n")
    print("Redes sociales seleccionadas:")
    for c in EXTRACTORES_DISPONIBLES:
        print(f"  - {c.nombre}")
    print("\nEstrategia de búsqueda:")
    print(f"  Palabras clave: {config.TERMINOS_BUSQUEDA}")
    print(f"  Hashtags      : {config.HASHTAGS}")
    print(linea + "\n")


def guardar_evidencia(texto: str) -> str:
    os.makedirs(config.DIR_EVIDENCIAS, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(config.DIR_EVIDENCIAS, f"ejecucion_{marca}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


def main():
    parser = argparse.ArgumentParser(description="Extracción paralela de datos.")
    parser.add_argument("--benchmark", action="store_true",
                        help="Compara tiempos secuencial vs paralelo.")
    parser.add_argument("--secuencial", action="store_true",
                        help="Ejecuta sólo en modo secuencial.")
    args = parser.parse_args()

    encabezado()
    controlador = ControladorParalelo(EXTRACTORES_DISPONIBLES)

    lineas_evidencia: list[str] = [
        "EVIDENCIA DE EJECUCIÓN",
        f"Fecha: {datetime.now().isoformat()}",
        f"Problemática: {config.PROBLEMATICA}",
        "",
    ]

    t_secuencial = t_paralelo = None

    if args.secuencial:
        registros, t_secuencial = controlador.ejecutar_secuencial()
    elif args.benchmark:
        log.info("== Fase 1/2: modo SECUENCIAL (referencia) ==")
        _, t_secuencial = controlador.ejecutar_secuencial()
        log.info("== Fase 2/2: modo PARALELO (solución) ==")
        registros, t_paralelo = controlador.ejecutar_paralelo()
    else:
        registros, t_paralelo = controlador.ejecutar_paralelo()

    # --- Post-procesamiento ---
    total_bruto = len(registros)
    registros = deduplicar(registros)
    conteo = resumen_por_fuente(registros)
    info = guardar(registros)

    # --- Reporte final ---
    print("\n" + "-" * 70)
    print("RESUMEN")
    print("-" * 70)
    print(f"Registros brutos    : {total_bruto}")
    print(f"Registros únicos     : {len(registros)}")
    print("Registros por fuente :")
    for fuente, n in sorted(conteo.items()):
        print(f"    {fuente:<12}: {n}")
    print(f"\nDataset combinado (JSON): {info['combinado']}")
    for fuente, ruta in sorted(info["por_fuente"].items()):
        print(f"  {fuente:<12}: {ruta}")

    lineas_evidencia += [
        f"Registros brutos: {total_bruto}",
        f"Registros únicos: {len(registros)}",
        "Registros por fuente:",
    ]
    lineas_evidencia += [f"    {f}: {n}" for f, n in sorted(conteo.items())]
    lineas_evidencia += ["", f"Dataset combinado (JSON): {info['combinado']}"]
    lineas_evidencia += [f"  {f}: {r}" for f, r in sorted(info["por_fuente"].items())]
    lineas_evidencia += [""]

    if t_secuencial is not None and t_paralelo is not None:
        speedup = t_secuencial / t_paralelo if t_paralelo else 0
        print("\n" + "-" * 70)
        print("COMPARACIÓN DE RENDIMIENTO")
        print("-" * 70)
        print(f"Tiempo secuencial : {t_secuencial:.2f} s")
        print(f"Tiempo paralelo    : {t_paralelo:.2f} s")
        print(f"Aceleración (speedup): {speedup:.2f}x")
        lineas_evidencia += [
            "COMPARACIÓN DE RENDIMIENTO",
            f"Tiempo secuencial: {t_secuencial:.2f} s",
            f"Tiempo paralelo  : {t_paralelo:.2f} s",
            f"Speedup          : {speedup:.2f}x",
        ]

    ruta_ev = guardar_evidencia("\n".join(lineas_evidencia) + "\n")
    print(f"\nEvidencia guardada en: {ruta_ev}")


if __name__ == "__main__":
    main()
