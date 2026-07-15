# Extracción Paralela de Datos en Redes Sociales — Museo Nacional del Ecuador

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Integrantes:** _(completar con los nombres del grupo)_

Sistema que extrae **en paralelo** opiniones publicadas en **Facebook, TikTok y
YouTube** sobre el diseño ganador del nuevo Museo Nacional del Ecuador, y genera
un dataset textual unificado con trazabilidad, listo para el análisis de
sentimientos del proyecto final.

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

Facebook y TikTok bloquean el scraping con librerías de terceros (imitan el
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

---

## Arquitectura

```
                 ┌────────────────────────────────────────────┐
                 │                 main.py                     │
                 └───────────────────┬────────────────────────┘
                                     │
                 ┌───────────────────▼────────────────────────┐
                 │        src/controlador.py                   │
                 │   ThreadPoolExecutor (un hilo por fuente)   │
                 │   + GestorLogin compartido                  │
                 └──────┬───────────────┬───────────────┬──────┘
             (hilo 1)   │    (hilo 2)   │    (hilo 3)    │
              ┌─────────▼──┐   ┌────────▼──┐   ┌─────────▼──┐
              │  Facebook  │   │  TikTok   │   │  YouTube   │
              │  Selenium  │   │  Selenium │   │  API v3    │
              └─────────┬──┘   └────────┬──┘   └─────────┬──┘
                        │  (cada uno guarda su JSON)      │
                        └──────────────┬─────────────────┘
                                       ▼
                          src/consolidar.py
                (une los tres JSON en un dataset unificado)
                                       ▼
                         datos/dataset_<fecha>.json
```

### Archivos

```
main.py                     # punto de entrada (con opción de análisis de sentimientos)
src/
  main.py                   # entrada mínima: solo la extracción paralela
  controlador.py            # ejecuta los scrapers en hilos + consolida
  gestor_login.py           # coordina los logins manuales entre hilos
  scraper_facebook.py       # scraper Selenium de Facebook (publicaciones + comentarios)
  scraper_tiktok.py         # scraper Selenium de TikTok (videos + comentarios)
  scraper_youtube.py        # extractor de YouTube por API oficial
  consolidar.py             # une los JSON por fuente en un dataset unificado
datos/                      # datasets generados (JSON por fuente + combinado)
```

---

## Paralelismo: hilos y justificación

La extracción de las tres fuentes se ejecuta **al mismo tiempo** en
[`src/controlador.py`](src/controlador.py) con un `ThreadPoolExecutor`: un hilo
por fuente.

**Se eligieron hilos (threads), no procesos**, porque el trabajo es
**I/O-bound**: cada scraper pasa la mayor parte del tiempo esperando al navegador
o a la red (cargar páginas, hacer scroll, esperar respuestas de la API), no
calculando. Con hilos, mientras una fuente espera, Python libera el GIL y otro
hilo avanza: las esperas se **solapan** y el tiempo total tiende al de la fuente
más lenta, no a la suma de las tres. Además, los hilos comparten memoria, lo que
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
| `fuente` | Red social de origen (Facebook / TikTok / YouTube) |
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
Facebook, TikTok y YouTube, y `metricas` permite ponderar por relevancia.

---

## Cómo ejecutar

Requiere **Python 3.9+**, **Google Chrome** y las dependencias del proyecto.

```bash
# 1) Entorno e instalación
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Clave de la API de YouTube en un archivo .env
#    YOUTUBE_API_KEY=tu_clave

# 3) Ejecutar la extracción paralela
python3 -m src.main       # solo extracción + consolidación
python3 main.py           # extracción paralela + (opcional) análisis de sentimientos
```

Durante la corrida, cuando Facebook o TikTok abran Chrome, inicia sesión
manualmente y presiona ENTER en la terminal; mientras tanto los demás hilos
esperan. Ejecuta el comando desde la raíz del proyecto para que las rutas de
salida (`datos/`) sean correctas.
