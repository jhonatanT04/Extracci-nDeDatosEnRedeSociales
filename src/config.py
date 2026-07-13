"""
Configuración central del proyecto.

Define la PROBLEMÁTICA, el CONTEXTO y la ESTRATEGIA DE BÚSQUEDA (palabras clave
y hashtags) usadas para recolectar las opiniones. Centralizar esto garantiza la
TRAZABILIDAD: cada registro queda asociado a la red y a la consulta que lo
originó.

Modelo de extracción
--------------------
Facebook, X (Twitter) y TikTok bloquean el scraping automático gratuito (ver la
sección "Estrategia de extracción" del README). Por eso la recolección de las
publicaciones/comentarios reales se hace de forma MANUAL y se vuelca a un
archivo CSV por cada red (carpeta `datos_manuales/`). El sistema LEE, LIMPIA,
NORMALIZA y ALMACENA esos datos de las tres redes EN PARALELO.
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
# 3) FUENTES: una red -> un archivo CSV de recolección manual
# ---------------------------------------------------------------------------
DIR_MANUAL = "datos_manuales"

ARCHIVOS_FUENTE = {
    "Facebook": "facebook.csv",
    "X-Twitter": "x_twitter.csv",
    "TikTok": "tiktok.csv",
}

# Consulta por defecto si el usuario no especifica en el CSV de dónde salió el
# registro (mantiene la trazabilidad mínima).
CONSULTA_POR_DEFECTO = "recoleccion_manual"

# ---------------------------------------------------------------------------
# 4) SALIDA
# ---------------------------------------------------------------------------
DIR_DATOS = "datos"
DIR_EVIDENCIAS = "evidencias"
