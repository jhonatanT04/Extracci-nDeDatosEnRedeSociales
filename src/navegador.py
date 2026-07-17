"""Fábrica de Chrome+Selenium con perfil por red y ajustes anti-detección.

Para reducir los captchas de "confirma que eres humano", cada red usa una
COPIA de tu perfil real de Chrome (con sus cookies, sesión e historial), lo
que hace que el navegador automatizado parezca un usuario ya conocido. Se usa
una copia por red (no el perfil real directo) porque Chrome bloquea una carpeta
de perfil mientras la usa, y Facebook y TikTok corren en paralelo: cada uno
necesita su propia carpeta.

La copia se hace UNA sola vez (la primera corrida). Conviene cerrar tu Chrome
antes de esa primera copia para que las cookies se copien sin bloqueos; luego
puedes volver a abrirlo con normalidad.
"""

import os
import shutil
import sys

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Carpeta donde viven las copias de perfil por red (junto a la raíz del proyecto).
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_PERFILES = os.path.join(_RAIZ, ".perfil_navegador")

# Archivos de caché/bloqueo que no hace falta copiar (aligeran mucho la copia).
_IGNORAR = shutil.ignore_patterns(
    "Singleton*", "Cache", "Code Cache", "GPUCache", "DawnCache",
    "GrShaderCache", "ShaderCache", "Service Worker", "*.lock", "lockfile",
)


def _perfil_chrome_real():
    """Ruta del directorio de datos de Chrome del usuario según el SO."""
    if sys.platform.startswith("linux"):
        return os.path.expanduser("~/.config/google-chrome")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("LOCALAPPDATA", ""),
                            "Google", "Chrome", "User Data")
    return ""


def _asegurar_copia(subperfil):
    """Devuelve la carpeta de perfil de esta red, copiando el perfil real de
    Chrome la primera vez."""
    destino = os.path.join(BASE_PERFILES, subperfil)
    if os.path.isdir(os.path.join(destino, "Default")):
        return destino  # ya se copió antes

    real = _perfil_chrome_real()
    origen_default = os.path.join(real, "Default")
    os.makedirs(destino, exist_ok=True)

    if os.path.isdir(origen_default):
        print(f"[{subperfil}] Copiando tu perfil real de Chrome "
              f"(solo la primera vez, cierra Chrome si es posible)...")
        shutil.copytree(origen_default, os.path.join(destino, "Default"),
                        ignore=_IGNORAR, dirs_exist_ok=True)
        # "Local State" guarda la clave para descifrar las cookies en algunos SO.
        estado = os.path.join(real, "Local State")
        if os.path.isfile(estado):
            shutil.copy2(estado, os.path.join(destino, "Local State"))
    else:
        print(f"[{subperfil}] No se encontró el perfil real de Chrome en "
              f"'{real}'. Se usará un perfil nuevo (tendrás que iniciar sesión).")
    return destino


def crear_driver(subperfil):
    """Crea un Chrome con la copia de perfil de la red 'subperfil' y ajustes
    anti-detección."""
    destino = _asegurar_copia(subperfil)

    opciones = webdriver.ChromeOptions()
    opciones.add_argument(f"--user-data-dir={destino}")
    opciones.add_argument("--profile-directory=Default")
    opciones.add_argument("--window-size=1920,1080")
    # Ocultar señales de automatización.
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    servicio = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=servicio, options=opciones)

    # Que navigator.webdriver no delate a Selenium.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', "
                   "{get: () => undefined});"},
    )
    return driver
