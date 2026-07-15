"""
Cliente de análisis de sentimientos usando la API de OpenAI.

Se eligió la API de OpenAI (modelos GPT) porque:
  - No requiere descargar pesos de modelo ni tener GPU.
  - Los modelos GPT ofrecen excelente comprensión del español,
    incluyendo sarcasmo, jerga de redes sociales y dobles negaciones.
  - Soporta respuesta estructurada (JSON mode) lo que simplifica
    el post-procesamiento.
  - Permite usar modelos como gpt-4o-mini (económico y rápido)
    o gpt-4o (más preciso) según las necesidades.

La llamada a la API es E/S (se espera la respuesta de red), por eso el
CONTROLADOR (`controlador_sentimientos.py`) la paraleliza con HILOS,
igual que la extracción de la Práctica 06.
"""

from __future__ import annotations

import json
import os
import time

import requests

from .analizador_groq import ResultadoSentimiento, CATEGORIAS_VALIDAS, _SYSTEM_PROMPT

_URL = "https://api.openai.com/v1/chat/completions"


class AnalizadorSentimientoOpenAI:
    """Wrapper delgado sobre la API de chat completions de OpenAI."""

    def __init__(
        self,
        api_key: str | None = None,
        modelo: str | None = None,
        temperatura: float = 0.0,
        timeout: int = 30,
        max_reintentos: int = 3,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Falta OPENAI_API_KEY. Pega tu clave en el archivo .env "
                "(OPENAI_API_KEY=tu_clave) — consíguela en "
                "https://platform.openai.com/api-keys"
            )
        self.modelo = modelo or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperatura = temperatura
        self.timeout = timeout
        self.max_reintentos = max_reintentos

    def clasificar(self, texto: str) -> ResultadoSentimiento:
        """Clasifica el sentimiento de un texto usando la API de OpenAI.

        Envía el texto al modelo GPT con un prompt de sistema que le indica
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
                    # Límite de tasa: esperar y reintentar.
                    espera = float(resp.headers.get("Retry-After", 2 * intento))
                    time.sleep(espera)
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
