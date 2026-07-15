#!/usr/bin/env python3
"""
Punto de entrada de la práctica:
"Análisis PARALELO de sentimientos sobre datos de redes sociales" (Práctica 07).

Usa como entrada el dataset combinado generado por la Práctica 06
(`datos/dataset_*.json`). Si todavía no corriste el scraping real, usa el
dataset inventado `datos/dataset_prueba.json` para probar el flujo completo.

Uso:
    python3 main_sentimientos.py                            # dataset más reciente en datos/
    python3 main_sentimientos.py --archivo datos/dataset_prueba.json
    python3 main_sentimientos.py --benchmark                # compara secuencial vs paralelo
    python3 main_sentimientos.py --secuencial                # sólo modo secuencial

Requiere GROQ_API_KEY definida en el archivo .env (clave gratuita:
https://console.groq.com/keys).
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from modelo import AnalizadorSentimientoGroq
from src.almacenamiento import cargar_dataset
from src.almacenamiento_sentimientos import guardar
from src.controlador_sentimientos import ControladorSentimientos
from src.utilidades import log


def main():
    parser = argparse.ArgumentParser(description="Análisis paralelo de sentimientos.")
    parser.add_argument(
        "--archivo",
        default=None,
        help="Ruta a un dataset_*.json específico (por defecto: el más reciente en datos/).",
    )
    parser.add_argument("--benchmark", action="store_true",
                        help="Compara tiempos secuencial vs paralelo.")
    parser.add_argument("--secuencial", action="store_true",
                        help="Ejecuta sólo en modo secuencial.")
    args = parser.parse_args()

    dataset = cargar_dataset(args.archivo)
    registros = dataset["registros"]

    print("=" * 70)
    print("  ANÁLISIS PARALELO DE SENTIMIENTOS")
    print("=" * 70)
    print(f"Problemática:\n  {dataset.get('problematica', '(no definida)')}\n")
    print(f"Registros a clasificar: {len(registros)}\n")

    analizador = AnalizadorSentimientoGroq()
    controlador = ControladorSentimientos(analizador)

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


if __name__ == "__main__":
    main()
