import json
import os
from time import sleep

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()


class ScraperFacebook:
    """Extrae publicaciones y comentarios de la búsqueda de Facebook
    usando Selenium sobre un Chrome real."""

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        scrolls_feed=50,
        max_rondas_comentarios=50,
        archivo_salida="datos/facebook_publicaciones.json",
    ):
        self.busqueda = busqueda
        self.scrolls_feed = scrolls_feed
        self.max_rondas_comentarios = max_rondas_comentarios
        self.archivo_salida = archivo_salida
        self.username = os.getenv("FACEBOOK_USER", "")
        self.password = os.getenv("FACEBOOK_PASSWORD", "")
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
        self.driver.get("https://www.facebook.com/")

        input("ENTER para continuar... ")

        self.driver.find_element(
            By.XPATH, '//div[@role="button" and @aria-label="Iniciar sesión"]'
        ).click()

        input("Inicia sesión en Facebook y presiona ENTER para continuar... ")

    # ------------------------------------------------------------------
    # Búsqueda y feed
    # ------------------------------------------------------------------
    def buscar(self):
        buscador = self.driver.find_element(
            By.XPATH, '//input[@type="search" and @aria-label="Buscar en Facebook"]'
        )
        buscador.click()

        sleep(2)

        buscador.send_keys(self.busqueda)
        buscador.send_keys(Keys.ENTER)

        sleep(5)

    def scrollear_feed(self):
        # Primero se scrollea el feed para que Facebook cargue las publicaciones.
        for _ in range(self.scrolls_feed):
            self.driver.execute_script("window.scrollBy(0, 2200);")
            sleep(3)
        self.driver.execute_script("window.scrollTo(0, 0);")
        sleep(2)

    # ------------------------------------------------------------------
    # Extracción de campos de una publicación
    # ------------------------------------------------------------------
    def extraer_autor(self, publicacion):
        try:
            return publicacion.find_element(
                By.XPATH, './/div[@data-ad-rendering-role="profile_name"]//a'
            ).text
        except Exception:
            pass
        try:
            return publicacion.find_element(By.CSS_SELECTOR, "h3 a, h4 a, strong a").text
        except Exception:
            return ""

    def extraer_texto(self, publicacion):
        try:
            bloque = publicacion.find_element(
                By.CSS_SELECTOR, 'div[data-ad-preview="message"]'
            )
            if bloque.text:
                return bloque.text
        except Exception:
            pass
        partes = [d.text for d in publicacion.find_elements(By.CSS_SELECTOR, 'div[dir="auto"]')
                  if len(d.text) > 30]
        return max(partes, key=len) if partes else ""

    # ------------------------------------------------------------------
    # Comentarios (diálogo de la publicación)
    # ------------------------------------------------------------------
    def ordenar_por_todos_los_comentarios(self):
        """Cambia el filtro 'Más relevantes' a 'Todos los comentarios' para
        que Facebook no oculte comentarios al scrollear."""
        try:
            filtro = self.driver.find_element(
                By.XPATH,
                '//div[@role="button" and @aria-haspopup="menu"]'
                '[.//span[contains(text(), "relevantes") or contains(text(), "recientes")]]',
            )
            filtro.click()
            sleep(2)
            opcion = self.driver.find_element(
                By.XPATH,
                '//div[@role="menuitem"][.//span[contains(text(), "Todos los comentarios")]]',
            )
            opcion.click()
            sleep(3)
        except Exception:
            print("  (no se pudo cambiar el filtro de comentarios, sigo con el actual)")

    def extraer_comentarios(self):
        """Scrollea dentro del diálogo hasta cargar todos los comentarios
        y devuelve [{autor, texto}, ...]."""
        self.ordenar_por_todos_los_comentarios()

        xpath_comentario = '//div[@role="article" and starts-with(@aria-label, "Comentario de")]'
        cantidad_anterior = -1
        for _ in range(self.max_rondas_comentarios):
            comentarios = self.driver.find_elements(By.XPATH, xpath_comentario)

            # Expandir "Ver más comentarios" si aparece.
            for boton in self.driver.find_elements(
                By.XPATH,
                '//div[@role="button"][.//span[contains(text(), "Ver más comentarios")]]',
            ):
                try:
                    boton.click()
                    sleep(2)
                except Exception:
                    pass

            # Scroll dentro del diálogo: llevar el último comentario a la vista
            # hace que el contenedor cargue los siguientes.
            if comentarios:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'end'});", comentarios[-1]
                )
            sleep(2)

            if len(comentarios) == cantidad_anterior:
                break
            cantidad_anterior = len(comentarios)

        resultado = []
        for comentario in self.driver.find_elements(By.XPATH, xpath_comentario):
            try:
                autor = comentario.find_element(
                    By.XPATH, './/a[@aria-hidden="false"]//span[@dir="auto"]'
                ).text
            except Exception:
                # Respaldo: el aria-label es "Comentario de <autor> hace <tiempo>".
                etiqueta = comentario.get_attribute("aria-label") or ""
                autor = etiqueta.removeprefix("Comentario de ").split(" hace ")[0]
            try:
                texto = comentario.find_element(
                    By.XPATH, './/span[@dir="auto" and @lang]'
                ).text
            except Exception:
                partes = [d.text for d in comentario.find_elements(
                    By.CSS_SELECTOR, 'div[dir="auto"]') if d.text]
                texto = max(partes, key=len) if partes else ""
            if texto:
                resultado.append({"autor": autor, "texto": texto})
        return resultado

    def cerrar_dialogo(self):
        try:
            self.driver.find_element(
                By.XPATH, '//div[@role="button" and @aria-label="Cerrar"]'
            ).click()
            sleep(2)
        except Exception:
            webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            sleep(2)

    # ------------------------------------------------------------------
    # Recorrido de publicaciones
    # ------------------------------------------------------------------
    def extraer_publicaciones(self):
        xpath_boton = '//div[@role="button" and starts-with(@aria-label, "Comentar")]'
        total_botones = len(self.driver.find_elements(By.XPATH, xpath_boton))
        print(f"Publicaciones con botón de comentar: {total_botones}")

        for i in range(total_botones):
            # El feed se re-renderiza con cada scroll y al cerrar el diálogo
            # (virtualización), dejando obsoletas las referencias anteriores.
            # Por eso todo se vuelve a buscar en cada intento.
            exito = False
            autor = descripcion = ""
            for _ in range(50):
                botones = self.driver.find_elements(By.XPATH, xpath_boton)
                if i >= len(botones):
                    break
                boton = botones[i]
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", boton
                    )
                    sleep(2)
                    # En el feed de búsqueda cada publicación va envuelta en un
                    # div con aria-posinset (ahí role="article" son comentarios).
                    articulo = boton.find_element(
                        By.XPATH, './ancestor::div[@aria-posinset][1]'
                    )
                    autor = self.extraer_autor(articulo)
                    descripcion = self.extraer_texto(articulo)
                    if not autor:
                        etiqueta = boton.get_attribute("aria-label") or ""
                        autor = etiqueta.removeprefix("Comentar la publicación de ")
                    boton.click()
                    exito = True
                    break
                except StaleElementReferenceException:
                    sleep(2)

            if not exito:
                print(f"\n[{i + 1}/{total_botones}] Publicación omitida (el feed se re-renderizó)")
                continue

            print(f"\n[{i + 1}/{total_botones}] Autor: {autor}")
            print("Descripción:", descripcion[:120], "...")
            sleep(4)

            comentarios = self.extraer_comentarios()
            print(f"Comentarios extraídos: {len(comentarios)}")

            self.cerrar_dialogo()

            self.publicaciones.append({
                "fuente": "Facebook",
                "consulta": self.busqueda,
                "autor": autor,
                "texto": descripcion,
                "comentarios": comentarios,
            })

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
            self.buscar()
            self.scrollear_feed()
            self.extraer_publicaciones()
            self.guardar()
        finally:
            self.driver.quit()
