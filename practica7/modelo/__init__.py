"""
Paquete del modelo de análisis de sentimientos (Práctica 07).

Soporta DOS proveedores de LLM:
  - **Groq** (tier gratuito, modelos Llama): AnalizadorSentimientoGroq
  - **OpenAI** (modelos GPT): AnalizadorSentimientoOpenAI

Ambos exponen la misma interfaz `.clasificar(texto) -> ResultadoSentimiento`,
así que el controlador paralelo los trata de forma idéntica (polimorfismo).

La función `crear_analizador(proveedor)` es la fábrica recomendada: lee la
variable de entorno correspondiente y devuelve el analizador listo para usar.
"""

from .analizador_groq import AnalizadorSentimientoGroq
from .analizador_openai import AnalizadorSentimientoOpenAI
from .analizador_groq import ResultadoSentimiento  # misma dataclass compartida

PROVEEDORES = {
    "groq": AnalizadorSentimientoGroq,
    "openai": AnalizadorSentimientoOpenAI,
}


def crear_analizador(proveedor: str = "groq"):
    """Fábrica: crea el analizador correspondiente al proveedor elegido.

    Args:
        proveedor: 'groq' o 'openai' (insensible a mayúsculas).

    Returns:
        Instancia de AnalizadorSentimientoGroq o AnalizadorSentimientoOpenAI.

    Raises:
        ValueError: si el proveedor no es válido.
    """
    proveedor = proveedor.strip().lower()
    clase = PROVEEDORES.get(proveedor)
    if clase is None:
        validos = ", ".join(sorted(PROVEEDORES.keys()))
        raise ValueError(
            f"Proveedor '{proveedor}' no reconocido. Opciones válidas: {validos}"
        )
    return clase()


__all__ = [
    "AnalizadorSentimientoGroq",
    "AnalizadorSentimientoOpenAI",
    "ResultadoSentimiento",
    "crear_analizador",
    "PROVEEDORES",
]
