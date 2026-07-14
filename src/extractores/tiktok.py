"""
Scraper de TikTok con Selenium (navegador real).

Estrategia: para cada PALABRA CLAVE se abre la búsqueda
(`/search?q=...`) y para cada HASHTAG su página (`/tag/<hashtag>`); se hace
scroll y de cada tarjeta de video se extraen la descripción (alt de la
miniatura / aria-label), el autor y el enlace, hacia objetos `Registro`.

TikTok detecta bots agresivamente: con perfil persistente y sesión iniciada
(`python3 preparar_sesion.py tiktok`) el navegador real pasa como usuario
normal. Si aparece un captcha, resuélvelo en la ventana y el scraping continúa.
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

_RE_VIDEO = re.compile(r"tiktok\.com/@([\w.\-]+)/video/(\d+)")


class ExtractorTikTok(ExtractorBase):
    nombre = "TikTok"

    def extraer(self) -> list[Registro]:
        driver = crear_driver("tiktok")
        try:
            return self._scrapear(driver)
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    def _scrapear(self, driver) -> list[Registro]:
        registros: list[Registro] = []
        vistos: set[str] = set()

        consultas = (
            [("https://www.tiktok.com/search?q=" + urllib.parse.quote(t),
              f"palabra_clave:{t}") for t in config.TERMINOS_BUSQUEDA]
            + [(f"https://www.tiktok.com/tag/{urllib.parse.quote(h)}",
                f"hashtag:#{h}") for h in config.HASHTAGS]
        )

        for url, etiqueta in consultas:
            log.info("[%s] Buscando: %s", self.nombre, etiqueta)
            try:
                driver.get(url)
                WebDriverWait(driver, config.ESPERA_MAX).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'a[href*="/video/"]'))
                )
            except Exception as exc:  # noqa: BLE001
                if self._hay_captcha(driver):
                    log.warning("[%s] TikTok muestra un captcha; resuélvelo en "
                                "la ventana o inicia sesión con "
                                "preparar_sesion.py tiktok", self.nombre)
                else:
                    log.warning("[%s] Sin resultados para '%s': %s",
                                self.nombre, etiqueta, exc)
                continue

            for _ in range(config.SCROLLS_POR_CONSULTA):
                for a in driver.find_elements(By.CSS_SELECTOR,
                                              'a[href*="/video/"]'):
                    reg = self._tarjeta_a_registro(a, etiqueta)
                    if reg and reg.id_original not in vistos:
                        vistos.add(reg.id_original)
                        registros.append(reg)
                driver.execute_script("window.scrollBy(0, 2200);")
                time.sleep(config.PAUSA_SCROLL)

        return registros

    # ------------------------------------------------------------------
    def _hay_captcha(self, driver) -> bool:
        try:
            return bool(driver.find_elements(
                By.CSS_SELECTOR, '[id*="captcha"], [class*="captcha"]'))
        except Exception:  # noqa: BLE001
            return False

    def _tarjeta_a_registro(self, enlace, etiqueta: str) -> Registro | None:
        href = enlace.get_attribute("href") or ""
        m = _RE_VIDEO.search(href)
        if not m:
            return None
        autor, id_video = m.group(1), m.group(2)

        texto = self._descripcion(enlace)
        if not texto:
            return None

        return Registro(
            fuente=self.nombre,
            consulta=etiqueta,
            texto=limpiar_texto(texto, quitar_urls=True),
            id_original=id_video,
            autor=f"@{autor}",
            url=f"https://www.tiktok.com/@{autor}/video/{id_video}",
            metricas=self._metricas(enlace),
        )

    def _descripcion(self, enlace) -> str:
        # 1) alt de la miniatura: TikTok pone ahí la descripción del video.
        try:
            for img in enlace.find_elements(By.TAG_NAME, "img"):
                alt = (img.get_attribute("alt") or "").strip()
                if len(alt) > 15:
                    return alt
        except Exception:  # noqa: BLE001
            pass
        # 2) aria-label del propio enlace o su título.
        for attr in ("aria-label", "title"):
            try:
                val = (enlace.get_attribute(attr) or "").strip()
                if len(val) > 15:
                    return val
            except Exception:  # noqa: BLE001
                pass
        # 3) texto visible de la tarjeta contenedora.
        try:
            contenedor = enlace.find_element(By.XPATH, "./ancestor::div[2]")
            t = (contenedor.text or "").strip()
            if len(t) > 15:
                return t.split("\n")[0]
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _metricas(self, enlace) -> dict:
        """Vistas mostradas sobre la miniatura (ej. '1.2M')."""
        metr = {"vistas": 0}
        try:
            marcador = enlace.find_elements(
                By.CSS_SELECTOR, 'strong[data-e2e="video-views"], strong')
            for s in marcador:
                valor = self._numero_abreviado(s.text)
                if valor:
                    metr["vistas"] = valor
                    break
        except Exception:  # noqa: BLE001
            pass
        return metr

    def _numero_abreviado(self, texto: str) -> int:
        """Convierte '1.2M', '15.3K', '987' a entero."""
        t = (texto or "").strip().upper().replace(",", ".")
        m = re.match(r"^(\d+(?:\.\d+)?)([KM]?)$", t)
        if not m:
            return 0
        valor = float(m.group(1))
        factor = {"K": 1_000, "M": 1_000_000}.get(m.group(2), 1)
        return int(valor * factor)
