# Informe Técnico — Práctica de Laboratorio 07
## Análisis Paralelo de Sentimientos sobre Datos de Redes Sociales usando NLP

---

**Asignatura:** Computación Paralela  
**Institución:** Universidad Politécnica Salesiana (UPS)  
**Autores:** Justin Lucero, Jhonatan Tacuri, Wilmer Merchán  
**Caso de Estudio:** Percepción ciudadana sobre el diseño ganador *"Ecos del Sol"* del nuevo Museo Nacional del Ecuador (MUNA)  
**Repositorio GitHub:** [https://github.com/jhonatanT04/Extracci-nDeDatosEnRedeSociales.git](https://github.com/jhonatanT04/Extracci-nDeDatosEnRedeSociales.git)  
**Fecha:** Julio de 2026  

---

## 1. Resumen Ejecutivo y Objetivos

El presente informe técnico detalla el diseño, justificación, arquitectura e implementación de un sistema concurrente y paralelo para el **procesamiento de lenguaje natural (NLP) y análisis de sentimientos** sobre grandes volúmenes de datos extraídos de redes sociales (**Facebook, TikTok y YouTube**).

La práctica toma como insumo directo el corpus consolidado en la **Práctica de Laboratorio 06**, procesando en paralelo las **508 opiniones reales recolectadas** mediante Modelos de Lenguaje de Gran Escala (LLM) en la nube (**OpenAI GPT-4o-mini** y **Groq Llama-3.1-8b-instant**). Además, incorpora un **Dashboard Visual Interactivo** (`Dark Mode & Glassmorphism`) para la exploración semántica, trazabilidad y explicabilidad (*Explainable AI*) de los resultados.

### Objetivos Cumplidos (Conforme a la Guía de Evaluación):
1. **Uso del dataset real de la Práctica 06 (0.5 pts):** Carga e integración automática de los 508 registros reales (`datos/dataset_20260715_110053.json`) con trazabilidad completa.
2. **Propuesta y justificación del modelo NLP (0.8 pts):** Justificación técnica del uso de LLMs con respuesta en formato JSON estricto (`response_format: json_object`) y definición de 5 categorías de clasificación para el debate arquitectónico/social.
3. **Diseño e implementación de solución paralela (1.7 pts):** Arquitectura híbrida en dos niveles (Hilos por Fuente + Sub-pool concurrente para lotes de alto volumen) y patrón concurrente **Productor-Consumidor** robusto.
4. **Uso adecuado de técnicas de concurrencia (0.8 pts):** Justificación teórica de la liberación del *Global Interpreter Lock* (GIL) en operaciones $I/O-Bound$ usando `threading` y `queue.Queue`.
5. **Almacenamiento estructurado dual (0.5 pts):** Exportación relacional en JSON preservando metadatos y métricas tanto en la carpeta de la práctica como en la raíz del proyecto.
6. **Evidencia de ejecución y resultados (0.4 pts):** Demostración empírica del procesamiento paralelo de 508 textos en **49.59 segundos**, tablas estadísticas por plataforma e interfaz gráfica funcional.
7. **Relación con el Proyecto Final (0.3 pts):** Articulación de los resultados clasificados con la visualización, storytelling y redacción del artículo científico.

---

## 2. Uso Correcto del Dataset Generado en la Práctica 06 (`0.5 pts`)

El sistema ha sido estructurado para garantizar la máxima interoperabilidad entre las fases del proyecto. El módulo `almacenamiento_sentimientos.py` (funciones `listar_datasets()` y `cargar_dataset()`) implementa un algoritmo de búsqueda y resolución inteligente de rutas:

1. **Búsqueda en Raíz y Local (`DIR_DATOS_RAIZ` y `DIR_DATOS`):** El sistema escanea tanto la carpeta `datos/` del directorio padre (donde el script `consolidar.py` de la Práctica 06 genera sus exportaciones masivas) como el directorio `practica7/datos/`.
2. **Priorización Automática de Datos Reales:** Filtra y excluye automáticamente el archivo simulado `dataset_prueba.json` tan pronto como detecta un archivo de extracción real (`dataset_*.json`), cargando por defecto la versión más reciente según su marca temporal de modificación (`os.path.getmtime`).
3. **Integración Directa en Raíz (`main.py`):** El archivo `main.py` en la raíz del proyecto soporta las banderas `--sentimientos` (ejecuta extracción, consolidación y análisis en un solo flujo) y `--solo-sentimientos` (analiza el último dataset existente sin volver a raspar las redes).

### Composición del Dataset Real Analizado (`dataset_20260715_110053.json`):
* **Total de registros:** 508 publicaciones y comentarios.
* **Distribución por Fuente:**
  * **YouTube:** 488 registros (comentarios en reportajes periodísticos de Ecuavisa, Diario Expreso, etc.).
  * **TikTok:** 12 registros (videos y debates de arquitectura y crítica ciudadana).
  * **Facebook:** 8 registros (publicaciones y comentarios de profesionales y ciudadanía).
* **Trazabilidad Preservada:** Cada registro analizado hereda intactos sus campos clave (`id_unico`, `fuente`, `consulta`, `autor`, `url`, `metricas`).

---

## 3. Propuesta y Justificación del Modelo de Análisis de Sentimientos (`0.8 pts`)

### ¿Por qué Modelos de Lenguaje (LLMs vía API) y no clasificadores léxicos o locales?
El análisis de sentimientos en textos extraídos de redes sociales ecuatorianas presenta desafíos complejos:
* **Sarcasmo e Ironía:** Comentarios como *"Apaludan floribestias. Un museo con sobreprecio es mas importante que escuelas y hospitales"* requieren comprensión profunda del tono irónico y el contexto sociopolítico.
* **Jerga, Modismos y Errores:** Expresiones informales o abreviaturas en comentarios rápidos.
* **Posturas Mixtas:** Debates arquitectónicos donde un usuario alaba la estética pero critica el costo de $100 millones.

Los diccionarios tradicionales (ej. AFINN, VADER) o modelos estáticos bag-of-words fallan severamente en estos escenarios. Por ello, se implementó una solución basada en **LLMs servidos vía API REST con salida en JSON estricto (`response_format: json_object`)**:
* **OpenAI (`gpt-4o-mini`):** Modelo predeterminado de alta precisión semántica en español, veloz y altamente capaz de discernir matices argumentativos en debates de infraestructura pública.
* **Groq (`llama-3.1-8b-instant`):** Alternativa integrada de ultra baja latencia y acceso gratuito para validación cruzada y comparación de inferencias.

### Categorías de Clasificación Propuestas y Justificadas
Para capturar la riqueza del debate sobre el diseño *"Ecos del Sol"*, se definieron **5 categorías**:
1. `positivo`: Aprobación explícita, defensa del diseño, elogio a los criterios arquitectónicos o culturales.
2. `negativo`: Rechazo estético (ej. *"caja de cartón"*), denuncia de presunto sobreprecio o reclamo por priorizar otras necesidades públicas (hospitales, medicinas).
3. `neutral`: Consultas informativas, titulares periodísticos o reportes sin juicio de valor.
4. `mixto`: Presencia equilibrada en el mismo texto de argumentos a favor y en contra.
5. `no_clasificable`: Textos ininteligibles, ambigüedad extrema o fallos imprevisibles tras agotar reintentos.

### Tolerancia a Fallos y Manejo de Rate-Limits (`HTTP 429`)
Para procesar cientos de solicitudes sin pérdidas, los módulos `analizador_openai.py` y `analizador_groq.py` implementan:
* **Reintentos automáticos (`max_reintentos = 5`):** Bucle de reintentos exponenciales ante errores de red.
* **Respeto estricto a `Retry-After`:** Al recibir un código de estado `429 (Too Many Requests)`, el sistema lee el encabezado de respuesta `Retry-After` y suspende el hilo exactamente el tiempo requerido para el reinicio de la cuota, garantizando un 100% de tasa de éxito en la clasificación del corpus.

---

## 4. Diseño e Implementación de la Solución Paralela / Concurrente (`1.5 pts`)

### Arquitectura de Concurrencia Híbrida en 2 Niveles
El procesamiento de un texto requiere una petición HTTP a los servidores de OpenAI o Groq. Este tipo de carga se clasifica estrictamente como **$I/O-Bound$ (limitado por entrada/salida y latencia de red)**, donde la CPU pasa la mayor parte del tiempo en espera pasiva aguardando la respuesta del servidor remoto.

Para evidenciar las técnicas aprendidas en la asignatura y resolver el desbalance de volumen entre fuentes (488 registros en YouTube vs 8 en Facebook), se diseñó una **arquitectura paralela en dos niveles**:

```text
                                [ Corpus Real: 508 Registros ]
                                              │
                              Agrupamiento por Fuente (Red Social)
                                              │
           ┌──────────────────────────────────┼──────────────────────────────────┐
           ▼                                  ▼                                  ▼
 [ Hilo Productor: Facebook ]       [ Hilo Productor: TikTok ]         [ Hilo Productor: YouTube ]
      (8 registros)                     (12 registros)                    (488 registros)
           │                                  │                                  │
           │ Ejecución Secuencial             │ Ejecución Secuencial             ▼
           │ (Volumen <= 15)                  │ (Volumen <= 15)        [ Sub-Pool Concurrente ]
           │                                  │                        (12 Sub-Hilos internos)
           ▼                                  ▼                                  │
       [ API LLM ]                        [ API LLM ]                            ▼
           │                                  │                          [ Peticiones HTTP ]
           └──────────────────┬───────────────┴──────────────────────────────────┘
                              ▼
                queue.Queue() [Cola Thread-Safe Sincronizada]
                              │
                              ▼
            [ Hilo Consumidor Central (Daemon Thread) ]
                              │
                              ▼
           Exportación JSON Dual (practica7/datos + raíz/datos)
```

#### Nivel 1 — Paralelismo por Red Social (Patrón Productor-Consumidor):
* El método `_agrupar_por_fuente()` divide el corpus en bloques de datos independientes, uno por red social (`Facebook`, `TikTok`, `YouTube`).
* Mediante `ThreadPoolExecutor(max_workers=n_bloques)`, se lanza un hilo **Productor** dedicado (`Sentimiento_0`, `Sentimiento_1`, `Sentimiento_2`) para cada plataforma. Las tres plataformas inician su labor **exactamente al mismo tiempo**.
* Cada productor empuja los objetos `RegistroSentimiento` clasificados a una **Cola Segura (`queue.Queue`)**. Esta estructura en memoria compartida garantiza exclusión mutua implícita sin condiciones de carrera.
* Un **Hilo Consumidor** (`threading.Thread` en modo demonio) drena la cola en tiempo real y consolida los resultados hasta recibir las señales de terminación (`_FIN`).

#### Nivel 2 — Concurrencia por Sub-Lotes para Fuentes de Alto Volumen:
* Si un hilo productor detecta que su fuente tiene un volumen pequeño (`len(bloque) <= 15`, caso de Facebook y TikTok), procesa sus textos uno a uno dentro de su hilo.
* Si el hilo productor detecta un gran volumen (`len(bloque) > 15`, caso de YouTube con 488 comentarios), **despliega dinámicamente un Sub-Pool concurrente (`ThreadPoolExecutor` interno)** con hasta 12 trabajadores (`Sub_You`).
* Esto solapa masivamente las esperas de red de los cientos de comentarios de YouTube, logrando que el análisis de 488 textos finalice en menos de 50 segundos en lugar de requerir más de 5 minutos en secuencia.

### Justificación Teórica (`queue.Queue` y `threading` vs `multiprocessing`)
Conforme a la literatura y bases teóricas de la asignatura (*Chapter 02: Thread-based Parallelism*):
1. **Liberación del GIL en Operaciones I/O:** El *Global Interpreter Lock* (GIL) de Python interrumpe su bloqueo exclusivo y se libera automáticamente al realizar operaciones de red I/O (`socket.send`/`recv`). Esto permite que múltiples hilos se ejecuten **verdaderamente en paralelo en los tiempos de latencia HTTP**, logrando un solapamiento óptimo.
2. **Memoria Compartida sin Overhead IPC:** A diferencia de `multiprocessing.Process`, que requiere serializar/deserializar objetos y duplicar el espacio de memoria (alto *IPC overhead*), los hilos comparten el espacio de direcciones del proceso padre. Esto hace que pasar objetos `RegistroSentimiento` a través de `queue.Queue()` sea instantáneo y con huella de memoria mínima.

---

## 5. Almacenamiento Estructurado de los Resultados (`0.5 pts`)

Para garantizar que los resultados sean interoperables y alimenten directamente a la visualización y al artículo del proyecto final, el módulo `almacenamiento_sentimientos.py` realiza una **exportación estructurada dual** en formato JSON (`sentimientos_<timestamp>.json`):
* Guarda el archivo en **`practica7/datos/`** para auditoría de la práctica.
* Guarda una copia idéntica en **`datos/` (raíz del proyecto)** para que todo el repositorio consuma de forma global el análisis.

### Esquema del Dataset de Salida:
```json
{
  "problematica": "¿Cuál es la percepción de los usuarios sobre el diseño 'Ecos del Sol' del nuevo MUNA?",
  "generado_en": "2026-07-15T16:38:47.912345",
  "total_registros": 508,
  "resumen_por_fuente": {
    "Facebook": { "positivo": 3, "negativo": 2, "mixto": 1, "no_clasificable": 2 },
    "TikTok": { "neutral": 6, "positivo": 2, "negativo": 1, "mixto": 1, "no_clasificable": 2 },
    "YouTube": { "negativo": 275, "mixto": 67, "neutral": 52, "positivo": 44, "no_clasificable": 50 }
  },
  "registros": [
    {
      "fuente": "Facebook",
      "consulta": "museo nacional del ecuador",
      "texto": "Este es mi proyecto favorito para el Museo Nacional del Ecuador... reúne criterios de diversidad cultural y memoria.",
      "autor": "Aleyda Quevedo Rojas",
      "sentimiento": "positivo",
      "justificacion": "La usuaria expresa explícitamente que es su proyecto favorito y elogia sus atributos culturales.",
      "modelo": "gpt-4o-mini",
      "metricas": { "likes": 0, "comentarios": 4, "compartidos": 0 },
      "id_unico": "8a8e9f68a9baf365"
    }
  ]
}
```

---

## 6. Evidencia de Ejecución Real y Resultados Obtenidos (`0.4 pts`)

### Log de Ejecución Real (508 Registros Clasificados con OpenAI `gpt-4o-mini`):
Se adjunta la evidencia de ejecución concurrente obtenida en terminal al correr el comando `python3 practica7/main.py --proveedor openai`:

```text
======================================================================
  ANÁLISIS PARALELO DE SENTIMIENTOS (OPENAI)
  Práctica de Laboratorio 07 — Computación Paralela
======================================================================
Problemática:
  ¿Cuál es la percepción de los usuarios de redes sociales sobre el diseño ganador ('Ecos del Sol') del nuevo Museo Nacional del Ecuador?

Registros a clasificar: 508
Fuentes: Facebook, TikTok, YouTube
Proveedor LLM: OPENAI

11:37:58 | INFO    | MainThread         | Modelo: gpt-4o-mini | Proveedor: OPENAI
11:37:58 | INFO    | Sentimiento_0      | Clasificando 8 textos de Facebook...
11:37:58 | INFO    | Sentimiento_1      | Clasificando 12 textos de TikTok...
11:37:58 | INFO    | Sentimiento_2      | Clasificando 488 textos de YouTube...
11:38:47 | INFO    | MainThread         | PARALELO: 508 textos clasificados en 49.59 s

----------------------------------------------------------------------
RESUMEN POR FUENTE Y SENTIMIENTO
----------------------------------------------------------------------
  Facebook:
      mixto          : 1
      negativo       : 2
      no_clasificable: 2
      positivo       : 3
  TikTok:
      mixto          : 1
      negativo       : 1
      neutral        : 6
      no_clasificable: 2
      positivo       : 2
  YouTube:
      mixto          : 67
      negativo       : 275
      neutral        : 52
      no_clasificable: 50
      positivo       : 44

Resultados guardados en (práctica 7): /home/justin/Documentos/COMPUTACION PARALELA/Extracci-nDeDatosEnRedeSociales/practica7/datos/sentimientos_20260715_113847.json
Resultados guardados en (raíz proyecto): /home/justin/Documentos/COMPUTACION PARALELA/Extracci-nDeDatosEnRedeSociales/practica7/../datos/sentimientos_20260715_113847.json

Tiempo paralelo: 49.59 s
```

### Tabla Resumen Agregada del Estudio (508 Opiniones)
| Red Social | Positivo | Negativo | Neutral | Mixto | No Clasificable | Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Facebook** | 3 | 2 | 0 | 1 | 2 | **8** |
| **TikTok** | 2 | 1 | 6 | 1 | 2 | **12** |
| **YouTube** | 44 | 275 | 52 | 67 | 50 | **488** |
| **TOTAL** | **49 (9.6%)** | **278 (54.7%)** | **58 (11.4%)** | **69 (13.6%)** | **54 (10.6%)** | **508 (100%)** |

---

## 7. Interfaz Gráfica y Dashboard Visual Interactivo (`Especial`)

Para facilitar la comprensión e inspección auditada de los datos clasificados por el LLM, se construyó una **Interfaz Gráfica de Usuario / Web Dashboard** en el directorio `practica7/interfaz/` y acompañada de su servidor lanzador en Python (`ver_sentimientos.py`).

### Arranque del Dashboard:
```bash
python3 practica7/ver_sentimientos.py
```
El comando levanta un servidor local (`http://localhost:8080`), sirve la API REST (`/api/datasets` y `/api/dataset`) y abre el navegador automáticamente en la vista principal.

### Características y Especificaciones de Diseño del Dashboard:
1. **Aestética Premium (`Dark Mode & Glassmorphism`):** Paleta de color HSL curada, tarjetas con desenfoque de fondo (`backdrop-filter: blur`), micro-animaciones en transiciones y tipografías Google Fonts (`Inter` y `Outfit`).
2. **Tarjetas KPI Clicables para Filtrado Instantáneo:** Muestran el total de registros por categoría (`Positivo`, `Negativo`, `Neutral`, `Mixto`, `No Clasificable`) junto con su porcentaje. Hacer clic en cualquier tarjeta KPI filtra dinámicamente todo el dashboard a esa categoría.
3. **Barras de Distribución por Red Social:** Muestran barras horizontales segmentadas por colores para comparar visualmente la proporción de sentimientos entre Facebook, TikTok y YouTube.
4. **Buscador en Tiempo Real y Filtros Combinados:** Permite buscar por palabras clave dentro del texto o la justificación, filtrar por fuente (`fuente`) y ordenar por relevancia o cantidad de interacciones (`likes`).
5. **Explicabilidad (`Explainable AI`):** Cada opinión se muestra en una tarjeta o fila de tabla que presenta el texto original junto con la **Justificación generada por el LLM**, explicando con total claridad por qué el modelo asignó ese sentimiento.
6. **Soporte Drag & Drop y Cambio de Datasets:** Permite arrastrar y soltar cualquier archivo `sentimientos_*.json` desde el explorador de archivos directamente al navegador o cambiar entre ejecuciones históricas desde un menú desplegable.

---

## 8. Relación e Impacto en el Proyecto Final (`0.3 pts`)

La Práctica de Laboratorio 07 actúa como el **eje analítico y transformador** que conecta la extracción en crudo de la Práctica 06 con las entregas del **Proyecto Final (Artículo Académico, Storytelling y Visualización de Grandes Volúmenes de Datos)**:

1. **Evidencia Cuantitativa para el Storytelling:** Los datos revelan un fuerte contraste entre plataformas: mientras en **YouTube** domina una clara corriente de rechazo y crítica sociopolítica/fiscal (`56.3% Negativo` y `13.7% Mixto`), en **TikTok** y **Facebook** existen posturas más equilibradas o explicativas (`Neutral/Positiva`). Este hallazgo constituye el hilo conductor perfecto para la narrativa de la percepción ciudadana sobre *"Ecos del Sol"*.
2. **Ponderación por Impacto Algorítmico:** Al preservar las métricas de interacción (`likes`, `comentarios`, `vistas`), el proyecto final podrá graficar el **"Sentimiento Ponderado por Interacción"**. Esto permite diferenciar entre la crítica de un usuario aislado y la de un video viral con miles de reproducciones e interacciones.
3. **Explicabilidad y Citas para el Artículo Científico:** El campo `justificacion` permite al equipo citar en el artículo académico extractos objetivos generados por inteligencia artificial que resumen y categorizan los argumentos técnicos, estéticos y económicos de la ciudadanía sobre el nuevo Museo Nacional del Ecuador.

---
*Fin del Informe Técnico — Práctica 07.*
