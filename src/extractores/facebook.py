"""
Extractor de Facebook.

Facebook bloquea el scraping automático gratuito (ver README), por lo que las
publicaciones y comentarios reales sobre el tema se recolectan manualmente en
`datos_manuales/facebook.csv`. Este extractor lee, limpia y normaliza ese
archivo. Se ejecuta en su propio hilo dentro del pool paralelo.
"""

from __future__ import annotations

from ..carga_manual import cargar_csv
from ..modelos import Registro
from .base import ExtractorBase


class ExtractorFacebook(ExtractorBase):
    nombre = "Facebook"

    def extraer(self) -> list[Registro]:
        return cargar_csv(self.nombre)
