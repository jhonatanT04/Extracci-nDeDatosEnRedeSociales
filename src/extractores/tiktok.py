"""
Extractor de TikTok.

TikTok bloquea el scraping automático (detección de bots en `TikTokApi`, ver
README), por lo que las descripciones y comentarios reales sobre el tema se
recolectan manualmente en `datos_manuales/tiktok.csv`. Este extractor lee,
limpia y normaliza ese archivo. Se ejecuta en su propio hilo dentro del pool
paralelo.
"""

from __future__ import annotations

from ..carga_manual import cargar_csv
from ..modelos import Registro
from .base import ExtractorBase


class ExtractorTikTok(ExtractorBase):
    nombre = "TikTok"

    def extraer(self) -> list[Registro]:
        return cargar_csv(self.nombre)
