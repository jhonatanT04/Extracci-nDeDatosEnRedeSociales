import json
import os
from time import monotonic, sleep
from urllib.parse import quote

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()


class ScraperTikTok:
    """Extrae publicaciones y comentarios de la búsqueda de TikTok
    usando Selenium sobre un Chrome real."""

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        scrolls_resultados=10,
        max_videos=10,
        max_rondas_comentarios=10,
        max_segundos_comentarios=10,
        archivo_salida="datos/tiktok_publicaciones.json",
    ):
        self.busqueda = busqueda
        self.scrolls_resultados = scrolls_resultados
        self.max_videos = max_videos
        self.max_rondas_comentarios = max_rondas_comentarios
        self.max_segundos_comentarios = max_segundos_comentarios
        self.archivo_salida = archivo_salida
        self.driver = None
        self.gestor = None
        self.publicaciones = []

    def _checkpoint(self):
        """Si otro hilo está iniciando sesión, se bloquea aquí hasta que
        termine (ver GestorLogin)."""
        if self.gestor is not None:
            self.gestor.esperar()

    # ------------------------------------------------------------------
    # Navegador y sesión
    # ------------------------------------------------------------------
    def crear_driver(self):
        service = Service(ChromeDriverManager().install())
        option = webdriver.ChromeOptions()
        option.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(service=service, options=option)

    def iniciar_sesion(self):
        self.driver.get("https://www.tiktok.com/")

        input("Inicia sesión en TikTok si hace falta y presiona ENTER para continuar... ")

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------
    def abrir_buscador(self):
        try:
            boton = self.driver.find_element(
                By.XPATH,
                '//div[@class="TUXButton-label" and text()="Buscar"]'
                '/ancestor::button[1]',
            )
        except Exception:
            # Respaldo: cualquier botón cuyo contenido diga "Buscar".
            boton = self.driver.find_element(
                By.XPATH, '//button[.//div[contains(text(), "Buscar")]]'
            )
        boton.click()
        sleep(3)

    def buscar(self):
        try:
            campo = self.driver.find_element(
                By.CSS_SELECTOR,
                'input[data-e2e="search-user-input"], input[type="search"]',
            )
            campo.send_keys(self.busqueda)
            sleep(1)
            campo.send_keys(Keys.ENTER)
        except Exception:
            # Respaldo: la URL de búsqueda directa funciona igual.
            print("No se encontró el campo de búsqueda; voy por URL directa.")
            self.driver.get(
                "https://www.tiktok.com/search?q=" + quote(self.busqueda)
            )
        sleep(5)

    # ------------------------------------------------------------------
    # Extracción de videos de los resultados
    # ------------------------------------------------------------------
    def extraer_videos(self):
        """Extrae las tarjetas visibles y scrollea hasta el fondo en cada
        ronda para que TikTok siga cargando más videos; se detiene cuando
        varias rondas seguidas ya no aportan videos nuevos."""
        vistos = set()
        rondas_sin_nuevos = 0
        for _ in range(self.scrolls_resultados):
            self._checkpoint()
            tarjetas = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[data-e2e="search_top-item"]'
            )
            nuevos = 0
            for tarjeta in tarjetas:
                if len(self.publicaciones) >= self.max_videos:
                    break
                try:
                    video = self.tarjeta_a_video(tarjeta)
                except StaleElementReferenceException:
                    continue
                if video and video["url"] not in vistos:
                    vistos.add(video["url"])
                    self.publicaciones.append(video)
                    nuevos += 1
                    print(f"[{len(self.publicaciones)}] @{video['autor']}: "
                          f"{video['texto'][:80]}")

            if len(self.publicaciones) >= self.max_videos:
                break

            # Algunas variantes muestran un botón en vez de scroll infinito.
            for boton in self.driver.find_elements(
                By.XPATH,
                '//button[contains(., "Cargar más") or contains(., "Load more")]',
            ):
                try:
                    boton.click()
                    sleep(2)
                except Exception:
                    pass

            # Llegar de verdad al fondo es lo que dispara la carga perezosa:
            # primero la última tarjeta a la vista y luego el fondo del todo.
            if tarjetas:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'end'});", tarjetas[-1]
                    )
                except StaleElementReferenceException:
                    pass
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            sleep(3)

            rondas_sin_nuevos = 0 if nuevos else rondas_sin_nuevos + 1
            if rondas_sin_nuevos >= 3:
                break

        print(f"\nVideos extraídos: {len(self.publicaciones)}")

    def tarjeta_a_video(self, tarjeta):
        try:
            url = tarjeta.find_element(
                By.CSS_SELECTOR, 'a[href*="/video/"]'
            ).get_attribute("href")
        except Exception:
            return None

        # La descripción (con hashtags) está en el pie de la tarjeta,
        # que es un hermano del contenedor del reproductor.
        try:
            pie = tarjeta.find_element(
                By.XPATH,
                './following-sibling::div[@data-e2e="search-card-desc"]'
                ' | .//div[@data-e2e="search-card-desc"]',
            )
        except Exception:
            pie = tarjeta

        try:
            texto = pie.find_element(
                By.CSS_SELECTOR, 'div[data-e2e="search-card-video-caption"]'
            ).text
        except Exception:
            texto = ""
        try:
            autor = pie.find_element(
                By.CSS_SELECTOR, 'p[data-e2e="search-card-user-unique-id"]'
            ).text
        except Exception:
            autor = ""
        try:
            vistas = tarjeta.find_element(
                By.CSS_SELECTOR, 'strong[data-e2e="video-views"]'
            ).text
        except Exception:
            vistas = ""

        return {
            "fuente": "TikTok",
            "consulta": self.busqueda,
            "autor": autor,
            "texto": texto,
            "url": url,
            "vistas": vistas,
        }

    # ------------------------------------------------------------------
    # Comentarios de cada video
    # ------------------------------------------------------------------
    def extraer_comentarios_de_videos(self):
        """Abre cada video por su URL y extrae los comentarios."""
        for n, video in enumerate(self.publicaciones, start=1):
            self._checkpoint()
            print(f"\n[{n}/{len(self.publicaciones)}] Comentarios de {video['url']}")
            try:
                self.driver.get(video["url"])
                sleep(5)
                video["comentarios"] = self.extraer_comentarios()
            except Exception as exc:
                print(f"  No se pudieron extraer: {exc.__class__.__name__}")
                video["comentarios"] = []
            print(f"  Comentarios extraídos: {len(video['comentarios'])}")

    def abrir_pestana_comentarios(self):
        """En la variante nueva del reproductor los comentarios no vienen
        cargados: hay que abrir primero la pestaña 'Comentarios'."""
        try:
            boton = self.driver.find_element(
                By.XPATH,
                '//button[@data-testid="tux-web-tab-bar"]'
                '[.//span[contains(text(), "Comentarios")]]',
            )
            boton.click()
            sleep(3)
        except Exception:
            pass  # variante antigua: los comentarios ya están visibles

    def extraer_comentarios(self):
        """Scrollea el panel de comentarios (virtualizado) extrayendo en cada
        ronda y expandiendo respuestas. Soporta las dos variantes del
        reproductor: la antigua (p[data-e2e=comment-level-N] con id) y la
        nueva de pestañas (span[data-e2e=comment-level-N], sin id)."""
        self.abrir_pestana_comentarios()

        # Primera entrada a los comentarios: dar tiempo a que el panel
        # cargue por completo antes de empezar a extraer.
        sleep(5)

        comentarios = {}
        rondas_sin_nuevos = 0
        inicio = monotonic()
        for _ in range(self.max_rondas_comentarios):
            # Tope de tiempo por video, además del tope de scrolls.
            if monotonic() - inicio > self.max_segundos_comentarios:
                break

            # Expandir "Ver N respuestas" (nivel 2) en cualquiera de sus formas.
            for boton in self.driver.find_elements(
                By.XPATH,
                '//p[starts-with(@data-e2e, "view-more-")]'
                ' | //button[.//div[contains(text(), "respuesta")]]'
                ' | //div[contains(@class, "DivViewRepliesContainer")]'
                '[not(.//button)]',
            ):
                try:
                    boton.click()
                    sleep(1)
                except Exception:
                    pass

            nuevos = 0
            ultimo = None
            for cuerpo in self.driver.find_elements(
                By.CSS_SELECTOR, '[data-e2e^="comment-level-"]'
            ):
                try:
                    contenedor = cuerpo.find_element(
                        By.XPATH,
                        './ancestor::div[@id or '
                        'contains(@class, "DivCommentItemWrapper")][1]',
                    )
                    ultimo = contenedor
                    texto = cuerpo.text
                    autor = contenedor.find_element(
                        By.CSS_SELECTOR, '[data-e2e^="comment-username-"]'
                    ).text
                    # La variante antigua trae el id del comentario; la nueva
                    # no, así que se deduplica por autor+texto.
                    clave = contenedor.get_attribute("id") or f"{autor}|{texto}"
                    if not texto or clave in comentarios:
                        continue
                    nivel = cuerpo.get_attribute("data-e2e")  # comment-level-N
                    comentarios[clave] = {
                        "autor": autor,
                        "texto": texto,
                        "nivel": int(nivel.rsplit("-", 1)[-1]),
                    }
                    nuevos += 1
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue

            # Scroll dentro del panel: llevar el último comentario a la vista
            # hace que el contenedor virtualizado cargue los siguientes.
            if ultimo is not None:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'end'});", ultimo
                    )
                except StaleElementReferenceException:
                    pass
            sleep(2)

            rondas_sin_nuevos = 0 if nuevos else rondas_sin_nuevos + 1
            if rondas_sin_nuevos >= 3:
                break

        return [c for c in comentarios.values() if c["texto"]]

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
                gestor.con_login(self.iniciar_sesion, "TikTok")
            else:
                self.iniciar_sesion()
            self._checkpoint()
            self.abrir_buscador()
            self.buscar()
            self.extraer_videos()
            self.extraer_comentarios_de_videos()
            self.guardar()
        finally:
            self.driver.quit()
