import json
import os
from time import sleep
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
        max_rondas_comentarios=15,
        archivo_salida="datos/tiktok_publicaciones.json",
    ):
        self.busqueda = busqueda
        self.scrolls_resultados = scrolls_resultados
        self.max_rondas_comentarios = max_rondas_comentarios
        self.archivo_salida = archivo_salida
        self.driver = None
        self.publicaciones = []

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
        """Scrollea los resultados y extrae cada tarjeta de video.
        TikTok marca sus elementos con data-e2e, que son estables."""
        vistos = set()
        for _ in range(self.scrolls_resultados):
            for tarjeta in self.driver.find_elements(
                By.CSS_SELECTOR, 'div[data-e2e="search_top-item"]'
            ):
                video = self.tarjeta_a_video(tarjeta)
                if video and video["url"] not in vistos:
                    vistos.add(video["url"])
                    self.publicaciones.append(video)
                    print(f"[{len(self.publicaciones)}] @{video['autor']}: "
                          f"{video['texto'][:80]}")
            self.driver.execute_script("window.scrollBy(0, 2500);")
            sleep(3)

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
            print(f"\n[{n}/{len(self.publicaciones)}] Comentarios de {video['url']}")
            try:
                self.driver.get(video["url"])
                sleep(5)
                video["comentarios"] = self.extraer_comentarios()
            except Exception as exc:
                print(f"  No se pudieron extraer: {exc.__class__.__name__}")
                video["comentarios"] = []
            print(f"  Comentarios extraídos: {len(video['comentarios'])}")

    def extraer_comentarios(self):
        """Scrollea el panel de comentarios (virtualizado) extrayendo en cada
        ronda, expande las respuestas, y deduplica por el id del comentario."""
        comentarios = {}
        rondas_sin_nuevos = 0
        for _ in range(self.max_rondas_comentarios):
            # Expandir "Ver N respuestas" visibles (nivel 2).
            for boton in self.driver.find_elements(
                By.CSS_SELECTOR, 'p[data-e2e^="view-more-"]'
            ):
                try:
                    boton.click()
                    sleep(1)
                except Exception:
                    pass

            nuevos = 0
            ultimo = None
            for parrafo in self.driver.find_elements(
                By.CSS_SELECTOR,
                'p[data-e2e="comment-level-1"], p[data-e2e="comment-level-2"]',
            ):
                try:
                    contenedor = parrafo.find_element(
                        By.XPATH, './ancestor::div[@id][1]'
                    )
                    id_comentario = contenedor.get_attribute("id") or ""
                    ultimo = contenedor
                    if not id_comentario or id_comentario in comentarios:
                        continue
                    autor = contenedor.find_element(
                        By.CSS_SELECTOR, 'span[data-e2e^="comment-username-"]'
                    ).text
                    nivel = parrafo.get_attribute("data-e2e")  # comment-level-N
                    comentarios[id_comentario] = {
                        "autor": autor,
                        "texto": parrafo.text,
                        "nivel": int(nivel.rsplit("-", 1)[-1]),
                    }
                    nuevos += 1
                except StaleElementReferenceException:
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
    def ejecutar(self):
        self.crear_driver()
        try:
            self.iniciar_sesion()
            self.abrir_buscador()
            self.buscar()
            self.extraer_videos()
            self.extraer_comentarios_de_videos()
            self.guardar()
        finally:
            self.driver.quit()
