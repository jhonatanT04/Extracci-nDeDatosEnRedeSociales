"""
Controlador de extracción PARALELA  (núcleo de la práctica).

Técnica de paralelismo empleada y su justificación
--------------------------------------------------
La extracción es una tarea *I/O-bound*: la mayor parte del tiempo el programa
espera respuestas HTTP de las APIs, no calcula. En ese escenario los HILOS son
la herramienta adecuada, porque mientras un hilo espera la red, el GIL de
Python se libera y otro hilo avanza. Así, las N fuentes se consultan al mismo
tiempo y el tiempo total tiende al de la fuente más lenta (no a la suma).

Se combinan tres mecanismos vistos en la asignatura:

  1) POOL de hilos (`ThreadPoolExecutor`): administra automáticamente un hilo
     por fuente. Cada hilo es un PRODUCTOR.
  2) COLA segura (`queue.Queue`): canal de comunicación entre los productores
     (extractores) y un CONSUMIDOR central (el controlador), que recoge los
     registros a medida que llegan.  -> patrón Productor/Consumidor.
  3) Aislamiento de fallos: si una fuente falla, las demás continúan.

También se incluye un modo SECUENCIAL para medir empíricamente la aceleración
(speedup) que aporta el paralelismo (evidencia de ejecución).
"""

from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .extractores.base import ExtractorBase
from .modelos import Registro
from .utilidades import log

# Marcador que un productor coloca en la cola al terminar.
_FIN = object()


class ControladorParalelo:
    def __init__(self, clases_extractores: list[type[ExtractorBase]]):
        self.extractores: list[ExtractorBase] = [c() for c in clases_extractores]

    # ------------------------------------------------------------------
    # MODO PARALELO: pool de productores + cola + consumidor central
    # ------------------------------------------------------------------
    def ejecutar_paralelo(self) -> tuple[list[Registro], float]:
        cola: "queue.Queue" = queue.Queue()
        recolectados: list[Registro] = []
        n_fuentes = len(self.extractores)

        # ---- CONSUMIDOR: corre en su propio hilo y drena la cola ----
        def consumidor():
            productores_terminados = 0
            while productores_terminados < n_fuentes:
                item = cola.get()
                if item is _FIN:
                    productores_terminados += 1
                else:
                    recolectados.append(item)
                cola.task_done()

        hilo_consumidor = threading.Thread(
            target=consumidor, name="Consumidor", daemon=True
        )
        hilo_consumidor.start()

        # ---- PRODUCTOR: cada extractor empuja sus registros a la cola ----
        def productor(extractor: ExtractorBase):
            for registro in extractor.extraer_seguro():
                cola.put(registro)
            cola.put(_FIN)  # avisa al consumidor que esta fuente terminó

        inicio = time.perf_counter()
        with ThreadPoolExecutor(max_workers=n_fuentes,
                                thread_name_prefix="Extractor") as pool:
            for ext in self.extractores:
                pool.submit(productor, ext)
        # Al salir del 'with', todos los productores terminaron.
        hilo_consumidor.join()
        duracion = time.perf_counter() - inicio

        log.info("PARALELO: %d registros en %.2f s", len(recolectados), duracion)
        return recolectados, duracion

    # ------------------------------------------------------------------
    # MODO SECUENCIAL: sólo para comparar tiempos (no es la solución final)
    # ------------------------------------------------------------------
    def ejecutar_secuencial(self) -> tuple[list[Registro], float]:
        recolectados: list[Registro] = []
        inicio = time.perf_counter()
        for ext in self.extractores:
            recolectados.extend(ext.extraer_seguro())
        duracion = time.perf_counter() - inicio
        log.info("SECUENCIAL: %d registros en %.2f s", len(recolectados), duracion)
        return recolectados, duracion
