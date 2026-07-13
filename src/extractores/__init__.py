"""Extractores concretos, uno por cada red social."""

from .twitter_x import ExtractorTwitterX
from .facebook import ExtractorFacebook
from .tiktok import ExtractorTikTok

# Fuentes activas del sistema. El controlador paralelo recorre esta lista.
# Las tres redes solicitadas: X (Twitter), Facebook y TikTok.
EXTRACTORES_DISPONIBLES = [
    ExtractorTwitterX,
    ExtractorFacebook,
    ExtractorTikTok,
]

__all__ = [
    "ExtractorTwitterX",
    "ExtractorFacebook",
    "ExtractorTikTok",
    "EXTRACTORES_DISPONIBLES",
]
