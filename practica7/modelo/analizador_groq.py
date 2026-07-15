"""
Cliente de análisis de sentimientos usando la API gratuita de Groq.

Se eligió una API de LLM (en vez de un modelo local) porque:
  - No requiere descargar pesos de modelo ni tener GPU.
  - El tier gratuito de Groq alcanza para el volumen de datos de esta
    práctica (decenas/centenas de textos cortos).
  - Un LLM entiende mejor matices del español (sarcasmo, comparaciones,
    negaciones) que un clasificador léxico simple.

La llamada a la API es E/S (se espera la respuesta de red), por eso el
CONTROLADOR (`controlador_sentimientos.py`) la paraleliza con HILOS,
igual que la extracción de la Práctica 06.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import requests

CATEGORIAS_VALIDAS = {"positivo", "negativo", "neutral", "mixto", "no_clasificable"}

_URL = "https://api.groq.com/openai/v1/chat/completions"

_SYSTEM_PROMPT = (
    "Eres un clasificador de sentimientos para comentarios en español "
    "publicados en redes sociales sobre temas sociales/culturales.\n"
    "Dado un texto, responde ÚNICAMENTE un JSON con este formato exacto:\n"
    '{"sentimiento": "positivo|negativo|neutral|mixto|no_clasificable", '
    '"justificacion": "una frase breve"}\n\n'
    "Categorías:\n"
    "- positivo: aprueba, felicita o defiende.\n"
    "- negativo: critica, rechaza o se queja.\n"
    "- neutral: informa o pregunta sin tomar postura.\n"
    "- mixto: mezcla claramente argumentos a favor y en contra.\n"
    "- no_clasificable: texto ambiguo, sin opinión o ininteligible."
)


@dataclass
class ResultadoSentimiento:
    """Resultado de clasificación de sentimiento (compartido por ambos proveedores)."""
    sentimiento: str
    justificacion: str
    modelo: str
    intentos: int = 1


class AnalizadorSentimientoGroq:
    """Wrapper delgado sobre la API de chat completions de Groq."""

    def __init__(
        self,
        api_key: str | None = None,
        modelo: str | None = None,
        temperatura: float = 0.0,
        timeout: int = 30,
        max_reintentos: int = 5,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Falta GROQ_API_KEY. Pega tu clave en el archivo .env "
                "(GROQ_API_KEY=tu_clave) — consíguela gratis en "
                "https://console.groq.com/keys"
            )
        self.modelo = modelo or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.temperatura = temperatura
        self.timeout = timeout
        self.max_reintentos = max_reintentos

    def clasificar(self, texto: str) -> ResultadoSentimiento:
        """Clasifica el sentimiento de un texto usando la API de Groq.

        Envía el texto al modelo Llama con un prompt de sistema que le indica
        las categorías válidas y el formato JSON de respuesta. Maneja
        reintentos ante rate-limit (429) y errores de red.
        """
        payload = {
            "model": self.modelo,
            "temperature": self.temperatura,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": texto[:2000]},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        ultimo_error: Exception | None = None
        for intento in range(1, self.max_reintentos + 1):
            try:
                resp = requests.post(
                    _URL, headers=headers, json=payload, timeout=self.timeout
                )
                if resp.status_code == 429:
                    # Límite del tier gratuito: esperar y reintentar.
                    espera = float(resp.headers.get("Retry-After", min(60, 3 * (2 ** intento))))
                    time.sleep(espera + 1.0)
                    continue
                resp.raise_for_status()
                contenido = resp.json()["choices"][0]["message"]["content"]
                data = json.loads(contenido)
                sentimiento = str(data.get("sentimiento", "")).strip().lower()
                if sentimiento not in CATEGORIAS_VALIDAS:
                    sentimiento = "no_clasificable"
                return ResultadoSentimiento(
                    sentimiento=sentimiento,
                    justificacion=str(data.get("justificacion", "")).strip(),
                    modelo=self.modelo,
                    intentos=intento,
                )
            except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
                ultimo_error = e
                time.sleep(1.5 * intento)

        return ResultadoSentimiento(
            sentimiento="no_clasificable",
            justificacion=f"Error tras {self.max_reintentos} intentos: {ultimo_error}",
            modelo=self.modelo,
            intentos=self.max_reintentos,
        )
