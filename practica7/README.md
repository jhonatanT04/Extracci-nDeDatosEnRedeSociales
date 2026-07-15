# Análisis paralelo de sentimientos con LLM — Práctica 07

**Asignatura:** Computación Paralela — Universidad Politécnica Salesiana (UPS)
**Práctica:** Análisis paralelo de sentimientos sobre datos de redes sociales
**Continúa de:** Práctica 06 (extracción paralela) — ver [`README.md`](../README.md)

Sistema que clasifica **en paralelo** el sentimiento de opiniones extraídas de
**X (Twitter), Facebook y TikTok** sobre el diseño "Ecos del Sol" del nuevo
Museo Nacional del Ecuador, usando **modelos de lenguaje (LLM)** como motor de
procesamiento de lenguaje natural.

Soporta **dos proveedores** de LLM:
- **Groq** (tier gratuito, modelos Llama) — rápido y sin costo.
- **OpenAI** (modelos GPT) — mayor precisión en español.

---

## 1. Objetivo de esta práctica

Tomar el dataset textual generado en la Práctica 06 (`datos/dataset_*.json`,
con opiniones de **X/Twitter, Facebook y TikTok** sobre el diseño "Ecos del
Sol" del nuevo Museo Nacional del Ecuador) y clasificar cada texto según su
sentimiento, de forma **paralela**, conservando la trazabilidad hasta la
fuente y la consulta original.

---

## 2. Por qué un LLM como modelo de análisis

La consigna permite usar "modelos de lenguaje, APIs, librerías de PLN,
modelos preentrenados, clasificadores tradicionales, modelos locales u otra
alternativa justificada". Se eligió un **LLM servido vía API** porque:

- **No requiere GPU ni descargar pesos de modelo**: todo el cómputo pesado
  ocurre en el servidor del proveedor, el proyecto solo hace peticiones HTTP.
- **Excelente comprensión del español** (sarcasmo, comparaciones, dobles
  negaciones, jerga de redes sociales) — los LLMs modernos superan a los
  clasificadores léxicos simples en matices lingüísticos.
- **Respuesta estructurada (JSON mode)**: se le pide al modelo que responda
  en un formato fijo, lo que simplifica el post-procesamiento.

### Dos proveedores disponibles

| Proveedor | Modelo por defecto | Ventaja principal | Variable de entorno |
|---|---|---|---|
| **Groq** | `llama-3.1-8b-instant` | Tier gratuito, muy rápido | `GROQ_API_KEY` |
| **OpenAI** | `gpt-4o-mini` | Alta precisión en español | `OPENAI_API_KEY` |

Ambos comparten la misma interfaz (`.clasificar(texto) → ResultadoSentimiento`),
así que el controlador paralelo los trata de forma idéntica (**polimorfismo**).

**Contrapartida asumida:** al ser una API externa, cada clasificación implica
una llamada de red (latencia + posible rate-limit). Esto es precisamente lo
que motiva la estrategia de paralelismo de la sección 4.

---

## 3. Estructura del proyecto

```
practica7/
  main.py                            # punto de entrada (CLI) con --proveedor groq|openai
  modelo/
    __init__.py                      # fábrica crear_analizador() + exporta ambos
    analizador_groq.py               # cliente API de Groq (modelos Llama)
    analizador_openai.py             # cliente API de OpenAI (modelos GPT)
  controlador_sentimientos.py        # núcleo PARALELO: pool de hilos + cola
  modelos_sentimiento.py             # RegistroSentimiento (modelo de datos)
  almacenamiento_sentimientos.py     # guardado JSON + carga de datasets
  utilidades.py                      # logger thread-safe + limpieza de texto
  datos/
    dataset_prueba.json              # 18 registros inventados para pruebas
    sentimientos_*.json              # resultados generados (se crean al ejecutar)
  .env                               # claves de API (NO se sube a git)
  .env.example                       # plantilla para las claves
  .venv/                             # entorno virtual Python
  requirements.txt                   # dependencias mínimas
  README.md                          # este archivo
```

### `modelo/` — Dos analizadores, una interfaz

Ambos analizadores encapsulan todo el trato con su API respectiva. El resto
del proyecto solo llama a `.clasificar(texto)`:

```python
from modelo import crear_analizador

# Usar Groq (por defecto)
analizador = crear_analizador("groq")
resultado = analizador.clasificar("Qué vergüenza ese diseño...")
# resultado.sentimiento    -> "negativo"
# resultado.justificacion  -> "El texto critica abiertamente el diseño"
# resultado.modelo         -> "llama-3.1-8b-instant"

# Usar OpenAI
analizador = crear_analizador("openai")
resultado = analizador.clasificar("Me encanta el nuevo museo!")
# resultado.modelo         -> "gpt-4o-mini"
```

**Qué hace internamente `clasificar()`:**

1. Arma un mensaje de **sistema** (`_SYSTEM_PROMPT`) que le dice al modelo
   exactamente qué categorías existen y en qué formato JSON debe responder.
2. Envía el texto del usuario como mensaje de **usuario** (recortado a 2000
   caracteres, más que suficiente para un post/comentario de red social).
3. Pide `response_format: {"type": "json_object"}` — el proveedor fuerza al
   modelo a devolver JSON válido.
4. Si la API responde **429 (rate limit)**, espera y reintenta (hasta
   `max_reintentos` veces, con backoff).
5. Si la categoría devuelta no es válida, o hay error de red/parseo,
   cae a `"no_clasificable"` en vez de romper el programa.

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
añadir, y además `no_clasificable` sirve como salida segura ante errores.

---

## 4. Paralelismo: `controlador_sentimientos.py`

**Técnica elegida: hilos (`ThreadPoolExecutor`) + cola productor/consumidor**
— el mismo patrón que la Práctica 06, y por la misma razón:

> Clasificar un texto es una llamada HTTP al LLM: el programa pasa la mayor
> parte del tiempo **esperando la respuesta de red**, no calculando
> (I/O-bound). En Python, mientras un hilo espera una respuesta de red,
> libera el GIL y otro hilo puede avanzar. Con **procesos** se pagaría el
> costo de crear procesos y serializar datos sin ninguna ganancia, porque el
> cuello de botella es la red, no la CPU.

### Flujo paralelo:

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
  analizador.clasificar(texto)  (Groq o OpenAI, por cada texto del bloque)
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
   procesa **todo el bloque de su fuente**, llamando al LLM texto por texto.
   Como hay un hilo por red, **las tres redes se clasifican al mismo
   tiempo**, no una tras otra.
3. **Cola (`queue.Queue`)**: cada hilo-productor empuja sus
   `RegistroSentimiento` a la cola a medida que el LLM responde. Un hilo
   **consumidor** central los recolecta — patrón **Productor/Consumidor**.
4. **Aislamiento de fallos**: cada texto que falla cae a `no_clasificable`
   en vez de lanzar una excepción.

También existe `ejecutar_secuencial()` para **medir el speedup** con
`--benchmark`.

---

## 5. Trazabilidad y almacenamiento

### Modelo de datos: `RegistroSentimiento` (`modelos_sentimiento.py`)

Cada resultado conserva el enlace a su origen exacto:

| Campo | De dónde sale |
|---|---|
| `fuente`, `consulta`, `texto`, `id_unico` | Copiados del `Registro` original de la Práctica 06 |
| `autor`, `fecha_publicacion`, `url`, `metricas` | Metadatos heredados |
| `sentimiento` | Categoría devuelta por el LLM |
| `justificacion` | Explicación breve que da el modelo (auditable) |
| `modelo` | Nombre del modelo usado (ej. `llama-3.1-8b-instant`, `gpt-4o-mini`) |
| `clasificado_en` | Marca de tiempo UTC |

### Guardado: `almacenamiento_sentimientos.py`

`guardar()` escribe un JSON `datos/sentimientos_<fecha_hora>.json` con:

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
  "registros": [ /* RegistroSentimiento por texto clasificado */ ]
}
```

---

## 6. Dataset de prueba: `datos/dataset_prueba.json`

18 registros **inventados** (6 por red: X-Twitter, Facebook, TikTok), con
opiniones variadas sobre "Ecos del Sol", en el mismo formato que produce la
Práctica 06. Sirve para probar el pipeline completo sin depender de Selenium.

---

## 7. Configuración: `.env`

```bash
# Groq (tier gratuito)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

- `main.py` carga el `.env` local **y** el `.env` de la raíz del proyecto,
  así que las claves que ya tengas configuradas se reutilizan.
- `.env` está en `.gitignore`: **las claves nunca se suben al repositorio**.

---

## 8. Cómo ejecutarlo

```bash
# 1) Activar el entorno virtual
cd practica7
source .venv/bin/activate

# 2) (Si es la primera vez) Instalar dependencias
pip install -r requirements.txt

# 3) Configurar claves en .env (ya copiadas de la raíz si existían)

# 4) Ejecutar con Groq (por defecto)
python3 main.py --archivo datos/dataset_prueba.json

# 5) Ejecutar con OpenAI
python3 main.py --archivo datos/dataset_prueba.json --proveedor openai

# 6) Benchmark: comparar tiempos secuencial vs paralelo
python3 main.py --archivo datos/dataset_prueba.json --benchmark

# 7) Solo modo secuencial (referencia)
python3 main.py --archivo datos/dataset_prueba.json --secuencial

# 8) Ver ayuda
python3 main.py --help
```

### Evidencia de ejecución real (Groq, dataset de prueba, 18 registros)

```
======================================================================
  ANÁLISIS PARALELO DE SENTIMIENTOS (GROQ)
  Práctica de Laboratorio 07 — Computación Paralela
======================================================================
Problemática:
  ¿Cuál es la percepción de los usuarios de redes sociales sobre el diseño
  ganador ('Ecos del Sol') del nuevo Museo Nacional del Ecuador?

Registros a clasificar: 18
Fuentes: Facebook, TikTok, X-Twitter
Proveedor LLM: GROQ

21:38:57 | INFO | Sentimiento_0  | Clasificando 6 textos de X-Twitter...
21:38:57 | INFO | Sentimiento_1  | Clasificando 6 textos de Facebook...
21:38:57 | INFO | Sentimiento_2  | Clasificando 6 textos de TikTok...
21:38:59 | INFO | MainThread     | PARALELO: 18 textos clasificados en 2.22 s

----------------------------------------------------------------------
RESUMEN POR FUENTE Y SENTIMIENTO
----------------------------------------------------------------------
  Facebook:   negativo: 3   neutral: 2   positivo: 1
  TikTok:     negativo: 2   neutral: 2   positivo: 2
  X-Twitter:  mixto: 1   negativo: 2   neutral: 2   positivo: 1

Resultados guardados en: datos/sentimientos_20260714_213859.json
```

Se observa que los **tres hilos** (`Sentimiento_0/1/2`) arrancan en el mismo
segundo y las 18 clasificaciones terminan en **2.22 s en total**, evidencia
de que las tres fuentes se procesaron **al mismo tiempo**.

---

## 9. Relación con el resto del proyecto

- **Entrada:** el campo `texto` de cada `Registro` de la Práctica 06.
- **Salida:** `datos/sentimientos_<fecha>.json`, con cada texto clasificado
  y trazable a su `fuente` y `consulta` originales.
- **Siguiente paso (proyecto final):** con `resumen_por_fuente` ya agregado,
  se puede graficar la distribución de sentimiento por red social,
  cruzarla con `metricas` para ponderar por relevancia, y con
  `fecha_publicacion` para storytelling temporal.
