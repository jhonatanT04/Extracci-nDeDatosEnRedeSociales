"""Junta las extracciones de todas las fuentes en un solo dataset JSON
con el mismo esquema que datos/dataset_prueba.json: cada publicación y
cada comentario se vuelve un registro plano y trazable (fuente, consulta,
texto, autor, métricas, id_unico)."""

import hashlib
import json
import os
from datetime import datetime, timezone

CONTEXTO = (
    "El Gobierno del Ecuador realizó una convocatoria internacional para "
    "seleccionar el diseño arquitectónico del nuevo Museo Nacional del "
    "Ecuador. El diseño ganador, 'Ecos del Sol', recibió numerosas críticas "
    "en redes sociales."
)
PROBLEMATICA = (
    "¿Cuál es la percepción de los usuarios de redes sociales sobre el "
    "diseño ganador ('Ecos del Sol') del nuevo Museo Nacional del Ecuador?"
)
OBJETIVO = (
    "Analizar las opiniones publicadas en redes sociales para identificar "
    "el sentimiento predominante y los principales temas de discusión."
)

ARCHIVOS_FUENTES = [
    "datos/facebook_publicaciones.json",
    "datos/tiktok_publicaciones.json",
    "datos/youtube_publicaciones.json",
    "datos/reddit_publicaciones.json",
]


def _id_unico(fuente, autor, texto, url):
    base = f"{fuente}|{autor}|{url}|{texto}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:16]


def _registro(fuente, consulta, texto, autor, url="", fecha="", metricas=None):
    ahora = datetime.now(timezone.utc).isoformat()
    id_unico = _id_unico(fuente, autor, texto, url)
    return {
        "fuente": fuente,
        "consulta": consulta,
        "texto": texto,
        "id_original": id_unico,
        "autor": autor,
        "fecha_publicacion": fecha,
        "url": url,
        "idioma": "es",
        "metricas": metricas or {"likes": 0, "comentarios": 0, "compartidos": 0},
        "extraido_en": ahora,
        "id_unico": id_unico,
    }


def _registros_de_publicacion(pub):
    """Convierte una publicación (y sus comentarios) en registros planos."""
    registros = []
    comentarios = pub.get("comentarios") or []

    metricas = {"likes": 0, "comentarios": len(comentarios), "compartidos": 0}
    if pub.get("vistas"):
        metricas["vistas"] = pub["vistas"]

    registros.append(_registro(
        fuente=pub.get("fuente", ""),
        consulta=pub.get("consulta", ""),
        texto=pub.get("texto", ""),
        autor=pub.get("autor", ""),
        url=pub.get("url", ""),
        fecha=pub.get("fecha", ""),
        metricas=metricas,
    ))

    for com in comentarios:
        registros.append(_registro(
            fuente=pub.get("fuente", ""),
            consulta=pub.get("consulta", ""),
            texto=com.get("texto", ""),
            autor=com.get("autor", ""),
            url=pub.get("url", ""),
            metricas={"likes": com.get("likes", 0), "comentarios": 0,
                      "compartidos": 0},
        ))
    return registros


def consolidar(archivos=None, carpeta_salida="datos"):
    registros = []
    vistos = set()

    for archivo in archivos or ARCHIVOS_FUENTES:
        if not os.path.exists(archivo):
            print(f"(no existe {archivo}, se omite)")
            continue
        with open(archivo, encoding="utf-8") as f:
            publicaciones = json.load(f)
        for pub in publicaciones:
            for reg in _registros_de_publicacion(pub):
                if not reg["texto"] or reg["id_unico"] in vistos:
                    continue
                vistos.add(reg["id_unico"])
                registros.append(reg)

    por_fuente = {}
    for reg in registros:
        por_fuente[reg["fuente"]] = por_fuente.get(reg["fuente"], 0) + 1

    dataset = {
        "contexto": CONTEXTO,
        "problematica": PROBLEMATICA,
        "objetivo": OBJETIVO,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "total_registros": len(registros),
        "registros_por_fuente": por_fuente,
        "registros": registros,
    }

    os.makedirs(carpeta_salida, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(carpeta_salida, f"dataset_{marca}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\nDataset consolidado: {ruta}")
    print(f"Total de registros: {len(registros)}  {por_fuente}")
    return ruta


if __name__ == "__main__":
    consolidar()
