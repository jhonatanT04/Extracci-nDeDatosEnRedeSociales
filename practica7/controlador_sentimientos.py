"""
Controlador de análisis de sentimientos PARALELO (Práctica 07).

Técnica de paralelismo y su justificación
------------------------------------------
Clasificar un texto implica una llamada HTTP a la API de OpenAI: es una tarea
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

from modelo import crear_analizador

from modelos_sentimiento import RegistroSentimiento
from utilidades import log

_FIN = object()


class ControladorSentimientos:
    def __init__(self, analizador=None, proveedor: str = "groq"):
        """Inicializa el controlador con un analizador dado o lo crea.

        Args:
            analizador: instancia de AnalizadorSentimientoGroq o OpenAI.
                        Si es None, se crea uno con `crear_analizador(proveedor)`.
            proveedor: 'groq' o 'openai'. Sólo se usa si analizador es None.
        """
        self.analizador = analizador or crear_analizador(proveedor)

    @staticmethod
    def _agrupar_por_fuente(registros: list[dict]) -> dict[str, list[dict]]:
        """Divide el corpus en bloques, uno por red social (fuente).

        Esto permite que cada hilo procese todos los textos de su fuente,
        cumpliendo con el requerimiento de 'clasificar sentimientos por
        fuente de información' y 'dividir el corpus en bloques de datos'.
        """
        bloques: dict[str, list[dict]] = {}
        for r in registros:
            bloques.setdefault(r["fuente"], []).append(r)
        return bloques

    def _clasificar_registro(self, r: dict) -> RegistroSentimiento:
        """Clasifica un registro individual llamando al modelo de OpenAI."""
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
        """Ejecuta la clasificación de sentimientos en modo PARALELO.

        Arquitectura:
        - Se agrupan los registros por fuente (red social).
        - Se crea un hilo PRODUCTOR por cada fuente, que clasifica sus textos
          llamando a la API de OpenAI y empuja los resultados a una cola.
        - Un hilo CONSUMIDOR drena la cola y recolecta los resultados.
        - El pool de hilos (`ThreadPoolExecutor`) administra el ciclo de vida.

        Como cada clasificación es una llamada HTTP (I/O-bound), los hilos
        permiten que las esperas de red se solapen: mientras un hilo espera
        la respuesta de OpenAI, Python libera el GIL y otro hilo avanza.
        """
        bloques = self._agrupar_por_fuente(registros)
        cola: "queue.Queue" = queue.Queue()
        resultados: list[RegistroSentimiento] = []
        n_bloques = len(bloques)

        def consumidor():
            """Hilo consumidor: drena la cola hasta recibir N señales de FIN
            (una por cada hilo productor)."""
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
            """Hilo productor: clasifica todos los textos de una fuente y
            los empuja a la cola compartida. Si una fuente tiene un volumen grande
            (ej. cientos de registros), utiliza un sub-pool de hilos para solapar
            la latencia I/O sin bloquear a las demás fuentes."""
            log.info("Clasificando %d textos de %s...", len(bloque), fuente)
            if len(bloque) > 15:
                sub_workers = min(12, (len(bloque) // 10) + 2)
                def _clasificar_y_encolar(r):
                    cola.put(self._clasificar_registro(r))
                with ThreadPoolExecutor(
                    max_workers=sub_workers, thread_name_prefix=f"Sub_{fuente[:3]}"
                ) as sub_pool:
                    for r in bloque:
                        sub_pool.submit(_clasificar_y_encolar, r)
            else:
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
        """Ejecuta la clasificación en modo SECUENCIAL (sin hilos).

        Existe solo para medir el speedup con --benchmark: el mismo trabajo
        se hace uno por uno, y se compara el tiempo con el modo paralelo.
        """
        inicio = time.perf_counter()
        resultados = [self._clasificar_registro(r) for r in registros]
        duracion = time.perf_counter() - inicio
        log.info(
            "SECUENCIAL: %d textos clasificados en %.2f s", len(resultados), duracion
        )
        return resultados, duracion
