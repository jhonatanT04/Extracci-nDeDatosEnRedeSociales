"""
Modelo de datos para resultados de análisis de sentimientos (Práctica 07).

Conserva la trazabilidad de la Práctica 06 (fuente, consulta, texto,
id_unico) y le añade la clasificación obtenida, para que cada opinión
clasificada pueda rastrearse hasta su fuente y su consulta de origen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class RegistroSentimiento:
    # --- Trazabilidad heredada del Registro original (Práctica 06) ---
    fuente: str
    consulta: str
    texto: str
    id_unico: str = ""
    autor: str = ""
    fecha_publicacion: str = ""
    url: str = ""
    metricas: dict = field(default_factory=dict)

    # --- Resultado del análisis de sentimientos ---
    sentimiento: str = "no_clasificable"
    justificacion: str = ""
    modelo: str = ""
    clasificado_en: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def como_dict(self) -> dict:
        return asdict(self)
