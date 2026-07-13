"""
Extractor de X (Twitter).

X bloquea el scraping automático gratuito y la librería `twikit` está rota
contra sus defensas actuales (ver README), por lo que los tweets reales sobre el
tema se recolectan manualmente en `datos_manuales/x_twitter.csv`. Este extractor
lee, limpia y normaliza ese archivo. Se ejecuta en su propio hilo dentro del
pool paralelo.
"""

from __future__ import annotations

from ..carga_manual import cargar_csv
from ..modelos import Registro
from .base import ExtractorBase


class ExtractorTwitterX(ExtractorBase):
    nombre = "X-Twitter"

    def extraer(self) -> list[Registro]:
        return cargar_csv(self.nombre)
