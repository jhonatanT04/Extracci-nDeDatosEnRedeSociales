"""
Utilidades transversales: limpieza de texto y un logger seguro para
entornos multihilo.
"""

from __future__ import annotations

import html
import logging
import re
import sys
import threading


# ---------------------------------------------------------------------------
# Logging seguro para hilos.
# ---------------------------------------------------------------------------
def crear_logger() -> logging.Logger:
    logger = logging.getLogger("sentimientos")
    if logger.handlers:  # evita duplicar handlers si se importa varias veces
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(threadName)-18s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


log = crear_logger()

_lock_impresion = threading.Lock()


# ---------------------------------------------------------------------------
# Limpieza de texto: las redes devuelven HTML/entidades; el análisis de
# sentimientos posterior necesita texto plano.
# ---------------------------------------------------------------------------
_re_tags = re.compile(r"<[^>]+>")
_re_espacios = re.compile(r"\s+")
_re_urls = re.compile(r"https?://\S+")


def limpiar_texto(texto: str, quitar_urls: bool = False) -> str:
    if not texto:
        return ""
    texto = _re_tags.sub(" ", texto)      # quita etiquetas HTML
    texto = html.unescape(texto)          # decodifica &amp; &#39; etc.
    if quitar_urls:
        texto = _re_urls.sub(" ", texto)
    texto = _re_espacios.sub(" ", texto)  # normaliza espacios
    return texto.strip()
