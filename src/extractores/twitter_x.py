"""
Scraper de X (Twitter) con Selenium (navegador real).

Estrategia: para cada PALABRA CLAVE y HASHTAG se abre la búsqueda en vivo
(`/search?q=...&f=live`), se hace scroll y se extraen los tweets visibles
(texto, autor, fecha, métricas y enlace) hacia objetos `Registro`.

Requiere sesión iniciada: ejecuta antes `python3 preparar_sesion.py x`.
La sesión se reutiliza desde el perfil persistente (ver src/navegador.py).
"""

from __future__ import annotations

import re
import time
import urllib.parse

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .. import config
from ..modelos import Registro
from ..navegador import crear_driver
from ..utilidades import limpiar_texto, log
from .base import ExtractorBase


class ExtractorTwitterX(ExtractorBase):
    nombre = "X-Twitter"

    def extraer(self) -> list[Registro]:
        driver = crear_driver("x")
        try:
            return self._scrapear(driver)
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    def _scrapear(self, driver) -> list[Registro]:
        registros: list[Registro] = []
        vistos: set[str] = set()

        consultas = (
            [(t, f"palabra_clave:{t}") for t in config.TERMINOS_BUSQUEDA]
            + [(f"#{h}", f"hashtag:#{h}") for h in config.HASHTAGS]
        )

        # Verifica la sesión una sola vez con la primera consulta.
        if not self._sesion_iniciada(driver):
            log.warning("[%s] No hay sesión iniciada en X. Ejecuta primero: "
                        "python3 preparar_sesion.py x", self.nombre)
            return []

        for texto_consulta, etiqueta in consultas:
            url = ("https://x.com/search?q="
                   + urllib.parse.quote(texto_consulta)
                   + "&src=typed_query&f=live")
            log.info("[%s] Buscando: %s", self.nombre, texto_consulta)
            try:
                driver.get(url)
                self._esperar_tweets(driver)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] Sin resultados para '%s': %s",
                            self.nombre, texto_consulta, exc)
                continue

            self._recorrer_scroll(driver, etiqueta, registros, vistos)

        return registros

    # ------------------------------------------------------------------
    def _sesion_iniciada(self, driver) -> bool:
        driver.get("https://x.com/home")
        try:
            WebDriverWait(driver, config.ESPERA_MAX).until(
                lambda d: "/login" not in d.current_url
                and (d.find_elements(By.CSS_SELECTOR, 'a[data-testid="AppTabBar_Home_Link"]')
                     or d.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            return "/login" not in driver.current_url and "/i/flow/login" not in driver.current_url
        except Exception:  # noqa: BLE001
            return False

    def _esperar_tweets(self, driver) -> None:
        WebDriverWait(driver, config.ESPERA_MAX).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
        )

    def _recorrer_scroll(self, driver, etiqueta, registros, vistos) -> None:
        for _ in range(config.SCROLLS_POR_CONSULTA):
            articulos = driver.find_elements(By.CSS_SELECTOR,
                                             'article[data-testid="tweet"]')
            for art in articulos:
                reg = self._articulo_a_registro(art, etiqueta)
                if reg and reg.url not in vistos:
                    vistos.add(reg.url)
                    registros.append(reg)
            driver.execute_script("window.scrollBy(0, 2200);")
            time.sleep(config.PAUSA_SCROLL)

    # ------------------------------------------------------------------
    def _articulo_a_registro(self, art, etiqueta: str) -> Registro | None:
        texto = self._texto_seguro(art, 'div[data-testid="tweetText"]')
        if not texto:
            return None

        url = self._enlace_tweet(art)
        id_original = ""
        if url:
            m = re.search(r"/status/(\d+)", url)
            id_original = m.group(1) if m else ""

        autor = self._autor(art)
        fecha = self._atributo_seguro(art, "time", "datetime")
        metricas = self._metricas(art)

        return Registro(
            fuente=self.nombre,
            consulta=etiqueta,
            texto=limpiar_texto(texto, quitar_urls=True),
            id_original=id_original,
            autor=autor,
            fecha_publicacion=fecha,
            url=url,
            metricas=metricas,
        )

    # -- helpers de extracción defensivos ------------------------------
    def _texto_seguro(self, elem, css: str) -> str:
        try:
            return elem.find_element(By.CSS_SELECTOR, css).text
        except Exception:  # noqa: BLE001
            return ""

    def _atributo_seguro(self, elem, css: str, attr: str) -> str:
        try:
            return elem.find_element(By.CSS_SELECTOR, css).get_attribute(attr) or ""
        except Exception:  # noqa: BLE001
            return ""

    def _enlace_tweet(self, art) -> str:
        try:
            for a in art.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]'):
                href = a.get_attribute("href") or ""
                if "/status/" in href and "/analytics" not in href:
                    return href.split("?")[0]
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _autor(self, art) -> str:
        try:
            bloque = art.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"]')
            for span in bloque.find_elements(By.TAG_NAME, "span"):
                t = (span.text or "").strip()
                if t.startswith("@"):
                    return t
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _metricas(self, art) -> dict:
        """Extrae likes/respuestas/retweets/vistas del aria-label del grupo."""
        metr = {"respuestas": 0, "retweets": 0, "likes": 0, "vistas": 0}
        try:
            grupo = art.find_element(By.CSS_SELECTOR, 'div[role="group"]')
            etiqueta = (grupo.get_attribute("aria-label") or "").lower()
        except Exception:  # noqa: BLE001
            return metr
        mapa = {
            "respuestas": r"(\d[\d.,]*)\s+(?:repl|respuesta)",
            "retweets": r"(\d[\d.,]*)\s+(?:repost|retweet)",
            "likes": r"(\d[\d.,]*)\s+(?:like|me gusta)",
            "vistas": r"(\d[\d.,]*)\s+(?:view|visualizaci)",
        }
        for clave, patron in mapa.items():
            m = re.search(patron, etiqueta)
            if m:
                metr[clave] = int(m.group(1).replace(".", "").replace(",", ""))
        return metr
