"""Controlador paralelo de la extracción.

Ejecuta los scrapers de las tres fuentes (Facebook, TikTok, YouTube) en hilos
concurrentes y, al terminar, consolida el dataset unificado.

¿Por qué HILOS y no procesos? El trabajo es I/O-bound: cada scraper pasa la
mayor parte del tiempo esperando al navegador o a la red, no calculando. Con
hilos se solapan esas esperas y además comparten memoria (incluido el
GestorLogin) sin coste de serialización entre procesos.

Un GestorLogin compartido coordina los inicios de sesión manuales de los
scrapers de Selenium: mientras uno pide login en la terminal, los demás hilos
se bloquean para no competir por stdin.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.consolidar import consolidar
from src.gestor_login import GestorLogin
from src.scraper_facebook import ScraperFacebook
from src.scraper_tiktok import ScraperTikTok
from src.scraper_youtube import ScraperYouTube


def _correr(scraper, gestor):
    """Ejecuta un scraper y devuelve (nombre, nº publicaciones, error)."""
    nombre = scraper.__class__.__name__
    try:
        scraper.ejecutar(gestor)
        return (nombre, len(scraper.publicaciones), None)
    except Exception as exc:  # noqa: BLE001
        return (nombre, len(getattr(scraper, "publicaciones", [])), exc)


def ejecutar_paralelo(scrapers=None, consolidar_al_final=True):
    """Lanza los scrapers en paralelo (un hilo por fuente) y consolida."""
    if scrapers is None:
        scrapers = [ScraperFacebook(), ScraperTikTok(), ScraperYouTube()]
    gestor = GestorLogin()

    print(f"Lanzando {len(scrapers)} extractores en paralelo (hilos)...\n")
    with ThreadPoolExecutor(max_workers=len(scrapers)) as pool:
        futuros = [pool.submit(_correr, s, gestor) for s in scrapers]
        for fut in as_completed(futuros):
            nombre, n, err = fut.result()
            if err is None:
                print(f"[OK] {nombre}: {n} publicaciones")
            else:
                print(f"[ERROR] {nombre}: {err.__class__.__name__}: {err}")

    if consolidar_al_final:
        return consolidar()
    return None
