import json
import os
import re
from time import sleep
from urllib.parse import quote

from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By

from src.navegador import crear_driver as crear_navegador

load_dotenv()


class ScraperX:
    """Extrae tweets (y sus respuestas) de la búsqueda de X (Twitter) usando
    Selenium sobre un Chrome real con la sesión del usuario. X usa atributos
    data-testid estables, que son los que se usan como selectores."""

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        scrolls_feed=8,
        max_publicaciones=15,
        max_rondas_comentarios=3,
        archivo_salida="datos/x_publicaciones.json",
        confirmar_login=None,
    ):
        self.busqueda = busqueda
        self.scrolls_feed = scrolls_feed
        self.max_publicaciones = max_publicaciones
        self.max_rondas_comentarios = max_rondas_comentarios
        self.archivo_salida = archivo_salida
        self.driver = None
        self.gestor = None
        self.publicaciones = []
        # Callable sin argumentos que bloquea hasta confirmar el login (CLI usa
        # input(); la app web pasa uno que espera un Event desde el navegador).
        self.confirmar_login = confirmar_login

    def _checkpoint(self):
        """Si otro hilo está iniciando sesión, se bloquea aquí hasta que
        termine (ver GestorLogin)."""
        if self.gestor is not None:
            self.gestor.esperar()

    # ------------------------------------------------------------------
    # Navegador y sesión
    # ------------------------------------------------------------------
    def crear_driver(self):
        self.driver = crear_navegador("x")

    def iniciar_sesion(self):
        # No se navega a x.com automáticamente: solo se abre el navegador (con
        # tu perfil) y se espera tu confirmación. La búsqueda navegará después.
        if self.confirmar_login is not None:
            self.confirmar_login()
        else:
            input("Abre X si hace falta y presiona ENTER para continuar... ")

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------
    def buscar(self):
        # f=live -> pestaña "Más recientes" (orden cronológico).
        url = ("https://x.com/search?q=" + quote(self.busqueda) + "&f=live")
        self.driver.get(url)
        sleep(5)

    # ------------------------------------------------------------------
    # Extracción de un tweet (artículo) a registro
    # ------------------------------------------------------------------
    def _tweet_a_registro(self, articulo):
        # El enlace con el <time> lleva al permalink /usuario/status/<id>.
        try:
            enlace = articulo.find_element(By.XPATH, './/a[.//time]')
            url = (enlace.get_attribute("href") or "").split("?")[0]
        except Exception:
            return None
        if "/status/" not in url:
            return None

        try:
            texto = articulo.find_element(
                By.CSS_SELECTOR, 'div[data-testid="tweetText"]'
            ).text
        except Exception:
            texto = ""

        autor = ""
        try:
            bloque = articulo.find_element(
                By.CSS_SELECTOR, 'div[data-testid="User-Name"]'
            )
            try:
                autor = bloque.find_element(
                    By.XPATH, './/span[starts-with(text(), "@")]'
                ).text
            except Exception:
                autor = (bloque.text or "").split("\n")[0]
        except Exception:
            pass

        return {
            "fuente": "X",
            "consulta": self.busqueda,
            "autor": autor,
            "texto": texto,
            "url": url,
            "metricas": self._metricas(articulo),
        }

    def _metricas(self, articulo):
        """Respuestas/reposts/likes best-effort desde el aria-label del grupo
        de acciones del tweet."""
        metr = {"respuestas": 0, "reposts": 0, "likes": 0}
        try:
            etiqueta = (articulo.find_element(
                By.CSS_SELECTOR, 'div[role="group"]'
            ).get_attribute("aria-label") or "").lower()
        except Exception:
            return metr
        mapa = {
            "respuestas": r"(\d[\d.,]*)\s*(?:respuesta|replies|repl)",
            "reposts": r"(\d[\d.,]*)\s*(?:repost|retweet)",
            "likes": r"(\d[\d.,]*)\s*(?:me gusta|like)",
        }
        for clave, patron in mapa.items():
            m = re.search(patron, etiqueta)
            if m:
                metr[clave] = int(m.group(1).replace(".", "").replace(",", ""))
        return metr

    # ------------------------------------------------------------------
    # Recorrido de la búsqueda (feed de tweets)
    # ------------------------------------------------------------------
    def extraer_publicaciones(self):
        """Scrollea el feed de resultados extrayendo tweets; el feed está
        virtualizado, así que se extrae en cada ronda y se deduplica por URL."""
        vistos = set()
        rondas_sin_nuevos = 0
        while (len(self.publicaciones) < self.max_publicaciones
               and rondas_sin_nuevos < self.scrolls_feed):
            self._checkpoint()
            nuevos = 0
            for art in self.driver.find_elements(
                By.CSS_SELECTOR, 'article[data-testid="tweet"]'
            ):
                if len(self.publicaciones) >= self.max_publicaciones:
                    break
                try:
                    reg = self._tweet_a_registro(art)
                except StaleElementReferenceException:
                    continue
                if reg and reg["texto"] and reg["url"] not in vistos:
                    vistos.add(reg["url"])
                    self.publicaciones.append(reg)
                    nuevos += 1
                    print(f"[{len(self.publicaciones)}] {reg['autor']}: "
                          f"{reg['texto'][:70]}")
            self.driver.execute_script("window.scrollBy(0, 2500);")
            sleep(3)
            rondas_sin_nuevos = 0 if nuevos else rondas_sin_nuevos + 1

        print(f"\nTweets extraídos: {len(self.publicaciones)}")

    # ------------------------------------------------------------------
    # Respuestas (comentarios) de cada tweet
    # ------------------------------------------------------------------
    def extraer_comentarios_de_tweets(self):
        for n, pub in enumerate(self.publicaciones, start=1):
            self._checkpoint()
            try:
                self.driver.get(pub["url"])
                sleep(4)
                pub["comentarios"] = self._extraer_respuestas(pub["url"])
            except Exception as exc:  # noqa: BLE001
                print(f"  No se pudieron extraer respuestas: {exc.__class__.__name__}")
                pub["comentarios"] = []
            print(f"[{n}/{len(self.publicaciones)}] {len(pub['comentarios'])} respuestas")

    def _limite_discover_more(self):
        """Posición vertical (y) del encabezado 'Discover more' / 'Descubre
        más' si existe. Debajo de esa línea, X muestra tweets relacionados
        (sugerencias), NO respuestas al tweet: son el límite de los comentarios
        reales. Devuelve None si aún no aparece."""
        for h in self.driver.find_elements(
            By.XPATH,
            '//*[@role="heading"][.//span[contains(text(), "Discover more") '
            'or contains(text(), "Descubre")]]',
        ):
            try:
                return h.location["y"]
            except Exception:  # noqa: BLE001
                continue
        return None

    def _extraer_respuestas(self, url_tweet):
        """En la página de un tweet, los artículos son el tweet principal y sus
        respuestas. Se descarta el principal, los duplicados y todo lo que esté
        en la zona 'Discover more' (sugerencias, no comentarios). Se scrollea y
        deduplica por URL."""
        respuestas = {}
        for _ in range(self.max_rondas_comentarios):
            limite_y = self._limite_discover_more()

            for art in self.driver.find_elements(
                By.CSS_SELECTOR, 'article[data-testid="tweet"]'
            ):
                try:
                    # Todo lo que quede por debajo del encabezado "Discover
                    # more" son tweets relacionados, no respuestas: se ignora.
                    if limite_y is not None and art.location["y"] >= limite_y:
                        continue
                    reg = self._tweet_a_registro(art)
                except StaleElementReferenceException:
                    continue
                if not reg or not reg["texto"]:
                    continue
                if reg["url"] == url_tweet or reg["url"] in respuestas:
                    continue
                respuestas[reg["url"]] = {
                    "autor": reg["autor"],
                    "texto": reg["texto"],
                    "likes": reg["metricas"].get("likes", 0),
                }

            # Si ya apareció "Discover more", se llegó al final de las
            # respuestas reales: no tiene sentido seguir scrolleando.
            if limite_y is not None:
                break

            self.driver.execute_script("window.scrollBy(0, 2500);")
            sleep(2)
        return list(respuestas.values())

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------
    def guardar(self):
        os.makedirs(os.path.dirname(self.archivo_salida) or ".", exist_ok=True)
        with open(self.archivo_salida, "w", encoding="utf-8") as f:
            json.dump(self.publicaciones, f, ensure_ascii=False, indent=2)
        print(f"\nGuardadas {len(self.publicaciones)} publicaciones en {self.archivo_salida}")

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------
    def ejecutar(self, gestor=None):
        self.gestor = gestor
        self.crear_driver()
        try:
            if gestor is not None:
                gestor.con_login(self.iniciar_sesion, "X")
            else:
                self.iniciar_sesion()
            self._checkpoint()
            self.buscar()
            self.extraer_publicaciones()
            self.extraer_comentarios_de_tweets()
            self.guardar()
        finally:
            self.driver.quit()
