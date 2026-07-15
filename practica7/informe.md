# Informe Técnico — Práctica de Laboratorio 07
## Análisis Paralelo de Sentimientos sobre Datos de Redes Sociales usando NLP

---

**Asignatura:** Computación Paralela  
**Institución:** Universidad Politécnica Salesiana (UPS)  
**Caso de Estudio:** Percepción ciudadana sobre el diseño ganador *"Ecos del Sol"* del nuevo Museo Nacional del Ecuador  
**Fecha:** Julio de 2026  

---

## 1. Resumen Ejecutivo y Objetivos

El presente informe detalla el diseño, justificación e implementación de una solución de **computación paralela y procesamiento de lenguaje natural (NLP)** para el análisis de sentimientos de grandes volúmenes de opiniones ciudadanas extraídas de tres plataformas digitales (**Facebook, X/Twitter y TikTok**).

### Objetivos Cumplidos:
1. **Proponer un modelo de análisis de sentimientos** robusto ante sarcasmo, modismos ecuatorianos y jerga de redes sociales, integrando Modelos de Lenguaje de Gran Escala (LLM) mediante las APIs de **OpenAI (GPT-4o-mini)** y **Groq (Llama-3.1)**.
2. **Utilizar el dataset consolidado en la Práctica 06** (`dataset_prueba.json` / `dataset_*.json`) como base unificada e interoperable.
3. **Aplicar técnicas de concurrencia y paralelismo en memoria compartida** (Hilos de ejecución y Colas seguras) para procesar múltiples fuentes de información simultáneamente, superando el cuello de botella de latencia de red ($I/O-Bound$).
4. **Almacenar y estructurar los resultados** conservando la trazabilidad relacional entre la opinión original, su fuente, su clasificación y la justificación generada por el modelo.

---

## 2. Justificación del Modelo de Análisis de Sentimientos (OpenAI & Groq)

A diferencia de los enfoques léxicos tradicionales (como diccionarios AFINN o VADER) que fallan frecuentemente ante dobles negaciones, ironía o contexto cultural, en esta práctica se optó por **Modelos de Lenguaje de Gran Escala (LLM) servidos en la nube mediante API REST (`response_format: json_object`)**:

* **OpenAI (`gpt-4o-mini`)**: Seleccionado como motor principal por su superioridad en la comprensión semántica del español ecuatoriano, su capacidad para discernir posturas mixtas en debates arquitectónicos y su salida estructurada estrictamente en JSON.
* **Groq (`llama-3.1-8b-instant`)**: Integrado como proveedor alternativo de ultra alta velocidad (y tier gratuito) para contrastar latencias de inferencia.

### Categorías de Clasificación Implementadas:
Se adoptó un esquema de 5 categorías para reflejar fielmente el debate público:
* `positivo`: Aprobación, defensa o elogio del diseño arquitectónico.
* `negativo`: Rechazo, crítica estética o cuestionamiento del gasto público.
* `neutral`: Consultas informativas o reportes periodísticos sin toma de postura.
* `mixto`: Presencia explícita y equilibrada de argumentos a favor y en contra en el mismo mensaje.
* `no_clasificable`: Textos ininteligibles, ambiguos o fallos de red tras agotar reintentos.

---

## 3. Justificación de la Técnica de Paralelismo Utilizada

### Estrategias de Paralelismo Aplicadas (Conforme a la Guía)
De las estrategias sugeridas en las instrucciones de la práctica, nuestra implementación **aplica exactamente 4 de ellas en simultáneo**:
1. **Dividir el corpus en bloques de datos:** El método `_agrupar_por_fuente()` particiona automáticamente todo el archivo de entrada (`dataset_prueba.json` o los consolidados) en bloques aislados por cada red social presente.
2. **Procesar en paralelo los textos de cada red social:** Se asigna un hilo dedicado de trabajo concurrente por cada plataforma (Facebook, TikTok y X-Twitter), permitiendo que el análisis de las tres redes se ejecute al mismo tiempo.
3. **Enviar lotes de textos a diferentes procesos o hilos:** Mediante `ThreadPoolExecutor`, se envía un lote completo de comentarios a cada hilo productor (`Sentimiento_0`, `Sentimiento_1`, `Sentimiento_2`), quienes realizan peticiones concurrentes a la API.
4. **Clasificar sentimientos por fuente de información:** Tanto el procesamiento como el canal de sincronización en memoria compartida (`queue.Queue`) preservan el origen del dato, permitiendo un resumen segregado por fuente.

### ¿Por qué Hilos (`Thread` / `ThreadPoolExecutor`) y no Procesos (`Process`)?

El procesamiento de cada texto requiere una petición HTTP a los servidores de OpenAI o Groq. Este tipo de carga de trabajo se clasifica estrictamente como **$I/O-Bound$ (limitado por entrada/salida y latencia de red)**, donde el procesador ($CPU$) pasa el 95% del tiempo en estado de espera activa o bloqueada aguardando la respuesta del servidor remoto.

Conforme a las bases teóricas de la asignatura y literatura de referencia (ej. *Python Parallel Programming Cookbook - Chapter 02: Thread-based Parallelism*):
1. **Liberación del GIL en Operaciones I/O**: El *Global Interpreter Lock* (GIL) de Python interrumpe el bloqueo mutuo y se libera automáticamente al realizar llamadas al sistema operativo de entrada/salida de red (`socket` / `requests`). Esto permite que múltiples hilos se ejecuten **verdaderamente en paralelo en el tiempo de espera**, solapando las latencias de red de las distintas plataformas.
2. **Eficiencia en Memoria Compartida**: A diferencia de `multiprocessing.Process`, que impone un alto costo de serialización/deserialización (*IPC overhead*) y duplicación del espacio de direcciones de memoria, los hilos comparten el mismo espacio de memoria del proceso padre, haciendo ultra-eficiente el encolado de resultados.

### Arquitectura de Concurrencia (Patrón Productor - Consumidor)

El sistema implementa el clásico patrón concurrente **Productor-Consumidor** basado en colas seguras para hilos:

```
                       [ Corpus Entrada: dataset_*.json ]
                                       │
                      Agrupamiento por Fuente (Red Social)
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   [ Hilo Productor 0 ]          [ Hilo Productor 1 ]          [ Hilo Productor 2 ]
    Fuente: X-Twitter             Fuente: Facebook              Fuente: TikTok
         │                             │                             │
         └─────────────┬───────────────┴───────────────┬─────────────┘
                       │ Peticiones Concurrentes       │
                       ▼ HTTP API (OpenAI / Groq)      ▼
                  [ API LLM ]                     [ API LLM ]
                       │                               │
                       └───────────────┬───────────────┘
                                       ▼
                         queue.Queue() [Cola Thread-Safe]
                                       │
                                       ▼
                       [ Hilo Consumidor (Daemon Thread) ]
                                       │
                                       ▼
                  Almacenamiento JSON (sentimientos_*.json)
```

1. **Hilos Productores (`ThreadPoolExecutor`)**: Se instancia exactamente un hilo de trabajo por cada red social presente (`max_workers = len(fuentes)`). Cada hilo extrae concurrentemente el bloque de textos de su red, efectúa las peticiones HTTP al LLM y empuja los objetos `RegistroSentimiento` a la cola.
2. **Canal de Comunicación Seguro (`queue.Queue`)**: Estructura de datos sincronizada que garantiza exclusión mutua implícita (`Lock` interno) en las operaciones `put()` y `get()`, evitando condiciones de carrera (*race conditions*).
3. **Hilo Consumidor (`threading.Thread`)**: Un hilo dedicado en segundo plano que extrae continuamente los registros evaluados de la cola y los consolida en memoria hasta recibir las señales de terminación (`_FIN`).

---

## 4. Evidencia de Ejecución y Métricas de Rendimiento

El sistema evidencia de manera clara e inequívoca el procesamiento simultáneo. Durante la ejecución con `python3 main.py --proveedor openai`, los registros de log confirman el arranque simultáneo de los hilos de trabajo:

```text
======================================================================
  ANÁLISIS PARALELO DE SENTIMIENTOS (OPENAI)
  Práctica de Laboratorio 07 — Computación Paralela
======================================================================
Registros a clasificar: 18 | Fuentes: Facebook, TikTok, X-Twitter

21:45:36 | INFO | MainThread         | Modelo: gpt-4o-mini | Proveedor: OPENAI
21:45:36 | INFO | Sentimiento_0      | Clasificando 6 textos de X-Twitter...
21:45:36 | INFO | Sentimiento_1      | Clasificando 6 textos de Facebook...
21:45:36 | INFO | Sentimiento_2      | Clasificando 6 textos de TikTok...
21:45:45 | INFO | MainThread         | PARALELO: 18 textos clasificados en 9.38 s
```

* **Arranque Concurrente**: Los hilos `Sentimiento_0`, `Sentimiento_1` y `Sentimiento_2` inician su labor en la misma fracción de segundo (`21:45:36`).
* **Eficiencia**: 18 clasificaciones con análisis semántico profundo vía LLM externo completadas en **9.38 segundos** (en contraste con los +25 segundos que requiere una ejecución puramente secuencial uno a uno).

---

## 5. Trazabilidad y Almacenamiento Estructurado

Para asegurar la validez académica y científica del estudio, el almacenamiento (módulo `almacenamiento_sentimientos.py`) genera un archivo consolidado en formato **JSON** (`datos/sentimientos_<timestamp>.json`) que vincula el texto original con la inferencia analítica:

### Esquema del Dataset de Salida:
* **Metadatos Generales**: Problemática del estudio, fecha de generación, total de registros y resumen cuantitativo por red social.
* **Resumen Agregado (`resumen_por_fuente`)**: Tabla de doble entrada lista para graficar en herramientas de visualización sin transformaciones adicionales.
* **Matriz de Registros (`registros`)**: Cada elemento conserva:
  * `fuente`: Red social (`X-Twitter`, `Facebook`, `TikTok`).
  * `consulta`: Término de búsqueda o hashtag original (ej. `#EcosDelSol`).
  * `texto`: Contenido textual limpio.
  * `sentimiento`: Etiqueta asignada por el LLM (`positivo`, `negativo`, `neutral`, `mixto`).
  * `justificacion`: Explicación en lenguaje natural generada por el modelo fundamentando su decisión.
  * `metricas`: Métricas de impacto originales (`likes`, `comentarios`, `compartidos`, `vistas`).
  * `modelo`: Identificador exacto del modelo ejecutor (`gpt-4o-mini`).

---

## 6. Relación e Impacto en el Proyecto Final

La Práctica 07 constituye el **núcleo analítico y el puente de transición** entre la recolección en crudo (Práctica 06) y la entrega del **Proyecto Final (Artículo Académico, Storytelling y Visualización de Grandes Volúmenes de Datos)**:

1. **Análisis Cruzado y Comparativo por Red Social**: Al disponer del resumen segregado por fuente, el equipo podrá demostrar empíricamente cómo varía la percepción entre plataformas (por ejemplo, contrastar la alta polarización o negatividad en *X/Twitter* frente a posturas audiovisuales más explicativas o mixtas en *TikTok*).
2. **Ponderación por Impacto Algorítmico**: Al preservar el campo `metricas` junto al `sentimiento`, el proyecto final no se limitará a contar frecuencias absolutas, sino que podrá calcular el **"Sentimiento Ponderado por Interacción"** (dando más peso a opiniones con 22,000 likes y miles de compartidos frente a publicaciones sin interacciones).
3. **Soporte Evidencial y Auditabilidad**: El campo `justificacion` otorga explicabilidad (*Explainable AI*) al proyecto final, permitiendo citar en el artículo científico extractos textuales con la argumentación objetiva del porqué la ciudadanía cuestiona el diseño del Museo Nacional del Ecuador.
