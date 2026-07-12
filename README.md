# Extracción Paralela de Datos en Redes Sociales

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Práctica:** Extracción concurrente de datos desde redes sociales / fuentes digitales
**Integrantes:** _(completar con los nombres del grupo)_

Sistema que extrae, **en paralelo**, opiniones publicadas en cuatro fuentes
digitales sobre una misma problemática, y genera un dataset textual con
trazabilidad, listo para el análisis de sentimientos del proyecto final.

---

## 1. Problemática _(rúbrica: 0.7)_

> **Percepción pública sobre el uso de la Inteligencia Artificial en la
> educación** (impacto de herramientas como ChatGPT en el aprendizaje, la
> enseñanza y la integridad académica).

Es un tema real y actual: la irrupción de la IA generativa ha abierto un debate
intenso entre estudiantes, docentes y desarrolladores sobre si estas
herramientas ayudan o perjudican al aprendizaje. Las redes y comunidades
digitales concentran gran cantidad de opiniones espontáneas al respecto, lo que
las hace idóneas para un análisis de percepción.

Definición en código: [`src/config.py`](src/config.py) → `PROBLEMATICA`.

---

## 2. Fuentes seleccionadas y su justificación _(rúbrica: 0.6)_

Se seleccionaron **4 fuentes** (supera el mínimo de 3, y da redundancia si una
API falla). Todas ofrecen **API pública sin autenticación**, lo que garantiza
la reproducibilidad del proyecto sin gestionar claves privadas.

| Fuente | Tipo | Por qué es relevante | Estrategia | API |
|--------|------|----------------------|-----------|-----|
| **Hacker News** | Comunidad de tecnología y sociedad | Sus *comentarios* contienen debate argumentado sobre IA y educación | Palabras clave sobre comentarios | Algolia Search API |
| **Mastodon** | Red social federada (microblogging) | Opinión pública espontánea, estilo Twitter/X pero de acceso abierto | Hashtags | `timelines/tag` |
| **Lemmy** | Red social tipo foro (alternativa a Reddit) | Publicaciones y debate comunitario por temas | Palabras clave sobre *posts* | API v3 `search` |
| **DEV.to** | Red social de desarrolladores (Forem) | Artículos de docentes/estudiantes que construyen o usan IA educativa | Tags + filtro de educación | API de artículos |

> **Nota sobre X/Twitter, Reddit, Instagram:** se evaluaron pero restringen el
> acceso automatizado (bloqueo de scraping / API de pago). Se optó por fuentes
> abiertas equivalentes, cumpliendo el espíritu de la práctica: *proponer una
> estrategia de extracción viable ante las restricciones de acceso*.

Un extractor por fuente en [`src/extractores/`](src/extractores/).

---

## 3. Diseño de la solución y estrategia de búsqueda _(rúbrica: 0.7)_

### Estrategia de búsqueda
La búsqueda se centraliza en [`src/config.py`](src/config.py) para garantizar
**trazabilidad**:

- **Palabras clave** (búsqueda por texto): `artificial intelligence education`,
  `AI in education`, `ChatGPT students`.
- **Hashtags / tags** (fuentes indexadas por etiqueta): `ai`, `edtech`,
  `machinelearning`.
- **Filtro on-topic**: en fuentes amplias (tag `ai` de DEV.to) se filtra por
  palabras de educación para no desviarse de la problemática.

### Arquitectura

```
                 ┌──────────────────────────────────────────┐
                 │              main.py (CLI)                │
                 └───────────────────┬──────────────────────┘
                                     │
                 ┌───────────────────▼──────────────────────┐
                 │   ControladorParalelo (src/controlador)   │
                 │   POOL de hilos + COLA productor/consumidor│
                 └───┬───────┬───────────┬───────────┬───────┘
        (hilo 1)     │       │ (hilo 2)  │ (hilo 3)  │ (hilo 4)
              ┌──────▼─┐ ┌───▼────┐ ┌────▼───┐ ┌─────▼────┐
              │HackerN.│ │Mastodon│ │ Lemmy  │ │  DEV.to  │   ← PRODUCTORES
              └──────┬─┘ └───┬────┘ └────┬───┘ └─────┬────┘
                     └───────┴─────┬─────┴───────────┘
                                   ▼
                            queue.Queue          ← canal común
                                   ▼
                        Consumidor (recolecta)    ← CONSUMIDOR central
                                   ▼
                      Registro normalizado (src/modelos)
                                   ▼
                 Almacenamiento JSON + CSV (src/almacenamiento)
```

Diseño clave: **abstracción `ExtractorBase`**. Cada fuente implementa
`extraer()` y devuelve una lista de `Registro` homogéneos, de modo que el
controlador trata a todas por igual (polimorfismo) y añadir una nueva fuente no
cambia el núcleo paralelo.

---

## 4. Implementación de la extracción paralela _(rúbrica: 1.2)_

Toda la lógica está en [`src/controlador.py`](src/controlador.py). Las cuatro
fuentes se consultan **al mismo tiempo**:

1. **Pool de hilos** (`concurrent.futures.ThreadPoolExecutor`): lanza un hilo
   por fuente. Cada hilo es un **productor** que descarga y empuja sus
   registros a una cola.
2. **Cola segura** (`queue.Queue`): canal de comunicación thread-safe entre los
   extractores y un **consumidor** central (patrón **Productor/Consumidor**).
   El consumidor recoge los registros a medida que llegan, sin bloqueos.
3. **Aislamiento de fallos** (`extraer_seguro`): si una fuente falla, se
   registra el error y las demás continúan; el sistema nunca se detiene por una
   sola API caída.

En la ejecución real (ver §7) los cuatro hilos arrancaron en el mismo segundo
(`15:02:07`), evidenciando ejecución concurrente.

---

## 5. Justificación de la técnica de paralelismo _(rúbrica: 0.7)_

**Se eligieron HILOS (threads), no procesos. ¿Por qué?**

La extracción es una tarea **I/O-bound**: >90% del tiempo el programa **espera
respuestas HTTP** de las APIs; casi no hay cómputo. En este escenario:

- Con **hilos**, mientras un hilo espera la red, Python **libera el GIL** y otro
  hilo avanza. Los tiempos de espera se **solapan** y el tiempo total tiende al
  de la fuente más lenta, no a la suma. Además los hilos son **livianos** y
  comparten memoria, ideal para volcar todo a una cola común.
- Con **procesos** pagaríamos el coste de crear procesos y **serializar** datos
  entre ellos, sin ganancia real porque el cuello de botella es la red, no la
  CPU. (Los procesos convienen cuando la tarea es *CPU-bound*.)

Se añadieron **colas** porque la práctica requiere comunicar los datos entre los
extractores y un controlador central: `queue.Queue` es la estructura segura
para hilos que resuelve exactamente eso, y un **pool** porque administra
automáticamente el ciclo de vida de los hilos.

**Evidencia empírica del acierto** (modo `--benchmark`):

| Modo | Tiempo | Aceleración |
|------|--------|-------------|
| Secuencial | 11.37 s | 1.00x |
| **Paralelo** | **3.68 s** | **3.09x** |

El *speedup* de ~3x con 4 fuentes I/O-bound confirma que los hilos solapan
efectivamente las esperas de red.

---

## 6. Almacenamiento y trazabilidad _(rúbrica: 0.5)_

[`src/almacenamiento.py`](src/almacenamiento.py) guarda el dataset en **JSON y
CSV** con marca de tiempo, en [`datos/`](datos/). Cada registro
([`src/modelos.py`](src/modelos.py) → `Registro`) conserva la trazabilidad
exigida:

| Campo | Descripción |
|-------|-------------|
| `fuente` | Red social / fuente de origen |
| `consulta` | Palabra clave o hashtag que originó el registro |
| `texto` | Contenido textual limpio (sin HTML) |
| `autor`, `fecha_publicacion`, `url`, `idioma` | Metadatos |
| `metricas` | Interacción: likes, reacciones, comentarios, puntos… |
| `id_unico`, `extraido_en` | Deduplicación y sello temporal de extracción |

Se **deduplica** por `id_unico` (una misma opinión puede aparecer en varias
consultas).

Ejemplo de registro real:
```json
{
  "fuente": "DEV.to",
  "consulta": "tag:ai+filtro:educacion",
  "texto": "Introducing Our Next DEV Education Track: \"Build Multi-Agent Systems...\"",
  "autor": "jess",
  "metricas": { "reacciones": 197, "comentarios": 38, "tags": "agents,gemini,ai" }
}
```

---

## 7. Evidencia de ejecución y dataset _(rúbrica: 0.4)_

Última ejecución (`python3 main.py --benchmark`):

```
Registros brutos : 251
Registros únicos  : 247
Registros por fuente:
    DEV.to      : 26
    HackerNews  : 75
    Lemmy       : 72
    Mastodon    : 74
Tiempo secuencial : 11.37 s
Tiempo paralelo    : 3.68 s   (speedup 3.09x)
```

- Dataset generado: carpeta [`datos/`](datos/) (`.json` y `.csv`).
- Log de cada corrida: carpeta [`evidencias/`](evidencias/).

---

## 8. Relación con el proyecto final _(rúbrica: 0.2)_

El campo `texto` de cada registro es la **materia prima** para el proyecto
final de **análisis de sentimientos**: sobre esos textos se aplicará
clasificación de polaridad (positivo/negativo/neutro) para medir la percepción
sobre la IA en la educación. La columna `fuente` permitirá **comparar el
sentimiento entre plataformas**, `metricas` permitirá **ponderar** por
relevancia (más likes = más peso) y `fecha_publicacion` habilitará el análisis
temporal y el *storytelling* del informe final.

---

## Cómo ejecutar

Requiere **solo Python 3.9+** (sin dependencias externas):

```bash
python3 main.py               # extracción paralela + guardado del dataset
python3 main.py --benchmark   # además compara secuencial vs paralelo (speedup)
python3 main.py --secuencial  # sólo modo secuencial (referencia)
```

## Estructura del proyecto

```
main.py                     # punto de entrada (CLI)
src/
  config.py                 # problemática + estrategia de búsqueda
  modelos.py                # Registro (modelo unificado + trazabilidad)
  utilidades.py             # HTTP con reintentos, limpieza de texto, logging
  controlador.py            # núcleo PARALELO: pool de hilos + cola
  almacenamiento.py         # guardado JSON/CSV + deduplicación
  extractores/
    base.py                 # ExtractorBase (contrato común)
    hackernews.py  mastodon.py  lemmy.py  devto.py
datos/                      # datasets generados (JSON + CSV)
evidencias/                 # logs de cada ejecución
```
