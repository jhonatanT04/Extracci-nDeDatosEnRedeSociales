"""
Fábrica del navegador Selenium (Google Chrome).

- Perfil PERSISTENTE por red (`.perfil_navegador/<red>`): conserva la sesión
  iniciada entre corridas, así el login manual se hace una sola vez, y permite
  correr varios navegadores EN PARALELO sin que se pisen.
- Opciones "stealth" para reducir la detección de automatización.
- Selenium 4 descarga el chromedriver automáticamente (Selenium Manager).
"""

from __future__ import annotations

import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from . import config


def ruta_perfil(subperfil: str) -> str:
    """Ruta absoluta del perfil de Chrome para una red concreta."""
    ruta = os.path.abspath(os.path.join(config.PERFIL_NAVEGADOR, subperfil))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def crear_driver(subperfil: str, headless: bool | None = None) -> webdriver.Chrome:
    """Crea un driver de Chrome con perfil persistente y ajustes anti-detección."""
    opciones = Options()
    opciones.add_argument(f"--user-data-dir={ruta_perfil(subperfil)}")
    opciones.add_argument("--no-first-run")
    opciones.add_argument("--no-default-browser-check")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--window-size=1300,950")
    opciones.add_argument("--lang=es-EC")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    if headless is None:
        headless = config.HEADLESS or os.environ.get("HEADLESS", "0") == "1"
    if headless:
        opciones.add_argument("--headless=new")
        opciones.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=opciones)
    driver.set_page_load_timeout(60)
    # Oculta navigator.webdriver antes de que cargue cualquier página.
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', "
                       "{get: () => undefined});"},
        )
    except Exception:  # noqa: BLE001 - no crítico si el navegador no soporta CDP
        pass
    return driver
