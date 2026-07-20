import json
import os
from time import sleep

from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from src.navegador import crear_driver as crear_navegador

load_dotenv()


class ScraperFacebook:
    """Extrae publicaciones y comentarios de la búsqueda de Facebook
    usando Selenium sobre un Chrome real."""

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        scrolls_feed=5,
        max_publicaciones=20,
        max_rondas_comentarios=5,
        archivo_salida="datos/facebook_publicaciones.json",
        confirmar_login=None,
    ):
        self.busqueda = busqueda
        self.scrolls_feed = scrolls_feed
        self.max_publicaciones = max_publicaciones
        self.max_rondas_comentarios = max_rondas_comentarios
        self.archivo_salida = archivo_salida
        self.username = os.getenv("FACEBOOK_USER", "")
        self.password = os.getenv("FACEBOOK_PASSWORD", "")
        self.driver = None
        self.gestor = None
        self.publicaciones = []
        # Callable sin argumentos que bloquea hasta confirmar el login. Por
        # defecto usa input() en la terminal (CLI); la app web pasa uno que
        # espera un threading.Event liberado desde el navegador.
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
        self.driver = crear_navegador("facebook")

    def iniciar_sesion(self):
        self.driver.get("https://www.facebook.com/")

        if self.confirmar_login is not None:
            self.confirmar_login()
        else:
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
            self.driver.execute_script("arguments[0].click();", filtro)
            sleep(2)
            opcion = self.driver.find_element(
                By.XPATH,
                '//div[@role="menuitem"][.//span[contains(text(), "Todos los comentarios")]]',
            )
            self.driver.execute_script("arguments[0].click();", opcion)
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
                    self.driver.execute_script("arguments[0].click();", boton)
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
            cerrar = self.driver.find_element(
                By.XPATH, '//div[@role="button" and @aria-label="Cerrar"]'
            )
            self.driver.execute_script("arguments[0].click();", cerrar)
            sleep(2)
        except Exception:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            sleep(2)

    # ------------------------------------------------------------------
    # Recorrido de publicaciones
    # ------------------------------------------------------------------
    def extraer_publicaciones(self):
        """Recorre el feed de forma incremental: procesa cada publicación con
        botón 'Comentar' que no se haya visto, y cuando no quedan nuevas a la
        vista, scrollea para cargar más. Así se cruzan los bloques de
        sugerencias ('Páginas', 'Personas', etc.) —que no tienen botón de
        comentar— y se sigue guardando las publicaciones que vienen después.
        La deduplicación es por autor+descripción porque el feed se re-renderiza
        (virtualización) y los índices anteriores quedan obsoletos."""
        xpath_boton = '//div[@role="button" and starts-with(@aria-label, "Comentar")]'
        procesados = set()
        scrolls_sin_nuevos = 0

        while (scrolls_sin_nuevos < self.scrolls_feed
               and len(self.publicaciones) < self.max_publicaciones):
            self._checkpoint()
            objetivo = None
            autor = descripcion = clave = ""
            for boton in self.driver.find_elements(By.XPATH, xpath_boton):
                try:
                    articulo = boton.find_element(
                        By.XPATH, './ancestor::div[@aria-posinset][1]'
                    )
                    autor = self.extraer_autor(articulo)
                    descripcion = self.extraer_texto(articulo)
                    if not autor:
                        etiqueta = boton.get_attribute("aria-label") or ""
                        autor = etiqueta.removeprefix("Comentar la publicación de ")
                    clave = f"{autor}|{descripcion}"
                    if clave in procesados:
                        continue
                    objetivo = boton
                    break
                except StaleElementReferenceException:
                    continue

            # No hay publicaciones nuevas visibles: scrollear para cargar más.
            if objetivo is None:
                self.driver.execute_script("window.scrollBy(0, 2200);")
                sleep(3)
                scrolls_sin_nuevos += 1
                continue
            scrolls_sin_nuevos = 0
            procesados.add(clave)

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", objetivo
                )
                sleep(2)
                # Facebook superpone una capa transparente (role="none",
                # data-visualcompletion="ignore") sobre el botón, que intercepta
                # el .click() nativo; el clic por JavaScript se dispara directo
                # sobre el elemento y sí abre los comentarios.
                self.driver.execute_script("arguments[0].click();", objetivo)
            except StaleElementReferenceException:
                continue

            print(f"\n[{len(self.publicaciones) + 1}] Autor: {autor}")
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

        print(f"\nTotal de publicaciones extraídas: {len(self.publicaciones)}")

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
                gestor.con_login(self.iniciar_sesion, "Facebook")
            else:
                self.iniciar_sesion()
            self._checkpoint()
            self.buscar()
            self.extraer_publicaciones()
            self.guardar()
        finally:
            self.driver.quit()
