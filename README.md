# Extracción Paralela de Datos en Redes Sociales — Museo Nacional del Ecuador

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Práctica:** Extracción concurrente de datos desde redes sociales
**Integrantes:** _(completar con los nombres del grupo)_

Sistema que carga, normaliza y almacena **en paralelo** opiniones publicadas en
**X (Twitter), Facebook y TikTok** sobre el diseño ganador del nuevo Museo
Nacional del Ecuador, generando un dataset textual con trazabilidad, listo para
el análisis de sentimientos del proyecto final.

---

## 1. Contexto y problemática _(rúbrica: 0.7)_

**Contexto.** El Gobierno del Ecuador realizó una convocatoria internacional
para seleccionar el diseño arquitectónico del nuevo Museo Nacional del Ecuador,
destinado a albergar más de 100.000 bienes patrimoniales. El diseño ganador,
**"Ecos del Sol"**, recibió numerosas críticas en redes sociales de ciudadanos,
arquitectos y artistas por aspectos estéticos, culturales y de representatividad
nacional. La controversia llevó al Gobierno a dejar sin efecto la propuesta
ganadora y reconvocar a los finalistas.

**Problemática.**
> ¿Cuál es la percepción de los usuarios de redes sociales sobre el diseño
> ganador ("Ecos del Sol") del nuevo Museo Nacional del Ecuador, y cuáles son
> los principales argumentos a favor y en contra expresados en las plataformas
> digitales?

**Objetivo.** Analizar las opiniones publicadas en redes sociales para
identificar el **sentimiento predominante** y los **principales temas de
discusión**.

Definido en [`src/config.py`](src/config.py) → `CONTEXTO`, `PROBLEMATICA`,
`OBJETIVO`.

---

## 2. Redes seleccionadas y su justificación _(rúbrica: 0.6)_

| Red | Por qué es relevante |
|-----|----------------------|
| **X (Twitter)** | Epicentro del debate público inmediato; arquitectos y ciudadanos criticaron el diseño en tiempo real |
| **Facebook** | Los medios ecuatorianos publicaron la noticia y la ciudadanía opinó masivamente en los comentarios |
| **TikTok** | Contenido audiovisual y opinión de públicos jóvenes sobre la polémica |

Las tres concentran la conversación pública ecuatoriana sobre el tema, con
perfiles de usuario distintos, lo que enriquece el análisis de percepción.

---

## 3. Estrategia de extracción (justificación del diseño)

La consigna pide *"proponer e implementar una estrategia de extracción... que
puede incluir scrapers, APIs oficiales, librerías de terceros u otros mecanismos
justificados"*, reconociendo que **algunas redes tienen restricciones de
acceso**. Este proyecto documenta ese caso real:

**Fase 1 — Se intentó scraping automático** con librerías de terceros. No fue
viable por las defensas anti-bot de cada plataforma:

| Red | Librería probada | Resultado |
|-----|------------------|-----------|
| X (Twitter) | `twikit` | La generación del *x-client-transaction-id* está rota contra el JS ofuscado actual de X (`Couldn't get KEY_BYTE indices`). Sin API gratuita. |
| Facebook | `facebook-scraper` | Devuelve 0 publicaciones incluso con cookies de sesión válidas (Facebook cambió/bloqueó `m.facebook.com`). |
| TikTok | `TikTokApi` (Playwright) | Detección de bot en modo headless (`empty response... detecting you're a bot`). |

**Fase 2 — Estrategia adoptada: scraping con Selenium (navegador real).** En
lugar de librerías que imitan el tráfico (fácilmente detectables), se automatiza
**Google Chrome real** con Selenium sobre una **sesión iniciada por el usuario**.
Esto sortea gran parte de la detección anti-bot porque las peticiones salen de un
navegador legítimo con cookies válidas. Detalles:

- **Perfil persistente por red** (`.perfil_navegador/<red>`, ver
  [`src/navegador.py`](src/navegador.py)): el login manual se hace **una sola
  vez** con `preparar_sesion.py` y la sesión se reutiliza en cada corrida.
- **Ajustes stealth**: se desactivan las banderas de automatización y se oculta
  `navigator.webdriver`.
- Cada red tiene un subperfil propio, por lo que los navegadores pueden correr
  **en paralelo** sin conflicto.

Estado de implementación (se construye **una red a la vez**):

| Red | Mecanismo | Estado |
|-----|-----------|--------|
| **X (Twitter)** | Selenium (`src/extractores/twitter_x.py`) | ✅ Implementado |
| **Facebook** | Selenium | 🚧 En construcción (fallback CSV en `datos_manuales/`) |
| **TikTok** | Selenium | 🚧 En construcción (fallback CSV en `datos_manuales/`) |

> La Fase 1 (librerías `twikit`/`facebook-scraper`/`TikTokApi`) quedó documentada
> arriba como justificación de por qué se pasó a Selenium.

### Estrategia de búsqueda (centralizada en [`src/config.py`](src/config.py))
- **Palabras clave:** `Ecos del Sol museo`, `nuevo Museo Nacional del Ecuador`…
- **Hashtags:** `#EcosDelSol`, `#MuseoNacionalEcuador`, `#NuevoMuseoNacional`…
- Cada registro guarda en el campo `consulta` con qué criterio se localizó
  (trazabilidad).

---

## 4. Diseño de la solución y arquitectura _(rúbrica: 0.7)_

```
                 ┌──────────────────────────────────────────┐
                 │              main.py (CLI)                │
                 └───────────────────┬──────────────────────┘
                                     │
                 ┌───────────────────▼──────────────────────┐
                 │   ControladorParalelo (src/controlador)   │
                 │   POOL de hilos + COLA productor/consumidor│
                 └───────┬──────────────┬──────────────┬─────┘
             (hilo 1)    │   (hilo 2)   │   (hilo 3)   │
                  ┌──────▼───┐   ┌──────▼───┐   ┌──────▼───┐
                  │ X/Twitter│   │ Facebook │   │  TikTok  │   ← PRODUCTORES
                  │ Selenium │   │ Selenium │   │ Selenium │     (scrapean+
                  └──────┬───┘   └──────┬───┘   └──────┬───┘      normalizan)
                         └───────┬──────┴──────────────┘
                                 ▼
                          queue.Queue          ← canal común
                                 ▼
                      Consumidor (recolecta)    ← CONTROLADOR central
                                 ▼
                    Registro normalizado (src/modelos)
                                 ▼
               Almacenamiento JSON (src/almacenamiento)
```

La abstracción **`ExtractorBase`** hace que cada red devuelva `Registro`
homogéneos; el controlador las trata por igual (polimorfismo) y
`extraer_seguro()` aísla fallos (si a una red le falta su CSV, las otras
continúan).

---

## 5. Implementación de la extracción paralela _(rúbrica: 1.2)_

Núcleo en [`src/controlador.py`](src/controlador.py). Las tres redes se procesan
**al mismo tiempo**:

1. **Pool de hilos** (`concurrent.futures.ThreadPoolExecutor`): un hilo por red,
   cada uno **productor** que scrapea su red (navegador Selenium propio), limpia
   y normaliza los textos y empuja los `Registro` a una cola.
2. **Cola segura** (`queue.Queue`): canal thread-safe entre los extractores y un
   **consumidor** central (patrón **Productor/Consumidor**).
3. **Aislamiento de fallos** (`extraer_seguro`): un error en una red no detiene
   a las demás.

En los logs de [`evidencias/`](evidencias/) se observa que los tres hilos
arrancan concurrentemente (`Extractor_0`, `Extractor_1`…).

---

## 6. Justificación de la técnica de paralelismo _(rúbrica: 0.7)_

**Se eligieron HILOS (threads), no procesos.**

El trabajo de cada fuente es **I/O-bound**: dominado por la **espera de red** del
navegador (cargar la página de búsqueda, esperar resultados, hacer scroll). En
ese perfil:

- Con **hilos**, mientras el navegador de una red espera la red, Python
  **libera el GIL** y el hilo de otra red avanza: las esperas se **solapan** y el
  tiempo total tiende al de la red más lenta, no a la suma. Además comparten
  memoria, ideal para volcar todo a una cola común.
- Con **procesos** pagaríamos creación de procesos y **serialización** de datos
  sin beneficio, porque el cuello de botella es la red, no la CPU (los procesos
  convienen en tareas *CPU-bound*).

Se añaden **colas** porque la consigna pide comunicar los datos entre los
extractores y un controlador central; `queue.Queue` es la estructura segura para
hilos que lo resuelve. El **pool** administra el ciclo de vida de los hilos.

Con `python main.py --benchmark` se mide el *speedup* (tiempo secuencial ÷
paralelo): al solapar las esperas de red de los tres navegadores, la corrida
paralela es notablemente más rápida que hacerlas una tras otra.

---

## 7. Preparar la sesión (paso obligatorio la primera vez)

Los scrapers usan tu sesión iniciada. Antes de la primera corrida, inicia sesión
manualmente en cada red (se guarda en el perfil y se reutiliza):

```bash
python3 preparar_sesion.py x          # abre Chrome, inicia sesión en X, ENTER
# (más adelante: preparar_sesion.py facebook / tiktok)
```

La sesión queda almacenada en `.perfil_navegador/<red>` (no versionado). No se
guardan usuarios ni contraseñas en el proyecto: sólo las cookies del navegador.

> ⚠️ Automatizar una cuenta puede infringir los Términos de Servicio de la red.
> Úsese con fines académicos y, de preferencia, con una cuenta secundaria.

---

## 8. Almacenamiento y trazabilidad _(rúbrica: 0.5)_

[`src/almacenamiento.py`](src/almacenamiento.py) guarda los resultados en
**JSON** con marca de tiempo en [`datos/`](datos/): un **dataset combinado**
(`dataset_<fecha>.json`) y **un archivo por red** (`x_twitter_<fecha>.json`, …).
Cada `Registro` ([`src/modelos.py`](src/modelos.py)) conserva:

| Campo | Descripción |
|-------|-------------|
| `fuente` | Red social de origen (X / Facebook / TikTok) |
| `consulta` | Palabra clave, hashtag o página que originó el registro |
| `texto` | Contenido textual limpio (sin HTML) |
| `autor`, `fecha_publicacion`, `url` | Metadatos |
| `metricas` | Interacción: likes, comentarios, compartidos, vistas |
| `id_unico`, `extraido_en` | Deduplicación y sello temporal |

Se **deduplica** por `id_unico`.

---

## 9. Evidencia de ejecución y dataset _(rúbrica: 0.4)_

- Dataset generado: carpeta [`datos/`](datos/) (JSON combinado + JSON por red).
- Log de cada corrida: carpeta [`evidencias/`](evidencias/) (muestra los tres
  hilos iniciando concurrentemente).

---

## 10. Relación con el proyecto final _(rúbrica: 0.2)_

El campo `texto` es la **materia prima** del proyecto final de **análisis de
sentimientos**: sobre esos textos se clasificará la polaridad (a favor / en
contra / neutro). `fuente` permite **comparar el sentimiento entre X, Facebook y
TikTok**; `metricas` permite **ponderar** por relevancia; y `fecha_publicacion`
habilita el análisis temporal de la controversia y el *storytelling* final.

---

## Cómo ejecutar

Requiere **Python 3.9+**, **Google Chrome** y Selenium.

```bash
# 1) Entorno e instalación
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Iniciar sesión en la red (una vez; ver §7)
python3 preparar_sesion.py x

# 3) Ejecutar la extracción paralela
python3 main.py               # scraping paralelo + guardado del dataset JSON
python3 main.py --benchmark   # además compara secuencial vs paralelo (speedup)
python3 main.py --secuencial  # sólo modo secuencial (referencia)
```

> Para pruebas sin ventana: `HEADLESS=1 python3 main.py` (las redes detectan el
> modo headless, úsalo sólo para depurar).

## Estructura del proyecto

```
main.py                     # punto de entrada (CLI)
preparar_sesion.py          # login manual por red (guarda sesión en el perfil)
src/
  navegador.py              # fábrica de Chrome+Selenium (perfil persistente, stealth)
  config.py                 # contexto, problemática, estrategia, parámetros Selenium
  modelos.py                # Registro (modelo unificado + trazabilidad)
  carga_manual.py           # fallback: lectura+normalización de CSV (FB/TikTok, transitorio)
  utilidades.py             # limpieza de texto, logging
  controlador.py            # núcleo PARALELO: pool de hilos + cola
  almacenamiento.py         # guardado JSON (combinado + por red) + deduplicación
  extractores/
    base.py                 # ExtractorBase (contrato común)
    twitter_x.py            # scraper Selenium de X (implementado)
    facebook.py  tiktok.py  # fallback CSV (migración a Selenium en curso)
datos_manuales/             # CSV de respaldo mientras FB/TikTok migran a Selenium
datos/                      # datasets generados (JSON)
evidencias/                 # logs de cada ejecución
```
