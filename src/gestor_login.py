"""Coordinación de los inicios de sesión manuales entre hilos.

Los scrapers de Selenium (Facebook, TikTok) necesitan que el usuario inicie
sesión a mano y presione ENTER en la terminal. Si dos hilos pidieran el login
al mismo tiempo, competirían por stdin y por la atención del usuario, y las
salidas se mezclarían. Este gestor garantiza que:

- Solo un hilo hace login a la vez (exclusión mutua con un Lock).
- Mientras un hilo está en el login, los demás hilos se BLOQUEAN al llegar a
  sus puntos de control (un Event compartido) y se reanudan cuando termina.
"""

import threading


class GestorLogin:
    def __init__(self):
        self._lock = threading.Lock()
        self._sin_login = threading.Event()
        self._sin_login.set()  # al inicio no hay ningún login en curso

    def esperar(self):
        """Punto de control de los hilos: si hay un login en curso en otro
        hilo, la ejecución se bloquea aquí hasta que ese login termine."""
        self._sin_login.wait()

    def con_login(self, funcion_login, nombre=""):
        """Ejecuta el login (abrir navegador + input()) en exclusión mutua,
        pausando a los demás hilos hasta que termine."""
        with self._lock:
            self._sin_login.clear()  # pausa a los demás hilos
            try:
                if nombre:
                    print(f"\n>>> [{nombre}] Iniciando sesión — el resto de "
                          f"hilos espera...")
                funcion_login()
            finally:
                self._sin_login.set()  # reanuda a los demás hilos
                if nombre:
                    print(f">>> [{nombre}] Sesión lista — se reanudan los "
                          f"demás hilos.\n")
