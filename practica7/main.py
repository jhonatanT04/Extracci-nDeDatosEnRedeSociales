#!/usr/bin/env python3
"""
Punto de entrada — Práctica de laboratorio 07:
"Análisis PARALELO de sentimientos sobre datos de redes sociales"

Usa como entrada el dataset combinado generado por la Práctica 06
(`datos/dataset_*.json`). Si todavía no corriste el scraping real, usa el
dataset inventado `datos/dataset_prueba.json` para probar el flujo completo.

Soporta DOS proveedores de LLM:
  - groq   (por defecto) → usa GROQ_API_KEY del .env
  - openai               → usa OPENAI_API_KEY del .env

Uso:
    python3 main.py --archivo datos/dataset_prueba.json                   # Groq (defecto)
    python3 main.py --archivo datos/dataset_prueba.json --proveedor openai  # OpenAI
    python3 main.py --benchmark                                             # compara sec. vs par.
    python3 main.py --secuencial                                            # sólo secuencial

Requiere la API key correspondiente definida en el archivo .env:
  - GROQ_API_KEY   → https://console.groq.com/keys
  - OPENAI_API_KEY → https://platform.openai.com/api-keys
"""

from __future__ import annotations

import argparse
import os
import sys

# Asegurar que el directorio de la práctica esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Cargar variables de entorno del .env raíz del proyecto
_RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
load_dotenv(os.path.join(_RAIZ, ".env"))

from modelo import crear_analizador, PROVEEDORES
from almacenamiento_sentimientos import cargar_dataset, guardar
from controlador_sentimientos import ControladorSentimientos
from utilidades import log


def main():
    parser = argparse.ArgumentParser(
        description="Análisis paralelo de sentimientos (Práctica 07).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Proveedores disponibles:\n"
            "  groq    → Modelos Llama vía API gratuita de Groq (requiere GROQ_API_KEY)\n"
            "  openai  → Modelos GPT vía API de OpenAI (requiere OPENAI_API_KEY)\n"
        ),
    )
    parser.add_argument(
        "--archivo",
        default=None,
        help="Ruta a un dataset_*.json específico (por defecto: el más reciente en datos/).",
    )
    parser.add_argument(
        "--proveedor",
        default="groq",
        choices=sorted(PROVEEDORES.keys()),
        help="Proveedor de LLM a usar: groq (defecto) o openai.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Compara tiempos secuencial vs paralelo.",
    )
    parser.add_argument(
        "--secuencial",
        action="store_true",
        help="Ejecuta sólo en modo secuencial.",
    )
    args = parser.parse_args()

    dataset = cargar_dataset(args.archivo)
    registros = dataset["registros"]

    proveedor_nombre = args.proveedor.upper()
    print("=" * 70)
    print(f"  ANÁLISIS PARALELO DE SENTIMIENTOS ({proveedor_nombre})")
    print("  Práctica de Laboratorio 07 — Computación Paralela")
    print("=" * 70)
    print(f"Problemática:\n  {dataset.get('problematica', '(no definida)')}\n")
    print(f"Registros a clasificar: {len(registros)}")
    print(f"Fuentes: {', '.join(sorted(set(r['fuente'] for r in registros)))}")
    print(f"Proveedor LLM: {proveedor_nombre}\n")

    analizador = crear_analizador(args.proveedor)
    controlador = ControladorSentimientos(analizador)

    log.info("Modelo: %s | Proveedor: %s", analizador.modelo, proveedor_nombre)

    t_secuencial = t_paralelo = None
    if args.secuencial:
        resultados, t_secuencial = controlador.ejecutar_secuencial(registros)
    elif args.benchmark:
        log.info("== Fase 1/2: modo SECUENCIAL (referencia) ==")
        _, t_secuencial = controlador.ejecutar_secuencial(registros)
        log.info("== Fase 2/2: modo PARALELO (solución) ==")
        resultados, t_paralelo = controlador.ejecutar_paralelo(registros)
    else:
        resultados, t_paralelo = controlador.ejecutar_paralelo(registros)

    info = guardar(resultados, problematica=dataset.get("problematica", ""))

    print("\n" + "-" * 70)
    print("RESUMEN POR FUENTE Y SENTIMIENTO")
    print("-" * 70)
    for fuente, conteo in sorted(info["resumen"].items()):
        print(f"  {fuente}:")
        for sentimiento, n in sorted(conteo.items()):
            print(f"      {sentimiento:<15}: {n}")
    print(f"\nResultados guardados en: {info['ruta']}")

    if t_secuencial is not None and t_paralelo is not None:
        speedup = t_secuencial / t_paralelo if t_paralelo else 0
        print("\n" + "-" * 70)
        print("COMPARACIÓN DE RENDIMIENTO")
        print("-" * 70)
        print(f"Tiempo secuencial    : {t_secuencial:.2f} s")
        print(f"Tiempo paralelo      : {t_paralelo:.2f} s")
        print(f"Aceleración (speedup): {speedup:.2f}x")

    if t_secuencial is not None and t_paralelo is None:
        print(f"\nTiempo secuencial: {t_secuencial:.2f} s")
    elif t_paralelo is not None and t_secuencial is None:
        print(f"\nTiempo paralelo: {t_paralelo:.2f} s")


if __name__ == "__main__":
    main()
