import argparse
import os
import sys

from consolidar import consolidar
from scraper_facebook import ScraperFacebook
from scraper_tiktok import ScraperTikTok
from scraper_youtube import ScraperYouTube


def main():
    parser = argparse.ArgumentParser(
        description="Extracción y Análisis de Datos en Redes Sociales (Prácticas 06 y 07)."
    )
    parser.add_argument(
        "--sentimientos",
        action="store_true",
        help="Ejecutar también el análisis paralelo de sentimientos (Práctica 07) tras consolidar.",
    )
    parser.add_argument(
        "--solo-sentimientos",
        action="store_true",
        help="Omitir scraping y ejecutar solo el análisis paralelo de sentimientos sobre el dataset existente.",
    )
    parser.add_argument(
        "--proveedor",
        default="groq",
        choices=["groq", "openai"],
        help="Proveedor de LLM para el análisis de sentimientos: groq (defecto) u openai.",
    )
    args = parser.parse_args()

    ruta_dataset = None
    if not args.solo_sentimientos:
        ScraperFacebook().ejecutar()
        ScraperTikTok().ejecutar()
        ScraperYouTube().ejecutar()
        ruta_dataset = consolidar()

    if args.sentimientos or args.solo_sentimientos:
        # Importar y ejecutar el flujo de Práctica 07
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "practica7"))
        from almacenamiento_sentimientos import cargar_dataset, guardar
        from controlador_sentimientos import ControladorSentimientos
        from modelo import crear_analizador

        dataset = cargar_dataset(ruta_dataset)
        registros = dataset["registros"]
        proveedor_nombre = args.proveedor.upper()

        print("\n" + "=" * 70)
        print(f"  ANÁLISIS PARALELO DE SENTIMIENTOS ({proveedor_nombre}) - PRÁCTICA 07")
        print("=" * 70)
        print(f"Registros a clasificar: {len(registros)}")

        analizador = crear_analizador(args.proveedor)
        controlador = ControladorSentimientos(analizador)
        resultados, duracion = controlador.ejecutar_paralelo(registros)

        info = guardar(resultados, problematica=dataset.get("problematica", ""))
        print("\n" + "-" * 70)
        print("RESUMEN DE SENTIMIENTOS POR FUENTE")
        print("-" * 70)
        for fuente, conteo in sorted(info["resumen"].items()):
            print(f"  {fuente}:")
            for sentimiento, n in sorted(conteo.items()):
                print(f"      {sentimiento:<15}: {n}")
        print(f"\nResultados guardados en: {info.get('ruta_raiz', info['ruta'])}")


if __name__ == "__main__":
    main()
