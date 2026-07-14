"""
Scraper de Facebook con Selenium (navegador real).

Estrategia: para cada PALABRA CLAVE y HASHTAG se abre la búsqueda de
publicaciones (`/search/posts?q=...`), se hace scroll y se extraen las
publicaciones visibles (texto, autor, enlace) hacia objetos `Registro`.

Facebook ofusca su HTML (clases generadas), por lo que se usan únicamente
selectores semánticos estables (role="article", dir="auto", href) y toda la
extracción es defensiva: si un campo no aparece, se guarda vacío.

Requiere sesión iniciada: ejecuta antes `python3 preparar_sesion.py facebook`.
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

# Enlaces que identifican una publicación concreta dentro de un artículo.
_HREF_POST = ('a[href*="/posts/"], a[href*="story_fbid="], '
              'a[href*="/videos/"], a[href*="/reel/"], a[href*="/watch/"]')


class ExtractorFacebook(ExtractorBase):
    nombre = "Facebook"

    def extraer(self) -> list[Registro]:
        driver = crear_driver("facebook")
        try:
            return self._scrapear(driver)
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    def _scrapear(self, driver) -> list[Registro]:
        if not self._sesion_iniciada(driver):
            log.warning("[%s] No hay sesión iniciada en Facebook. Ejecuta "
                        "primero: python3 preparar_sesion.py facebook",
                        self.nombre)
            return []

        registros: list[Registro] = []
        vistos: set[str] = set()

        consultas = (
            [(t, f"palabra_clave:{t}") for t in config.TERMINOS_BUSQUEDA]
            + [(f"#{h}", f"hashtag:#{h}") for h in config.HASHTAGS]
        )
        for texto_consulta, etiqueta in consultas:
            url = ("https://www.facebook.com/search/posts?q="
                   + urllib.parse.quote(texto_consulta))
            log.info("[%s] Buscando: %s", self.nombre, texto_consulta)
            try:
                driver.get(url)
                WebDriverWait(driver, config.ESPERA_MAX).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'div[role="article"], div[role="feed"]'))
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] Sin resultados para '%s': %s",
                            self.nombre, texto_consulta, exc)
                continue

            for _ in range(config.SCROLLS_POR_CONSULTA):
                for art in driver.find_elements(By.CSS_SELECTOR,
                                                'div[role="article"]'):
                    reg = self._articulo_a_registro(art, etiqueta)
                    if reg and reg.id_unico() not in vistos:
                        vistos.add(reg.id_unico())
                        registros.append(reg)
                driver.execute_script("window.scrollBy(0, 2200);")
                time.sleep(config.PAUSA_SCROLL)

        return registros

    # ------------------------------------------------------------------
    def _sesion_iniciada(self, driver) -> bool:
        driver.get("https://www.facebook.com/")
        try:
            WebDriverWait(driver, config.ESPERA_MAX).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, 'input[name="email"]')
                or d.find_elements(By.CSS_SELECTOR, 'div[role="feed"]')
                or d.find_elements(By.CSS_SELECTOR, 'div[role="main"]')
            )
        except Exception:  # noqa: BLE001
            return False
        # Si sigue mostrando el formulario de login, no hay sesión.
        return not driver.find_elements(By.CSS_SELECTOR, 'input[name="email"]')

    # ------------------------------------------------------------------
    def _articulo_a_registro(self, art, etiqueta: str) -> Registro | None:
        texto = self._texto_publicacion(art)
        if not texto or len(texto) < 15:
            return None

        url = self._enlace_post(art)
        autor = self._autor(art)
        return Registro(
            fuente=self.nombre,
            consulta=etiqueta,
            texto=limpiar_texto(texto, quitar_urls=True),
            id_original=self._id_desde_url(url),
            autor=autor,
            url=url,
            metricas=self._metricas(art),
        )

    def _texto_publicacion(self, art) -> str:
        # El mensaje del post suele estar marcado con data-ad-preview.
        try:
            bloques = art.find_elements(
                By.CSS_SELECTOR, 'div[data-ad-preview="message"]')
            if bloques:
                return " ".join(b.text for b in bloques if b.text)
        except Exception:  # noqa: BLE001
            pass
        # Alternativa: párrafos de texto del artículo (dir="auto").
        try:
            partes = [d.text for d in art.find_elements(
                By.CSS_SELECTOR, 'div[dir="auto"]') if d.text]
            # Se descartan fragmentos muy cortos (botones, "Me gusta", etc.).
            partes = [p for p in partes if len(p) > 30]
            return max(partes, key=len) if partes else ""
        except Exception:  # noqa: BLE001
            return ""

    def _autor(self, art) -> str:
        try:
            enlace = art.find_element(By.CSS_SELECTOR, "h3 a, h4 a, strong a")
            return (enlace.text or "").strip()
        except Exception:  # noqa: BLE001
            pass
        try:
            return (art.find_element(By.TAG_NAME, "strong").text or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def _enlace_post(self, art) -> str:
        try:
            for a in art.find_elements(By.CSS_SELECTOR, _HREF_POST):
                href = a.get_attribute("href") or ""
                if href:
                    return href.split("?")[0]
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _id_desde_url(self, url: str) -> str:
        m = re.search(r"(?:posts|videos|reel)/(\w+)|story_fbid=(\w+)", url)
        if not m:
            return ""
        return m.group(1) or m.group(2) or ""

    def _metricas(self, art) -> dict:
        """Reacciones/comentarios best-effort desde los aria-label visibles."""
        metr = {"reacciones": 0, "comentarios": 0, "compartidos": 0}
        try:
            texto = " ".join(
                (e.get_attribute("aria-label") or "")
                for e in art.find_elements(By.CSS_SELECTOR, "[aria-label]")
            ).lower()
        except Exception:  # noqa: BLE001
            return metr
        mapa = {
            "reacciones": r"(\d[\d.,]*)\s*(?:reaccion|reaction|me gusta|like)",
            "comentarios": r"(\d[\d.,]*)\s*(?:comentario|comment)",
            "compartidos": r"(\d[\d.,]*)\s*(?:vez compartido|veces compartido|share)",
        }
        for clave, patron in mapa.items():
            m = re.search(patron, texto)
            if m:
                metr[clave] = int(m.group(1).replace(".", "").replace(",", ""))
        return metr
