"""
Clase base abstracta para todos los extractores.

Define el contrato común: cada extractor sabe extraer una lista de `Registro`
para la problemática configurada. La lógica concreta de cada API vive en las
subclases. Esta abstracción permite que el controlador paralelo trate a todas
las fuentes de forma homogénea (polimorfismo).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..modelos import Registro
from ..utilidades import log


class ExtractorBase(ABC):
    #: Nombre legible de la fuente (se guarda en cada registro).
    nombre: str = "desconocida"

    @abstractmethod
    def extraer(self) -> list[Registro]:
        """Descarga y devuelve los registros normalizados de esta fuente."""
        raise NotImplementedError

    # -- helpers compartidos ------------------------------------------------
    def _log_inicio(self) -> None:
        log.info("[%s] Iniciando extracción...", self.nombre)

    def _log_fin(self, n: int) -> None:
        log.info("[%s] Extracción finalizada: %d registros válidos.",
                 self.nombre, n)

    def extraer_seguro(self) -> list[Registro]:
        """
        Envuelve `extraer()` para que un fallo en una fuente NO detenga al
        resto del sistema (aislamiento de fallos, clave en ejecución paralela).
        """
        self._log_inicio()
        try:
            registros = [r for r in self.extraer() if r.es_valido()]
            self._log_fin(len(registros))
            return registros
        except Exception as exc:  # noqa: BLE001 - se registra y se continúa
            log.error("[%s] Error no recuperable: %s", self.nombre, exc)
            return []
