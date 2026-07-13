"""
Modelo de datos unificado.

Todas las fuentes, aunque tengan formatos muy distintos, se normalizan al
mismo `Registro`. Esto asegura la TRAZABILIDAD exigida por la práctica: cada
registro identifica de qué fuente proviene, qué consulta lo originó y cuál es
el contenido textual, además de metadatos de interacción cuando existen.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Registro:
    # --- Trazabilidad obligatoria ---
    fuente: str                 # red social / fuente digital de origen
    consulta: str               # palabra clave, hashtag o criterio usado
    texto: str                  # contenido textual obtenido (limpio)

    # --- Metadatos complementarios ---
    id_original: str = ""       # id del post/comentario en la fuente
    autor: str = ""             # usuario / autor
    fecha_publicacion: str = "" # fecha de publicación (ISO 8601)
    url: str = ""               # enlace a la publicación
    idioma: str = ""            # idioma declarado por la fuente, si existe

    # Métricas de interacción (likes, comentarios, etc.). Diccionario flexible
    # porque cada fuente expone métricas distintas.
    metricas: dict = field(default_factory=dict)

    # Momento exacto de la extracción (evidencia de ejecución).
    extraido_en: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def id_unico(self) -> str:
        """Hash estable para deduplicar registros entre ejecuciones."""
        base = f"{self.fuente}|{self.id_original}|{self.url}|{self.texto[:80]}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    def como_dict(self) -> dict:
        d = asdict(self)
        d["id_unico"] = self.id_unico()
        return d

    def es_valido(self) -> bool:
        """Descarta registros sin texto útil para el análisis posterior."""
        return bool(self.texto and len(self.texto.strip()) >= 15)
