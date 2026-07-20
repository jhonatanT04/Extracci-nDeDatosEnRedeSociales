#!/usr/bin/env python3
"""
Aplicación web del Proyecto Final — Computación Paralela (UPS).

Backend único que integra de punta a punta las prácticas 6 y 7: recibe una
consulta de búsqueda desde el navegador, dispara la extracción concurrente
de las 4 redes sociales (Facebook, TikTok, YouTube, Reddit) usando hilos,
clasifica el sentimiento de cada opinión en paralelo con un LLM (Groq u
OpenAI), genera una interpretación narrativa (storytelling) de los
resultados y expone todo mediante una API HTTP + dashboard estático.

Uso:
    python3 webapp/server.py
    (o)  uvicorn webapp.server:app --reload

Requiere las claves de API relevantes en el .env de la raíz (ver
.env.example): GROQ_API_KEY u OPENAI_API_KEY, YOUTUBE_API_KEY,
REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET. Facebook y TikTok usan el perfil
real de Chrome del usuario (ver src/navegador.py); solo piden login manual
la primera vez.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRACTICA7_DIR = os.path.join(PROJECT_ROOT, "practica7")
DIR_DATOS_RAIZ = os.path.join(PROJECT_ROOT, "datos")
DIR_DATOS_P7 = os.path.join(PRACTICA7_DIR, "datos")
DIR_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PRACTICA7_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.controlador import ejecutar_paralelo
from src.scraper_facebook import ScraperFacebook
from src.scraper_reddit import ScraperReddit
from src.scraper_tiktok import ScraperTikTok
from src.scraper_youtube import ScraperYouTube

from storytelling import generar_storytelling

FUENTES_DISPONIBLES = ["Facebook", "TikTok", "YouTube", "Reddit"]
FUENTES_CON_LOGIN_MANUAL = {"Facebook", "TikTok"}

app = FastAPI(title="Análisis Paralelo de Redes Sociales — Proyecto Final")

# job_id -> dict con el estado del pipeline (ver `_nuevo_job`)
jobs: dict[str, dict] = {}
# f"{job_id}:{fuente}" -> threading.Event, liberado cuando el usuario
# confirma en la web que ya inició sesión en esa red.
login_events: dict[str, threading.Event] = {}


# ---------------------------------------------------------------------
# Utilidades de estado del job
# ---------------------------------------------------------------------
def _log(job: dict, mensaje: str) -> None:
    job["eventos"].append({
        "ts": datetime.now().strftime("%H:%M:%S"),
        "mensaje": mensaje,
    })
    print(f"[job {job['id'][:8]}] {mensaje}")


def _nuevo_job(consulta: str, fuentes: list[str], proveedor: str) -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "consulta": consulta,
        "fuentes": fuentes,
        "proveedor": proveedor,
        "estado": "en_cola",
        "login_pendiente": None,
        "eventos": [],
        "resultado": None,
        "error": None,
        "creado_en": datetime.now().isoformat(),
    }
    jobs[job_id] = job
    for fuente in fuentes:
        if fuente in FUENTES_CON_LOGIN_MANUAL:
            login_events[f"{job_id}:{fuente}"] = threading.Event()
    return job


def _confirmar_login_callback(job: dict, fuente: str):
    """Devuelve un callable sin argumentos que el scraper llama en vez de
    input(): bloquea hasta que el usuario confirme el login desde la web."""
    def _esperar():
        job["login_pendiente"] = fuente
        _log(job, f"Esperando confirmación de login en {fuente} desde la interfaz web...")
        login_events[f"{job['id']}:{fuente}"].wait()
        job["login_pendiente"] = None
        _log(job, f"Login de {fuente} confirmado. Continuando extracción.")
    return _esperar


def _construir_scrapers(job: dict) -> list:
    scrapers = []
    if "Facebook" in job["fuentes"]:
        scrapers.append(ScraperFacebook(
            busqueda=job["consulta"],
            confirmar_login=_confirmar_login_callback(job, "Facebook"),
        ))
    if "TikTok" in job["fuentes"]:
        scrapers.append(ScraperTikTok(
            busqueda=job["consulta"],
            confirmar_login=_confirmar_login_callback(job, "TikTok"),
        ))
    if "YouTube" in job["fuentes"]:
        scrapers.append(ScraperYouTube(busqueda=job["consulta"]))
    if "Reddit" in job["fuentes"]:
        scrapers.append(ScraperReddit(busqueda=job["consulta"]))
    return scrapers


# ---------------------------------------------------------------------
# Pipeline completo: extracción concurrente -> clasificación paralela ->
# storytelling. Corre en un hilo aparte para no bloquear el servidor.
# ---------------------------------------------------------------------
def _ejecutar_pipeline(job_id: str) -> None:
    job = jobs[job_id]
    try:
        job["estado"] = "extrayendo"
        _log(job, f"Extracción paralela iniciada para «{job['consulta']}» "
                  f"en {', '.join(job['fuentes'])}.")

        scrapers = _construir_scrapers(job)

        def on_evento(tipo, nombre, extra=None):
            if tipo == "inicio":
                _log(job, f"[{nombre}] hilo iniciado.")
            elif tipo == "fin":
                _log(job, f"[{nombre}] terminado: {extra} registros recolectados.")
            elif tipo == "error":
                _log(job, f"[{nombre}] ERROR: {extra}")

        ruta_dataset = ejecutar_paralelo(scrapers=scrapers, on_evento=on_evento)
        if not ruta_dataset:
            raise RuntimeError("La extracción no generó ningún dataset consolidado.")
        _log(job, f"Dataset consolidado: {os.path.basename(ruta_dataset)}")

        job["estado"] = "clasificando"
        _log(job, f"Clasificando sentimientos en paralelo con {job['proveedor'].upper()}...")

        from almacenamiento_sentimientos import cargar_dataset, guardar
        from controlador_sentimientos import ControladorSentimientos
        from modelo import crear_analizador

        dataset = cargar_dataset(ruta_dataset)
        if not dataset["registros"]:
            raise RuntimeError(
                "El dataset consolidado no tiene registros con texto (0 "
                "opiniones extraídas). Revisa las claves de API / login."
            )

        analizador = crear_analizador(job["proveedor"])
        controlador = ControladorSentimientos(analizador)
        resultados, duracion = controlador.ejecutar_paralelo(dataset["registros"])
        info = guardar(resultados, problematica=dataset.get("problematica", job["consulta"]))
        _log(job, f"Clasificación paralela terminada en {duracion:.2f} s "
                  f"({len(resultados)} registros).")

        job["estado"] = "storytelling"
        with open(info["ruta"], encoding="utf-8") as f:
            sentimientos = json.load(f)
        historia = generar_storytelling(sentimientos)
        sentimientos["storytelling"] = historia
        sentimientos["tiempo_clasificacion_s"] = round(duracion, 2)

        rutas_a_actualizar = {info["ruta"]}
        if info.get("ruta_raiz"):
            rutas_a_actualizar.add(info["ruta_raiz"])
        for ruta in rutas_a_actualizar:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(sentimientos, f, ensure_ascii=False, indent=2)

        job["estado"] = "listo"
        job["resultado"] = {
            "archivo": os.path.basename(info["ruta"]),
            "total": info["total"],
            "resumen": info["resumen"],
            "tiempo_clasificacion_s": round(duracion, 2),
            "storytelling": historia,
        }
        _log(job, "Pipeline completo. Resultados listos en el dashboard.")
    except Exception as exc:  # noqa: BLE001
        job["estado"] = "error"
        job["error"] = f"{exc.__class__.__name__}: {exc}"
        _log(job, f"ERROR: {job['error']}")


# ---------------------------------------------------------------------
# API: disparo de búsqueda + progreso
# ---------------------------------------------------------------------
class SolicitudBusqueda(BaseModel):
    consulta: str
    fuentes: list[str] | None = None
    proveedor: str = "groq"


@app.post("/api/buscar")
def api_buscar(solicitud: SolicitudBusqueda):
    consulta = solicitud.consulta.strip()
    if not consulta:
        raise HTTPException(400, "La consulta no puede estar vacía.")

    fuentes = solicitud.fuentes or list(FUENTES_DISPONIBLES)
    fuentes = [f for f in fuentes if f in FUENTES_DISPONIBLES]
    if not fuentes:
        raise HTTPException(400, "Selecciona al menos una fuente válida.")

    proveedor = solicitud.proveedor if solicitud.proveedor in ("groq", "openai") else "groq"

    job = _nuevo_job(consulta, fuentes, proveedor)
    hilo = threading.Thread(target=_ejecutar_pipeline, args=(job["id"],), daemon=True)
    hilo.start()
    return {"job_id": job["id"]}


@app.get("/api/job/{job_id}")
def api_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado.")
    return job


@app.post("/api/job/{job_id}/confirmar-login")
def api_confirmar_login(job_id: str, cuerpo: dict):
    fuente = cuerpo.get("fuente", "")
    clave = f"{job_id}:{fuente}"
    evento = login_events.get(clave)
    if not evento:
        raise HTTPException(404, "No hay un login pendiente para esa fuente en este job.")
    evento.set()
    return {"ok": True}


@app.get("/api/fuentes")
def api_fuentes():
    """Indica qué fuentes tienen credenciales configuradas, para que la UI
    pueda advertir o deshabilitar las que no van a funcionar."""
    return {
        "Facebook": {"tipo": "login_manual_chrome", "disponible": True},
        "TikTok": {"tipo": "login_manual_chrome", "disponible": True},
        "YouTube": {"tipo": "api_key", "disponible": bool(os.getenv("YOUTUBE_API_KEY"))},
        "Reddit": {
            "tipo": "api_key",
            "disponible": bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")),
        },
    }


# ---------------------------------------------------------------------
# API: exploración de resultados ya generados (dashboard)
# ---------------------------------------------------------------------
def _listar_archivos_sentimientos():
    archivos = {}
    for d in (DIR_DATOS_RAIZ, DIR_DATOS_P7):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.startswith("sentimientos_") and f.endswith(".json"):
                ruta = os.path.join(d, f)
                if f not in archivos or os.path.getmtime(ruta) > os.path.getmtime(archivos[f]):
                    archivos[f] = ruta

    ordenados = sorted(archivos.items(), key=lambda kv: os.path.getmtime(kv[1]), reverse=True)
    return [
        {
            "nombre": nombre,
            "ruta": ruta,
            "fecha": datetime.fromtimestamp(os.path.getmtime(ruta)).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for nombre, ruta in ordenados
    ]


@app.get("/api/datasets")
def api_datasets():
    datasets = _listar_archivos_sentimientos()
    latest = datasets[0]["nombre"] if datasets else None
    return {"datasets": datasets, "latest": latest}


@app.get("/api/dataset")
def api_dataset(file: str = ""):
    datasets = _listar_archivos_sentimientos()
    objetivo = next((d for d in datasets if d["nombre"] == file), None)
    if not objetivo and datasets:
        objetivo = datasets[0]
    if not objetivo:
        raise HTTPException(404, "No hay datasets de sentimientos disponibles todavía.")
    with open(objetivo["ruta"], encoding="utf-8") as f:
        return JSONResponse(json.load(f))


# ---------------------------------------------------------------------
# Estáticos (dashboard)
# ---------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(DIR_STATIC, "index.html"))


app.mount("/", StaticFiles(directory=DIR_STATIC), name="static")


def main():
    import uvicorn

    puerto = int(os.environ.get("PUERTO_WEBAPP", "8000"))
    print("\n" + "=" * 70)
    print("  APLICACIÓN WEB — PROYECTO FINAL DE COMPUTACIÓN PARALELA")
    print("=" * 70)
    print(f"Interfaz disponible en: http://localhost:{puerto}")
    print("Ctrl+C para detener.\n")
    uvicorn.run(app, host="0.0.0.0", port=puerto, log_level="warning")


if __name__ == "__main__":
    main()
