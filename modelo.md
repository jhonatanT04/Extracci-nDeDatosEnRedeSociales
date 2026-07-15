# Análisis paralelo de sentimientos con Groq — Práctica 07

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Práctica:** Análisis paralelo de sentimientos sobre datos de redes sociales
**Continúa de:** Práctica 06 (extracción paralela) — ver [`README.md`](README.md)

Este documento explica cómo funciona la parte de **análisis de sentimientos**:
qué hace cada pieza, por qué se usó la API de **Groq**, cómo se paraleliza el
procesamiento y cómo se guardan y trazan los resultados.

---

## 1. Objetivo de esta parte

Tomar el dataset textual generado en la Práctica 06 (`datos/dataset_*.json`,
con opiniones de **X/Twitter, Facebook y TikTok** sobre el diseño "Ecos del
Sol" del nuevo Museo Nacional del Ecuador) y clasificar cada texto según su
sentimiento, de forma **paralela**, conservando la trazabilidad hasta la
fuente y la consulta original.

---

## 2. Por qué Groq como modelo de análisis

La consigna permite usar "modelos de lenguaje, APIs, librerías de PLN,
modelos preentrenados, clasificadores tradicionales, modelos locales u otra
alternativa justificada". Se eligió **la API gratuita de Groq** (modelos
open-weight tipo Llama servidos a muy alta velocidad) porque:

- **No requiere GPU ni descargar pesos de modelo**: todo el cómputo pesado
  ocurre en el servidor de Groq, el proyecto solo hace peticiones HTTP.
- **Tier gratuito suficiente** para el volumen de esta práctica (decenas o
  centenas de textos cortos).
- **Mejor comprensión del español** (sarcasmo, comparaciones, dobles
  negaciones, jerga de redes sociales) que un enfoque léxico simple
  (contar palabras positivas/negativas de un diccionario).
- **Respuesta estructurada (JSON)**: se le pide al modelo que responda en un
  formato fijo, lo que simplifica el post-procesamiento y evita depender de
  heurísticas de parsing de texto libre.

**Contrapartida asumida:** al ser una API externa, cada clasificación implica
una llamada de red (latencia + límite de tasa del tier gratuito). Esto es
precisamente lo que motiva la estrategia de paralelismo de la sección 4.

---

## 3. Dónde vive el modelo: carpeta `modelo/`

```
modelo/
  __init__.py            # expone AnalizadorSentimientoGroq y ResultadoSentimiento
  analizador_groq.py      # la clase que habla con la API de Groq
```

### `AnalizadorSentimientoGroq` (`modelo/analizador_groq.py`)

Es la única clase de esta carpeta. Encapsula todo el trato con la API para
que el resto del proyecto (`src/controlador_sentimientos.py`) no sepa nada
de HTTP, JSON de Groq, ni reintentos: solo llama a `.clasificar(texto)`.

```python
analizador = AnalizadorSentimientoGroq()
resultado = analizador.clasificar("Qué vergüenza ese diseño...")
# resultado.sentimiento    -> "negativo"
# resultado.justificacion  -> "El texto critica abiertamente el diseño"
# resultado.modelo         -> "llama-3.1-8b-instant"
```

**Qué hace internamente `clasificar()`:**

1. Arma un mensaje de **sistema** (`_SYSTEM_PROMPT`) que le dice al modelo
   exactamente qué categorías existen y en qué formato JSON debe responder.
2. Envía el texto del usuario como mensaje de **usuario** (recortado a 2000
   caracteres, más que suficiente para un post/comentario de red social).
3. Pide `response_format: {"type": "json_object"}` — Groq fuerza al modelo a
   devolver JSON válido, evitando tener que parsear texto libre.
4. Si Groq responde **429 (rate limit)** del tier gratuito, espera el tiempo
   indicado en `Retry-After` (o un backoff simple) y reintenta, hasta
   `max_reintentos` veces.
5. Si la categoría devuelta no es una de las válidas, o hay cualquier error
   de red/parseo tras agotar los reintentos, cae a `"no_clasificable"` en vez
   de romper el programa — un texto problemático no debe tumbar la
   clasificación de los demás.

### Categorías de sentimiento

| Categoría | Significado |
|---|---|
| `positivo` | Aprueba, felicita o defiende el diseño/tema |
| `negativo` | Critica, rechaza o se queja |
| `neutral` | Informa o pregunta sin tomar postura |
| `mixto` | Mezcla claramente argumentos a favor y en contra |
| `no_clasificable` | Texto ambiguo, sin opinión o que falló al clasificar |

Las tres primeras son las exigidas por la consigna; `mixto` y
`no_clasificable` son las categorías opcionales que la consigna permite
añadir, y además `no_clasificable` sirve como salida segura ante errores de
la API.

---

## 4. Paralelismo: `src/controlador_sentimientos.py`

**Técnica elegida: hilos (`ThreadPoolExecutor`) + cola productor/consumidor**
— el mismo patrón que la Práctica 06, y por la misma razón:

> Clasificar un texto es una llamada HTTP a Groq: el programa pasa la mayor
> parte del tiempo **esperando la respuesta de red**, no calculando
> (I/O-bound). En Python, mientras un hilo espera una respuesta de red,
> libera el GIL y otro hilo puede avanzar. Con **procesos** se pagaría el
> costo de crear procesos y serializar datos sin ninguna ganancia, porque el
> cuello de botella es la red, no la CPU.

Flujo:

```
        registros (dataset_*.json de la Práctica 06)
                         │
              agrupar por 'fuente'
                         │
      ┌──────────────────┼──────────────────┐
      ▼                  ▼                  ▼
 bloque X-Twitter   bloque Facebook     bloque TikTok      ← 1 hilo por fuente
      │                  │                  │                (PRODUCTORES)
      ▼                  ▼                  ▼
  AnalizadorSentimientoGroq.clasificar(texto)  (por cada texto del bloque)
      │                  │                  │
      └──────────────────┼──────────────────┘
                         ▼
                  queue.Queue()            ← canal thread-safe
                         ▼
              Consumidor (hilo aparte)      ← recolecta RegistroSentimiento
                         ▼
        almacenamiento_sentimientos.guardar()
```

1. **`_agrupar_por_fuente`**: divide el corpus en **bloques** (uno por red
   social) — la consigna lo sugiere explícitamente ("dividir el corpus en
   bloques de datos" / "clasificar sentimientos por fuente").
2. **Pool de hilos** (`ThreadPoolExecutor(max_workers=n_fuentes)`): cada hilo
   procesa **todo el bloque de su fuente**, llamando a Groq texto por texto.
   Como hay un hilo por red, **las tres redes se clasifican al mismo
   tiempo**, no una tras otra.
3. **Cola (`queue.Queue`)**: cada hilo-productor empuja sus
   `RegistroSentimiento` a la cola a medida que Groq responde. Un hilo
   **consumidor** central los recolecta — patrón **Productor/Consumidor**,
   igual que en la Práctica 06.
4. **Aislamiento de fallos**: como cada texto que falla cae a
   `no_clasificable` en vez de lanzar una excepción, un problema con un
   texto (o una racha de rate-limit) no detiene el resto del bloque ni de
   las otras fuentes.

También existe `ejecutar_secuencial()`, que clasifica los mismos registros
uno por uno sin hilos, solo para **medir el speedup** con `--benchmark`
(igual que en la Práctica 06).

---

## 5. Trazabilidad y almacenamiento

### Modelo de datos: `RegistroSentimiento` (`src/modelos_sentimiento.py`)

Cada resultado conserva el enlace a su origen exacto:

| Campo | De dónde sale |
|---|---|
| `fuente`, `consulta`, `texto`, `id_unico` | Copiados del `Registro` original de la Práctica 06 |
| `autor`, `fecha_publicacion`, `url`, `metricas` | Metadatos heredados, útiles para ponderar/filtrar después |
| `sentimiento` | Categoría devuelta por Groq |
| `justificacion` | Explicación breve que da el modelo (auditable) |
| `modelo` | Nombre del modelo de Groq usado (ej. `llama-3.1-8b-instant`) |
| `clasificado_en` | Marca de tiempo UTC de cuándo se clasificó |

Así, cualquier fila del resultado final responde a la vez: *¿qué se dijo?*,
*¿dónde?*, *¿con qué búsqueda se encontró?* y *¿qué sentimiento se le
asignó y por qué?*.

### Guardado: `src/almacenamiento_sentimientos.py`

`guardar(resultados, problematica)` escribe **un único JSON**
`datos/sentimientos_<fecha_hora>.json` con:

```json
{
  "problematica": "...",
  "generado_en": "...",
  "total_registros": 18,
  "resumen_por_fuente": {
    "X-Twitter": { "negativo": 2, "neutral": 2, "positivo": 1, "mixto": 1 },
    "Facebook":  { "negativo": 3, "neutral": 2, "positivo": 1 },
    "TikTok":    { "negativo": 2, "neutral": 2, "positivo": 2 }
  },
  "registros": [ /* un RegistroSentimiento por texto clasificado */ ]
}
```

El `resumen_por_fuente` es exactamente el insumo que necesita la etapa de
**visualización / comparación entre redes / storytelling** del proyecto
final: ya viene agregado por red y por sentimiento.

---

## 6. Carga del dataset de entrada: `cargar_dataset()`

Añadido en `src/almacenamiento.py`. `main_sentimientos.py` llama a
`cargar_dataset(ruta)`:

- Si se pasa `--archivo`, usa exactamente ese JSON.
- Si no, busca en `datos/` todos los archivos `dataset_*.json` y toma el
  **más reciente** (por fecha de modificación, no por nombre).
- Si no encuentra ninguno, lanza un error claro indicando que hay que correr
  la Práctica 06 (`python3 main.py`) o usar `datos/dataset_prueba.json`.

---

## 7. Configuración: `.env`

```
GROQ_API_KEY=...   # tu clave gratuita de https://console.groq.com/keys
GROQ_MODEL=llama-3.1-8b-instant
```

- `main_sentimientos.py` llama a `load_dotenv()` al inicio, así que basta con
  pegar la clave en `.env` — no hace falta exportar variables de entorno
  manualmente.
- `.env` está en `.gitignore`: **la clave nunca se sube al repositorio**.
- `GROQ_MODEL` es opcional; si se omite, se usa `llama-3.1-8b-instant`
  (rápido, ideal para este volumen). `llama-3.3-70b-versatile` es más
  preciso pero más lento y con menor límite gratuito.

---

## 8. Dataset de prueba: `datos/dataset_prueba.json`

Mientras no se corra el scraping real de la Práctica 06, existe un dataset
**inventado** con 18 registros (6 por red: X-Twitter, Facebook, TikTok),
con opiniones variadas (positivas, negativas, neutrales y una mixta) sobre
el caso "Ecos del Sol", en el mismo formato que produce
`almacenamiento.guardar()`. Sirve para probar el pipeline completo de punta
a punta sin depender de Selenium ni de sesiones iniciadas.

---

## 9. Cómo ejecutarlo

```bash
# Instalar dependencias (incluye requests y python-dotenv)
uv sync                       # o: pip install -r requirements.txt

# Pegar la clave de Groq en .env (una sola vez)

# Ejecutar con el dataset de prueba
uv run python3 main_sentimientos.py --archivo datos/dataset_prueba.json

# Ejecutar con el dataset real más reciente de la Práctica 06
uv run python3 main_sentimientos.py

# Comparar tiempos secuencial vs paralelo (evidencia de speedup)
uv run python3 main_sentimientos.py --archivo datos/dataset_prueba.json --benchmark

# Solo modo secuencial (referencia)
uv run python3 main_sentimientos.py --archivo datos/dataset_prueba.json --secuencial
```

### Evidencia de ejecución real (dataset de prueba, 18 registros)

```
21:05:08 | INFO | Sentimiento_0 | Clasificando 6 textos de X-Twitter...
21:05:08 | INFO | Sentimiento_1 | Clasificando 6 textos de Facebook...
21:05:08 | INFO | Sentimiento_2 | Clasificando 6 textos de TikTok...
21:05:10 | INFO | MainThread    | PARALELO: 18 textos clasificados en 2.21 s

RESUMEN POR FUENTE Y SENTIMIENTO
  Facebook:   negativo: 3   neutral: 2   positivo: 1
  TikTok:     negativo: 2   neutral: 2   positivo: 2
  X-Twitter:  mixto: 1   negativo: 2   neutral: 2   positivo: 1

Resultados guardados en: datos/sentimientos_20260714_210510.json
```

Se observa que los **tres hilos** (`Sentimiento_0/1/2`) arrancan en el mismo
segundo (`21:05:08`) y las 18 clasificaciones (18 llamadas a la API de Groq)
terminan en **2.21 s en total**, evidencia de que las tres fuentes se
procesaron **al mismo tiempo** y no una tras otra.

---

## 10. Relación con el resto del proyecto

- **Entrada:** el campo `texto` de cada `Registro` de la Práctica 06.
- **Salida:** `datos/sentimientos_<fecha>.json`, con cada texto ya
  clasificado y aún trazable a su `fuente` y `consulta` originales.
- **Siguiente paso (proyecto final):** con `resumen_por_fuente` ya agregado,
  se puede graficar directamente la distribución de sentimiento por red
  social, cruzarla con `metricas` (likes/comentarios) para ponderar por
  relevancia, y con `fecha_publicacion` para un storytelling temporal de la
  controversia.
