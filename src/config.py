"""
Configuración central del proyecto.

Define la PROBLEMÁTICA, el CONTEXTO y la ESTRATEGIA DE BÚSQUEDA (palabras clave
y hashtags) usadas para recolectar las opiniones. Centralizar esto garantiza la
TRAZABILIDAD: cada registro queda asociado a la red y a la consulta que lo
originó.

Modelo de extracción
--------------------
Facebook, X (Twitter) y TikTok bloquean las APIs/librerías de scraping
gratuitas (ver la sección "Estrategia de extracción" del README). Por eso las
tres redes se scrapean con SELENIUM sobre Google Chrome real y una sesión
iniciada por el usuario (`preparar_sesion.py <red>`). El controlador ejecuta
los tres scrapers EN PARALELO (un navegador por red).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1) CONTEXTO Y PROBLEMÁTICA (rúbrica: "Definición clara de la problemática")
# ---------------------------------------------------------------------------
CONTEXTO = (
    "El Gobierno del Ecuador realizó una convocatoria internacional para "
    "seleccionar el diseño arquitectónico del nuevo Museo Nacional del Ecuador, "
    "un proyecto destinado a albergar más de 100.000 bienes patrimoniales del "
    "país. El diseño ganador, denominado 'Ecos del Sol', recibió numerosas "
    "críticas en redes sociales por parte de ciudadanos, arquitectos y artistas, "
    "quienes cuestionaron aspectos estéticos, culturales y de representatividad "
    "nacional. La controversia fue tal que el Gobierno anunció que dejaría sin "
    "efecto la propuesta ganadora y volvería a convocar a los finalistas para "
    "seleccionar un nuevo diseño."
)

PROBLEMATICA = (
    "¿Cuál es la percepción de los usuarios de redes sociales sobre el diseño "
    "ganador ('Ecos del Sol') del nuevo Museo Nacional del Ecuador, y cuáles son "
    "los principales argumentos a favor y en contra expresados en las "
    "plataformas digitales?"
)

OBJETIVO = (
    "Analizar las opiniones publicadas en redes sociales respecto al diseño "
    "ganador del nuevo Museo Nacional del Ecuador para identificar el sentimiento "
    "predominante y los principales temas de discusión."
)

# ---------------------------------------------------------------------------
# 2) ESTRATEGIA DE BÚSQUEDA (rúbrica: "estrategia de búsqueda")
# ---------------------------------------------------------------------------
# Frases usadas para localizar las publicaciones al recolectarlas.
TERMINOS_BUSQUEDA = [
    "Ecos del Sol museo",
    "nuevo Museo Nacional del Ecuador",
    "Museo Nacional Ecuador diseño",
    "diseño Museo Nacional Ecuador",
]

# Hashtags usados en las tres redes.
HASHTAGS = [
    "EcosDelSol",
    "MuseoNacionalEcuador",
    "MuseoNacionalDelEcuador",
    "NuevoMuseoNacional",
]

# ---------------------------------------------------------------------------
# 3) SCRAPING CON SELENIUM (navegador real)
# ---------------------------------------------------------------------------
# Carpeta base de perfiles de Chrome. Cada red usa un subperfil propio para
# poder correr varios navegadores EN PARALELO sin conflicto y conservar la
# sesión iniciada entre corridas (login manual la primera vez).
PERFIL_NAVEGADOR = ".perfil_navegador"

# Ejecutar sin ventana. Por defecto False: las redes detectan el modo headless,
# y además se necesita ver el navegador para el login manual. Se puede forzar
# con la variable de entorno HEADLESS=1 (útil sólo para pruebas).
HEADLESS = False

# Nº de desplazamientos (scroll) por cada consulta para cargar más resultados.
SCROLLS_POR_CONSULTA = 6

# Pausa (segundos) tras cada scroll para que carguen los resultados.
PAUSA_SCROLL = 2.5

# Espera máxima (segundos) a que aparezcan elementos en la página.
ESPERA_MAX = 20

# ---------------------------------------------------------------------------
# 4) SALIDA
# ---------------------------------------------------------------------------
DIR_DATOS = "datos"
DIR_EVIDENCIAS = "evidencias"
