"""
Controlador de análisis de sentimientos PARALELO (Práctica 07).

Técnica de paralelismo y su justificación
------------------------------------------
Clasificar un texto implica una llamada HTTP a la API de Groq: es una tarea
E/S-bound (se espera la respuesta de red), igual que la extracción de la
Práctica 06. Por eso se reutiliza el mismo patrón:

  1) El corpus se divide en BLOQUES por fuente (X, Facebook, TikTok...).
  2) Un POOL de HILOS procesa un bloque por hilo, así las tres fuentes se
     clasifican AL MISMO TIEMPO en vez de una tras otra.
  3) Cada hilo empuja sus resultados a una COLA (`queue.Queue`) que un
     CONSUMIDOR central drena -> patrón Productor/Consumidor.

Esto evidencia claramente qué parte del sistema corre en paralelo:
"procesar en paralelo los textos de cada red social" / "clasificar
sentimientos por fuente de información".
"""

from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from modelo import AnalizadorSentimientoGroq

from .modelos_sentimiento import RegistroSentimiento
from .utilidades import log

_FIN = object()


class ControladorSentimientos:
    def __init__(self, analizador: AnalizadorSentimientoGroq | None = None):
        self.analizador = analizador or AnalizadorSentimientoGroq()

    @staticmethod
    def _agrupar_por_fuente(registros: list[dict]) -> dict[str, list[dict]]:
        bloques: dict[str, list[dict]] = {}
        for r in registros:
            bloques.setdefault(r["fuente"], []).append(r)
        return bloques

    def _clasificar_registro(self, r: dict) -> RegistroSentimiento:
        resultado = self.analizador.clasificar(r["texto"])
        return RegistroSentimiento(
            fuente=r["fuente"],
            consulta=r.get("consulta", ""),
            texto=r["texto"],
            id_unico=r.get("id_unico", ""),
            autor=r.get("autor", ""),
            fecha_publicacion=r.get("fecha_publicacion", ""),
            url=r.get("url", ""),
            metricas=r.get("metricas", {}),
            sentimiento=resultado.sentimiento,
            justificacion=resultado.justificacion,
            modelo=resultado.modelo,
        )

    # ------------------------------------------------------------------
    # MODO PARALELO: pool de hilos (uno por fuente) + cola + consumidor
    # ------------------------------------------------------------------
    def ejecutar_paralelo(
        self, registros: list[dict]
    ) -> tuple[list[RegistroSentimiento], float]:
        bloques = self._agrupar_por_fuente(registros)
        cola: "queue.Queue" = queue.Queue()
        resultados: list[RegistroSentimiento] = []
        n_bloques = len(bloques)

        def consumidor():
            terminados = 0
            while terminados < n_bloques:
                item = cola.get()
                if item is _FIN:
                    terminados += 1
                else:
                    resultados.append(item)
                cola.task_done()

        hilo_consumidor = threading.Thread(
            target=consumidor, name="ConsumidorSentimientos", daemon=True
        )
        hilo_consumidor.start()

        def productor(fuente: str, bloque: list[dict]):
            log.info("Clasificando %d textos de %s...", len(bloque), fuente)
            for r in bloque:
                cola.put(self._clasificar_registro(r))
            cola.put(_FIN)

        inicio = time.perf_counter()
        with ThreadPoolExecutor(
            max_workers=n_bloques, thread_name_prefix="Sentimiento"
        ) as pool:
            for fuente, bloque in bloques.items():
                pool.submit(productor, fuente, bloque)
        hilo_consumidor.join()
        duracion = time.perf_counter() - inicio

        log.info(
            "PARALELO: %d textos clasificados en %.2f s", len(resultados), duracion
        )
        return resultados, duracion

    # ------------------------------------------------------------------
    # MODO SECUENCIAL: sólo para comparar tiempos (evidencia de speedup)
    # ------------------------------------------------------------------
    def ejecutar_secuencial(
        self, registros: list[dict]
    ) -> tuple[list[RegistroSentimiento], float]:
        inicio = time.perf_counter()
        resultados = [self._clasificar_registro(r) for r in registros]
        duracion = time.perf_counter() - inicio
        log.info(
            "SECUENCIAL: %d textos clasificados en %.2f s", len(resultados), duracion
        )
        return resultados, duracion
