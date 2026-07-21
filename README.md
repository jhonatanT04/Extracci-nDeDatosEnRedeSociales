# Análisis Paralelo de Redes Sociales — Museo Nacional del Ecuador

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Integrantes:** Justin Lucero, Jhonatan Tacuri, Wilmer Merchán

Sistema que extrae **en paralelo** opiniones publicadas en **Facebook, TikTok,
YouTube y X (Twitter)** sobre el diseño ganador del nuevo Museo Nacional del
Ecuador, las clasifica por sentimiento con un LLM (también en paralelo) y
presenta los resultados —con exploración e interpretación narrativa
(storytelling)— en una **aplicación web** de punta a punta.

> **¿Buscas cómo correr el proyecto final completo (app web)?** Ve directo a
> la sección [Proyecto Final: Aplicación Web](#proyecto-final-aplicación-web).
> Lo que sigue abajo documenta la Práctica 06 (extracción por CLI), que la
> app web reutiliza como motor de extracción.

---

## Contexto y problemática

El Gobierno del Ecuador realizó una convocatoria internacional para seleccionar
el diseño arquitectónico del nuevo Museo Nacional del Ecuador, destinado a
albergar más de 100.000 bienes patrimoniales. El diseño ganador, **"Ecos del
Sol"**, recibió numerosas críticas en redes sociales de ciudadanos, arquitectos
y artistas por aspectos estéticos, culturales y de representatividad nacional.

**Problemática.** ¿Cuál es la percepción de los usuarios de redes sociales sobre
el diseño ganador ("Ecos del Sol") del nuevo Museo Nacional del Ecuador?

**Objetivo.** Analizar las opiniones publicadas en redes sociales para
identificar el sentimiento predominante y los principales temas de discusión.

---

## Redes seleccionadas

| Red | Por qué es relevante | Cómo se extrae |
|-----|----------------------|----------------|
| **Facebook** | Los medios ecuatorianos publicaron la noticia y la ciudadanía opinó masivamente en los comentarios | Selenium sobre Chrome real (sesión iniciada por el usuario) |
| **TikTok** | Contenido audiovisual y opinión de públicos jóvenes sobre la polémica | Selenium sobre Chrome real |
| **YouTube** | Videos de noticias y análisis con debate extenso en los comentarios | API oficial (YouTube Data API v3) |
| **X (Twitter)** | Epicentro del debate público inmediato; arquitectos y ciudadanos opinaron en tiempo real sobre el diseño | Selenium sobre Chrome real (sesión iniciada por el usuario) |

Facebook, TikTok y X bloquean el scraping con librerías de terceros (imitan el
tráfico y son detectadas fácilmente), por lo que se automatiza **Google Chrome
real** con Selenium sobre una sesión que el usuario inicia manualmente: las
peticiones salen de un navegador legítimo con cookies válidas y esquivan gran
parte de la detección anti-bot. YouTube sí ofrece una **API oficial gratuita**,
así que ahí no hace falta navegador ni login: basta una clave de API.

---

## Estrategia de búsqueda

Todas las fuentes se consultan con el mismo tema (`museo nacional del ecuador`,
configurable en cada scraper). Cada registro guarda en el campo `consulta` con
qué criterio se localizó, para mantener la trazabilidad.

- **Facebook:** busca en el buscador del sitio, recorre el feed de resultados de
  forma incremental (ignorando bloques de sugerencias como "Páginas") y, por
  cada publicación, abre y extrae sus comentarios.
- **TikTok:** busca el tema, recorre las tarjetas de video de los resultados y,
  por cada video, abre la pestaña de comentarios y los extrae.
- **YouTube:** busca videos del tema con la API y descarga los hilos de
  comentarios (con respuestas anidadas) mediante paginación.
- **X (Twitter):** abre la búsqueda en vivo (`/search?q=...&f=live`), recorre
  los tweets de resultados y, por cada tweet, abre su hilo y extrae las
  respuestas como comentarios.

---

## Arquitectura

```
                 ┌────────────────────────────────────────────┐
                 │                 main.py                     │
                 └───────────────────┬────────────────────────┘
                                     │
                 ┌───────────────────▼────────────────────────┐
                 │        src/controlador.py                   │
                 │ ThreadPoolExecutor (un hilo por fuente)     │
                 │   + GestorLogin compartido                  │
                 └──────┬───────────┬───────────┬───────────┬──┘
             (hilo 1)   │  (hilo 2) │  (hilo 3) │  (hilo 4) │
              ┌─────────▼──┐ ┌──────▼───┐ ┌─────▼─────┐ ┌───▼──────┐
              │  Facebook  │ │  TikTok  │ │  YouTube  │ │    X     │
              │  Selenium  │ │ Selenium │ │  API v3   │ │ Selenium │
              └─────────┬──┘ └──────┬───┘ └─────┬─────┘ └───┬──────┘
                        │   (cada uno guarda su JSON)        │
                        └──────────────┬──────────────────────┘
                                       ▼
                          src/consolidar.py
                (une los cuatro JSON en un dataset unificado)
                                       ▼
                         datos/dataset_<fecha>.json
```

### Archivos

```
main.py                     # punto de entrada CLI (con opción de análisis de sentimientos)
webapp/                     # Proyecto Final: aplicación web de punta a punta (ver sección propia)
src/
  main.py                   # entrada mínima: solo la extracción paralela
  controlador.py            # ejecuta los scrapers en hilos + consolida
  gestor_login.py           # coordina los logins manuales entre hilos
  scraper_facebook.py       # scraper Selenium de Facebook (publicaciones + comentarios)
  scraper_tiktok.py         # scraper Selenium de TikTok (videos + comentarios)
  scraper_youtube.py        # extractor de YouTube por API oficial
  scraper_x.py              # scraper Selenium de X/Twitter (tweets + respuestas)
  consolidar.py             # une los JSON por fuente en un dataset unificado
datos/                      # datasets generados (JSON por fuente + combinado)
```

---

## Paralelismo: hilos y justificación

La extracción de las cuatro fuentes se ejecuta **al mismo tiempo** en
[`src/controlador.py`](src/controlador.py) con un `ThreadPoolExecutor`: un hilo
por fuente.

**Se eligieron hilos (threads), no procesos**, porque el trabajo es
**I/O-bound**: cada scraper pasa la mayor parte del tiempo esperando al navegador
o a la red (cargar páginas, hacer scroll, esperar respuestas de la API), no
calculando. Con hilos, mientras una fuente espera, Python libera el GIL y otro
hilo avanza: las esperas se **solapan** y el tiempo total tiende al de la fuente
más lenta, no a la suma de las cuatro. Además, los hilos comparten memoria, lo que
permite compartir el `GestorLogin` sin coste de serialización. Los procesos
convendrían si el cuello de botella fuera la CPU, que no es el caso aquí.

### Bloqueo coordinado de los logins

Facebook y TikTok necesitan que el usuario inicie sesión a mano y presione ENTER
en la terminal. Si dos hilos pidieran el login al mismo tiempo, competirían por
la entrada estándar y por la atención del usuario. Para evitarlo,
[`src/gestor_login.py`](src/gestor_login.py) implementa un **GestorLogin**
compartido por todos los hilos, con dos mecanismos:

- Un **Lock** garantiza que solo un hilo hace login a la vez.
- Un **Event** compartido hace que, mientras un hilo está en el login, **los
  demás hilos se bloqueen** al llegar a sus puntos de control, y se reanuden
  automáticamente cuando el login termina.

Así, cada vez que alguna red necesita iniciar sesión, el resto de la extracción
se pausa hasta que esa sesión esté lista, y luego todo continúa en paralelo.

---

## Almacenamiento y trazabilidad

Cada scraper guarda su propio JSON en [`datos/`](datos/)
(`facebook_publicaciones.json`, `tiktok_publicaciones.json`,
`youtube_publicaciones.json`). Al terminar,
[`src/consolidar.py`](src/consolidar.py) los une en un **dataset unificado**
`dataset_<fecha>.json`, donde cada publicación y cada comentario se convierte en
un registro plano y trazable:

| Campo | Descripción |
|-------|-------------|
| `fuente` | Red social de origen (Facebook / TikTok / YouTube / X) |
| `consulta` | Tema o criterio de búsqueda que originó el registro |
| `texto` | Contenido textual (publicación o comentario) |
| `autor`, `fecha_publicacion`, `url` | Metadatos |
| `metricas` | Interacción disponible (likes, comentarios, vistas) |
| `id_unico`, `extraido_en` | Deduplicación y sello temporal |

Los registros se **deduplican** por `id_unico`.

---

## Relación con el proyecto final

El campo `texto` es la materia prima del proyecto final de **análisis de
sentimientos**: sobre esos textos se clasificará la polaridad (a favor / en
contra / neutro). El campo `fuente` permite comparar el sentimiento entre
Facebook, TikTok, YouTube y X, y `metricas` permite ponderar por
relevancia.

---

## Proyecto Final: Aplicación Web

La entrega final integra de punta a punta la extracción (Práctica 06) y el
análisis de sentimientos (Práctica 07) en una sola **aplicación web**
(`webapp/`): el usuario escribe una consulta en el navegador, la app dispara
la extracción concurrente de las 4 redes, clasifica el sentimiento en
paralelo con un LLM, genera una interpretación narrativa (storytelling) y
muestra todo en un dashboard interactivo — sin tocar la terminal salvo para
levantar el servidor.

### Arquitectura de la app web

```
Navegador (formulario de búsqueda + dashboard)
        │  POST /api/buscar {consulta, fuentes, proveedor}
        ▼
webapp/server.py (FastAPI)
        │  lanza un hilo de trabajo por job (no bloquea el servidor)
        ▼
src.controlador.ejecutar_paralelo()      ← Práctica 06 (4 hilos, uno por red)
        │  Facebook/TikTok: si hace falta login, el job queda en estado
        │  "login_pendiente" y el hilo espera un threading.Event que la
        │  web libera cuando el usuario confirma haber iniciado sesión.
        ▼
practica7.ControladorSentimientos.ejecutar_paralelo()  ← Práctica 07 (hilos
        │                                                  por fuente + cola
        │                                                  productor/consumidor)
        ▼
webapp/storytelling.py  → interpretación narrativa basada en las cifras
        ▼
datos/sentimientos_<fecha>.json (con el storytelling embebido)
        │  GET /api/job/{id} (progreso en vivo, polling)
        │  GET /api/dataset  (resultado final)
        ▼
Dashboard (KPIs, distribución por red, storytelling, exploración de
comentarios con filtros y explicabilidad del LLM)
```

### Cómo ejecutar la app web

```bash
# 1) Instalar dependencias (usa uv; crea/gestiona .venv en la raíz)
uv sync

# 2) Completa las claves de API en .env (copia .env.example como base):
#    GROQ_API_KEY o OPENAI_API_KEY   -> clasificación de sentimientos
#    YOUTUBE_API_KEY                 -> extracción de YouTube
#    (Facebook/TikTok/X usan tu perfil real de Chrome, ver src/navegador.py)

# 3) Levantar el servidor
uv run python webapp/server.py

# 4) Abrir http://localhost:8000 en el navegador
```

Desde la interfaz: escribe una consulta, elige las fuentes y el proveedor de
LLM, y presiona "Iniciar extracción paralela". Si Facebook o TikTok necesitan
login, se abre una ventana de Chrome — inicia sesión ahí y presiona el botón
"Ya inicié sesión, continuar" en la web (el resto de hilos sigue trabajando
mientras tanto, igual que en la Práctica 06). Al terminar, el dashboard se
actualiza automáticamente con los nuevos resultados y el storytelling.

---

## Cómo ejecutar solo la extracción (Práctica 06, por CLI)

Requiere **Python 3.9+**, **Google Chrome** y las dependencias del proyecto.

```bash
# 1) Entorno e instalación
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Claves de API en un archivo .env (ver .env.example)
#    YOUTUBE_API_KEY=tu_clave
#    (Facebook/TikTok/X usan tu perfil real de Chrome, ver src/navegador.py)

# 3) Ejecutar la extracción paralela
python3 -m src.main       # solo extracción + consolidación
python3 main.py           # extracción paralela + (opcional) análisis de sentimientos
```

Durante la corrida, cuando Facebook o TikTok abran Chrome, inicia sesión
manualmente y presiona ENTER en la terminal; mientras tanto los demás hilos
esperan. Ejecuta el comando desde la raíz del proyecto para que las rutas de
salida (`datos/`) sean correctas.
