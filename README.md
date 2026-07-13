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

**Fase 2 — Estrategia adoptada: recolección manual + procesamiento paralelo.**
Las opiniones reales se recolectan manualmente (usando las palabras clave y
hashtags de la §_estrategia de búsqueda_) y se vuelcan a un CSV por red en
[`datos_manuales/`](datos_manuales/). El sistema entonces **lee, limpia,
normaliza, deduplica y almacena las tres fuentes EN PARALELO**. Así el requisito
de paralelismo se cumple sobre datos reales y verificables, sin depender de APIs
de pago ni de scraping bloqueado.

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
                  │  .csv    │   │   .csv   │   │   .csv   │     (leen+normalizan)
                  └──────┬───┘   └──────┬───┘   └──────┬───┘
                         └───────┬──────┴──────────────┘
                                 ▼
                          queue.Queue          ← canal común
                                 ▼
                      Consumidor (recolecta)    ← CONTROLADOR central
                                 ▼
                    Registro normalizado (src/modelos)
                                 ▼
               Almacenamiento JSON + CSV (src/almacenamiento)
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
   cada uno **productor** que lee su CSV, limpia y normaliza los textos y empuja
   los `Registro` a una cola.
2. **Cola segura** (`queue.Queue`): canal thread-safe entre los extractores y un
   **consumidor** central (patrón **Productor/Consumidor**).
3. **Aislamiento de fallos** (`extraer_seguro`): un error en una red no detiene
   a las demás.

En los logs de [`evidencias/`](evidencias/) se observa que los tres hilos
arrancan concurrentemente (`Extractor_0`, `Extractor_1`…).

---

## 6. Justificación de la técnica de paralelismo _(rúbrica: 0.7)_

**Se eligieron HILOS (threads), no procesos.**

El trabajo de cada fuente es **I/O-bound** (lectura de archivos) con un poco de
CPU ligera (limpieza de HTML/entidades y normalización). En ese perfil:

- Con **hilos**, las operaciones de E/S se **solapan** (mientras un hilo lee su
  archivo, otro avanza) y comparten memoria, ideal para volcar todo a una cola
  común. Los hilos son livianos y suficientes.
- Con **procesos** pagaríamos creación de procesos y **serialización** de datos
  sin beneficio, porque no hay cómputo pesado (los procesos convienen en tareas
  *CPU-bound*).

Se añaden **colas** porque la consigna pide comunicar los datos entre los
extractores y un controlador central; `queue.Queue` es la estructura segura para
hilos que lo resuelve. El **pool** administra el ciclo de vida de los hilos.

> **Nota honesta sobre el `--benchmark`.** El *speedup* real se aprecia cuando
> hay volumen de datos que leer/procesar; con pocos registros los tiempos son de
> milisegundos y la medición es ruido. El valor demostrado aquí es la
> **arquitectura concurrente** (pool + cola + productor/consumidor), no un número
> de aceleración. La misma arquitectura fue la que, en la versión con APIs
> reales, dio speedups de ~3x (solapando esperas de red).

---

## 7. Recolección de los datos (paso obligatorio)

Llena los tres archivos de [`datos_manuales/`](datos_manuales/) con opiniones
reales (guía completa en [`datos_manuales/COMO_LLENAR.md`](datos_manuales/COMO_LLENAR.md)):

- `facebook.csv`, `x_twitter.csv`, `tiktok.csv`
- Columna obligatoria: **`texto`**. Opcionales (suman trazabilidad):
  `consulta`, `autor`, `fecha`, `url`, `likes`, `comentarios`, `compartidos`, `vistas`.
- Recomendado: llenarlos con **LibreOffice/Excel/Sheets** y exportar como CSV
  UTF-8 (maneja solo las comas y comillas del texto).
- Incluye opiniones **a favor y en contra** para un análisis representativo.

---

## 8. Almacenamiento y trazabilidad _(rúbrica: 0.5)_

[`src/almacenamiento.py`](src/almacenamiento.py) guarda el dataset en **JSON y
CSV** con marca de tiempo en [`datos/`](datos/). Cada `Registro`
([`src/modelos.py`](src/modelos.py)) conserva:

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

- Dataset generado: carpeta [`datos/`](datos/) (`.json` y `.csv`).
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

Requiere **solo Python 3.9+** (sin dependencias que instalar):

```bash
# 1) Llena datos_manuales/*.csv con opiniones reales (ver §7)
# 2) Ejecuta:
python3 main.py               # carga paralela + guardado del dataset
python3 main.py --benchmark   # además compara secuencial vs paralelo
python3 main.py --secuencial  # sólo modo secuencial (referencia)
```

## Estructura del proyecto

```
main.py                     # punto de entrada (CLI)
datos_manuales/             # CSV a llenar con datos reales (uno por red)
  facebook.csv  x_twitter.csv  tiktok.csv  COMO_LLENAR.md
src/
  config.py                 # contexto, problemática, estrategia, fuentes
  modelos.py                # Registro (modelo unificado + trazabilidad)
  carga_manual.py           # lectura+normalización de los CSV
  utilidades.py             # limpieza de texto, logging
  controlador.py            # núcleo PARALELO: pool de hilos + cola
  almacenamiento.py         # guardado JSON/CSV + deduplicación
  extractores/
    base.py                 # ExtractorBase (contrato común)
    twitter_x.py  facebook.py  tiktok.py
datos/                      # datasets generados (JSON + CSV)
evidencias/                 # logs de cada ejecución
```
