# Machine Learning

Componente de Machine Learning de SynapDesk para clasificar tickets de soporte,
estimar su prioridad y sugerir el area responsable. El modelo funciona como
asistencia para el agente; la decision final permanece bajo supervision humana.

## Stack

- Python
- Pandas
- Scikit-learn
- Joblib
- TF-IDF
- SGDClassifier con `log_loss`

## Requisitos

- Python 3.12 (misma versión menor que el CI)
- pip
- CSV de tickets en espanol ubicado localmente en `ml/data/raw/tickets_esp.csv`
  o el dataset sintetico versionado en `ml/samples/tickets_esp_sintetico.csv`
  para verificar el pipeline.

El dataset de tickets y los artefactos generados no se versionan en Git. Debe
confirmarse la licencia, procedencia y ausencia de informacion sensible antes
de compartir el CSV fuera del entorno local.

El lector exige CSV con comas, comillas válidas y UTF-8 (admite BOM). Rechaza
filas con campos desalineados sin omitirlas ni sustituir caracteres. Renombrar
un archivo o envolver una fila CSV en una celda no corrige su formato.

Las seis dependencias de `requirements.txt` tienen versiones exactas. Los
artefactos y métricas registran Python, esas dependencias, SHA-256 del dataset,
catálogos de clases y cantidad de textos compartidos entre las particiones.

## Auditoria local de etiquetas

La preparacion existente normaliza textos y etiquetas, descarta filas vacias y
duplicados exactos. Para revisar posibles inconsistencias de prioridad sin
alterar el CSV original ni las etiquetas usadas para entrenar:

```bash
python ml/audit_ticket_dataset.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/data_quality
```

Si el CSV esta fuera del repositorio, sustituye `--input-csv` por su ruta local.
El script genera `data_quality.json` con conteos y SHA-256, y
`priority_review_candidates.csv` con el numero de fila del registro en el CSV
(incluyendo la cabecera), la prioridad actual y la señal detectada. La lista no
incluye el texto del ticket. Ambos archivos quedan en `ml/artifacts/`, excluido
de Git.

Los candidatos léxicos son casos para revisar, no errores confirmados. La
corrección de prioridades exige lectura del asunto y cuerpo originales y
criterios de impacto; una palabra de urgencia aislada no justifica un cambio.

Para aplicar correcciones humanas sin modificar el CSV fuente, consulta
[Correcciones reproducibles de prioridad](CORRECCIONES_PRIORIDAD.md).

## Instalacion

Desde la raiz del repositorio, usando Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r ml/requirements.txt
```

Para comprobar que el entorno esta activo:

```bash
which python
python --version
```

## Dataset

El pipeline principal utiliza `ml/data/raw/tickets_esp.csv`. Ese archivo no se
versiona porque puede contener datos externos o sensibles. Para verificar el
pipeline sin exponer datos reales se incluye
`ml/samples/tickets_esp_sintetico.csv`.

- El CSV completo utilizado en la evaluacion local contiene 2.239 registros
  en espanol; 2.237 quedan despues del filtrado y la eliminacion de duplicados.
  Su SHA-256 es
  `ade38dba719f54bfd06d3fcd12a4c6ff031887eca5545a98c74fac97b10db11a`.
  El archivo permanece fuera del repositorio.
- La muestra sintetica versionada contiene 12 tickets con `language = es`.
- Entradas del modelo: `subject` y `body`.
- Objetivos: `type`, `priority` y `queue`.
- `answer` no se utiliza como entrada para evitar fuga de informacion.

Las etiquetas tecnicas se conservan para mantener el contrato del sistema:

- Tipo: `incident`, `request`, `problem`, `change`.
- Prioridad: `low`, `medium`, `high`, `critical`.
- Area: nombres tecnicos como `technical_support` o `it_support`.

## Entrenamiento

Desde la raiz del repositorio:

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

El entrenamiento limpia el texto, normaliza las etiquetas, elimina filas
invalidas y duplicados, separa entrenamiento y prueba y genera las metricas.
La separación agrupa por texto preparado. Si no puede construir una partición
válida, falla explícitamente; no recurre a separar filas que comparten texto.

Verificacion reproducible con dataset sintetico:

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/samples/tickets_esp_sintetico.csv \
  --language es \
  --min-target-count 1 \
  --max-features 2000 \
  --output-dir ml/artifacts/ticket_classifier_sample
```

## Prediccion

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "URGENTE: no puedo entrar al correo" \
  --body "Necesito recuperar el acceso inmediatamente para trabajar." \
  --enable-business-rules
```

La respuesta entrega:

- `clasificacion_sugerida`;
- `prioridad_estimada`;
- `area_responsable`;
- confianza y tres clases probables cuando el modelo las entrega;
- version del modelo;
- decision y trazabilidad de las reglas aplicadas.

## Mapeo a MLPrediction

Hasta que el contrato Backend-ML quede cerrado en el PR documental, la
integracion debe tratar esta salida como un adaptador interno hacia
`MLPrediction`:

| Salida ML | Campo sugerido en dominio | Nota |
| --- | --- | --- |
| `predictions.clasificacion_sugerida.label` | `predictedCategory` | Mapeo pendiente: tipo no equivale automáticamente a categoría temática. |
| `predictions.prioridad_estimada.label` | `predictedPriority` | Puede venir del modelo o de una regla aprobada. |
| `predictions.area_responsable.label` | `predictedArea` | Correspondencia de cola con área pendiente de aprobación. |
| `predictions.*.confidence` | `confidence` o detalle por salida | Confianza estadistica solo cuando `confidence_source = model`. |
| `modelName` | `modelName` | Nombre del artefacto cargado. |
| `modelVersion` | `modelVersion` | Version exacta del entrenamiento. |
| `predictions.*.top3` | metadata adicional | Ranking estadístico, también en la muestra generada durante entrenamiento. |
| `decision`, `decision_source`, `rule`, `trigger` | metadata adicional | Trazabilidad de reglas y procedencia. |
| `model_label`, `model_confidence` | metadata adicional | Resultado estadistico original cuando hubo regla. |

Si `decision_source = business_rule`, la prioridad final no debe interpretarse
como una prediccion estadistica con certeza total. En ese caso `confidence`
queda en `null` y la confianza del clasificador queda en `model_confidence`.

Cada objetivo devuelve siempre estas diez claves internas: `label`,
`confidence`, `top3`, `decision`, `decision_source`, `confidence_source`,
`model_label`, `model_confidence`, `rule`, `trigger`. Sin regla aplicada,
los resultados estadísticos conservan `decision_source: model`; `rule` y
`trigger` son `null`. Un clasificador sin probabilidades devuelve confianza y
procedencia de confianza `null`, con `top3: []`.

Se conservan los nombres internos existentes para evitar una migración
innecesaria. El futuro adaptador traducirá a camelCase según el acuerdo del
PR #14. No se agregan DTO ni se aprueba el mapeo de confianza pública en este PR.

## Reglas de negocio

Las reglas de negocio estan desactivadas por defecto hasta que el equipo
apruebe sus criterios funcionales. La regla `urgent_priority`, cuando se activa
explicitamente, fuerza `priority = critical` cuando el asunto o cuerpo
contiene señales fuertes de urgencia, por ejemplo:

- `urgente`;
- `urgencia`;
- `emergencia`;
- `crítico`/`crítica` con contexto, como `falla crítica` o `es crítico`;
- `inmediatamente`;
- `alta prioridad`;
- `caida total` o `caída total`;
- `interrupcion total` o `interrupción total`.

Negaciones explicitas cercanas a la señal, como `no es urgente`, `sin urgencia`
o `no es una emergencia`, así como `no es nada urgente`, `no urgente` y
`no creo que sea urgente`, no activan la regla. Una `revisión crítica` del
manual tampoco es un disparador. La deteccion es lexical y no
resuelve todos los matices del lenguaje; sus criterios requieren validacion
funcional antes de activar la regla por defecto.

La palabra `urgente` sola no es un criterio suficiente para corregir etiquetas
del dataset ni una política aprobada de prioridad. La regla sigue siendo un
experimento opcional; las correcciones humanas se basan en impacto y no la
habilitan. En inferencia sin opción explícita se hereda la configuración del
artefacto; usa `--disable-business-rules` para asegurar su desactivación.

Cuando se aplica la regla, la respuesta incluye `decision = business_rule`
(o `model_and_business_rule` si el modelo ya predijo `critical`),
`decision_source`, `rule`, `trigger`, `model_label`, `model_confidence` y
`confidence_source`. En decisiones por regla, `confidence` queda en `null`
porque la confianza estadistica corresponde al modelo y se conserva en
`model_confidence`.

Para comparar únicamente el resultado estadistico del modelo:

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "URGENTE: no puedo entrar al correo" \
  --body "Necesito recuperar el acceso inmediatamente para trabajar."
```

## Artefactos generados

El entrenamiento genera localmente:

```text
ml/artifacts/ticket_classifier_es/
├── prepared_tickets.csv
├── ticket_classifier.joblib
├── metrics.json
└── sample_prediction.json
```

Estos archivos son reproducibles y estan excluidos de Git. No se deben subir
con `git add -f`.

## Comandos disponibles

| Comando | Descripcion |
| --- | --- |
| `python ml/train_ticket_classifier.py` | Prepara el CSV y entrena el modelo. |
| `python ml/predict_ticket.py` | Ejecuta una prediccion local. |
| `python ml/compare_priority_corrections.py --help` | Compara original y correcciones sobre la misma población, partición y referencia. |
| `python ml/audit_ticket_dataset.py --input-csv <ruta>` | Genera una lista local de prioridades para revision humana, sin corregir etiquetas. |
| `python -m py_compile ml/*.py` | Comprueba la sintaxis de los scripts. |
| `python -m unittest discover -s tests -t . -v` | Ejecuta las pruebas sin colisión entre `tests.ml` y el módulo `ml`. |
| `python ml/train_ticket_classifier.py --enable-business-rules` | Evalua con reglas deterministas aprobadas. |

## Evaluación reproducida desde el original intacto

Ejecución del 1 de noviembre de 2026 con el SHA-256 del original identificado
arriba, Python 3.12.4 y las dependencias exactas de `requirements.txt`.
Se entrenó sin correcciones y con correcciones usando `random_state=42`,
`test_size=0.2`, `min_target_count=2`, `max_features=120000`, unigramas/bigramas
y reglas desactivadas. Ambos conjuntos contienen los mismos 2.237 registros,
con 1.789 de entrenamiento y 448 de prueba, sin textos compartidos. Solo
cambia `priority`; se conservaron los textos y demás campos del original.

El archivo separado contiene 63 decisiones según `prioridad-impacto-v1`:
38 cambios (37 de `medium` a `high` y uno de `low` a `medium`) y 25 casos
`dudoso:` que conservan su etiqueta original. La revisión fue asistida,
previa al entrenamiento y sin consultar predicciones; requiere validación de
la responsable de datos. El manifiesto vincula las decisiones al SHA-256 del
original. No se utilizan motivos de importación manual como justificación.

Para reproducir ambos experimentos y la comparación, seguir
[Correcciones reproducibles de prioridad](CORRECCIONES_PRIORIDAD.md).
Las anotaciones sin textos ni datos personales y su manifiesto están en
`ml/annotations/` para revisión y reproducción. Los tickets, métricas completas
y modelos permanecen locales; las notas del proceso corresponden al PR.

### Misma referencia revisada para ambos modelos

La comparación principal evalúa ambos modelos sobre los mismos 448 tickets
con las mismas etiquetas revisadas. Hay 171 tickets `high` en esa referencia.

| Métrica de prioridad | Modelo sin correcciones | Modelo con correcciones |
| --- | ---: | ---: |
| Macro F1 | 0,6338 | 0,6263 |
| Weighted F1 | 0,6453 | 0,6366 |
| `high` detectados | 124 / 171 | 123 / 171 |
| `high` omitidos | 47 | 48 |
| Falsas alarmas `high` | 56 | 59 |
| Recall `high` | 0,7251 | 0,7193 |

| Clase | Soporte común | Precisión sin/con correcciones | Recall sin/con correcciones | F1 sin/con correcciones |
| --- | ---: | ---: | ---: | ---: |
| `high` | 171 | 0,6889 / 0,6758 | 0,7251 / 0,7193 | 0,7066 / 0,6969 |
| `medium` | 188 | 0,6080 / 0,6062 | 0,6436 / 0,6223 | 0,6253 / 0,6142 |
| `low` | 89 | 0,6522 / 0,6301 | 0,5056 / 0,5169 | 0,5696 / 0,5679 |

Las correcciones no mejoraron la detección de `high` en esta partición: el
modelo corregido detectó un caso menos y produjo tres falsas alarmas más.
No se presenta como superior ni se ajustaron etiquetas para mejorar métricas.
La referencia revisada no sustituye una validación independiente; una sola
partición tampoco permite concluir diferencias estadísticamente significativas.

### Referencia propia de cada entrenamiento

| Objetivo | Sin correcciones: Macro / Weighted F1 | Con correcciones: Macro / Weighted F1 |
| --- | ---: | ---: |
| Tipo (`type`) | 0,6835 / 0,6899 | 0,6835 / 0,6899 |
| Prioridad (`priority`) | 0,6225 / 0,6313 | 0,6263 / 0,6366 |
| Área/cola (`queue`) | 0,6500 / 0,5992 | 0,6500 / 0,5992 |

En la prueba cambian 13 etiquetas de prioridad. Por eso el resultado propio
sin correcciones tiene 159 `high` (detecta 115), mientras el corregido tiene
171 (detecta 123). Esos conteos con denominadores distintos no prueban mejora;
para comparar usar la referencia común de la tabla anterior. `comparison.json`
conserva ambas referencias, métricas por clase y matrices de confusión.

Estos resultados reemplazan la evaluación de la copia reexportada desde Excel:
se recuperó el original completo, sin excluir los 19 registros dañados por esa
exportación y sin aplicar sus cambios de texto o eliminación de etiquetas.
Las copias anteriores permanecen preservadas localmente.

El original solo contiene prioridades `low`, `medium` y `high`. El modelo
entrenado no aprende `critical`; la regla experimental puede imponerla si se
habilita. Estas métricas no evalúan esa regla ni son umbrales de aceptación
aprobados. Las probabilidades no están calibradas; la prioridad final requiere
revisión del contexto por el agente humano.

## Verificacion reproducible con la muestra sintetica

Resultados reproducidos el 1 de noviembre de 2026 con los cambios locales de
esta revisión, 12 tickets sintéticos y el comando de verificación de arriba.
Entorno: Python 3.12.4, pandas 2.3.3, scikit-learn 1.9.1, joblib 1.6.0,
NumPy 2.3.4, SciPy 1.18.1 y threadpoolctl 3.7.0. Reglas desactivadas;
intersección de textos entre particiones: cero en los tres objetivos.

| Salida | train_rows | test_rows | Macro F1 | Weighted F1 |
| --- | ---: | ---: | ---: | ---: |
| Clasificacion sugerida (`type`) | 9 | 3 | 0,1667 | 0,2222 |
| Prioridad solo modelo (`priority`) | 9 | 3 | 0,0000 | 0,0000 |
| Area responsable (`queue`) | 9 | 3 | 0,0000 | 0,0000 |

Estos valores solo verifican que el pipeline entrena y evalua con datos
sinteticos; tres ejemplos de prueba por objetivo no permiten estimar su calidad
para tickets reales. La regla determinista requiere evaluacion aparte despues
de aprobar sus criterios funcionales.

## Estado de implementacion

- [x] Dataset en espanol analizado y preparado.
- [x] Entrenamiento de modelos para tipo, prioridad y area.
- [x] Prediccion local mediante artefacto `.joblib`.
- [x] Regla de urgencia compartida entre evaluacion y prediccion, desactivada por defecto.
- [x] Metricas y pipeline ML documentados.
- [x] Pruebas automatizadas del modulo ML.
- [ ] Integracion del modelo dentro de un backend FastAPI.
- [ ] Montaje del modelo dentro de un servicio Docker.

## Documentacion relacionada

- [Pipeline de dataset y modelo](DATASET_ML_PIPELINE.md)
- [Estrategia de entornos](../docs/arquitectura/entornos.md)
- [Correcciones de prioridad](CORRECCIONES_PRIORIDAD.md)

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.

## Prototipo de embeddings y recuperación semántica

`semantic_retrieval/` implementa el flujo local de textos UTF-8 controlados →
fragmentos → embeddings → PostgreSQL + pgvector → búsqueda. Es un prototipo
experimental; la integración HTTP, autenticación, extracción de PDF y RAG siguen
pendientes. Su tabla experimental no fija el esquema documental del producto.

El candidato es `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
revisión `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, con 384 dimensiones.
Indexación y consulta usan exactamente el mismo `modelId`. Se fragmenta en
ventanas de 96 tokens con 16 de solapamiento. Antes de generar vectores se
comprueba el límite real del modelo: 128 tokens, incluidos los especiales.
Las consultas que lo superen se rechazan explícitamente, sin truncarlas.
También se conserva el límite de 1000 caracteres por consulta y 1 MB por archivo.

`score = 1 - distancia_coseno` es similitud en [-1, 1], no probabilidad ni
confianza calibrada. La búsqueda exacta filtra por modelo y devuelve
`documentId`, `documentChunkId`, `title`, `excerpt` y `score`. Sin documentos
para ese modelo devuelve `{"items": []}`. Sin umbral de relevancia, obtener
resultados no garantiza que respondan a la consulta.

### Entorno y comandos

Usar Python 3.12 en un entorno virtual y las versiones fijadas, junto con las
restricciones del clasificador cuando se prueben juntos. La revisión del modelo se fija
independientemente de las versiones de las bibliotecas. Las dependencias
transitivas pueden variar; registrar el entorno de la ejecución.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-semantic.txt
.\.venv\Scripts\python.exe -m pip check
```

Al validar junto al clasificador en una copia de `main`, instalar en una sola
operación `-r ml/requirements.txt -r ml/requirements-semantic.txt` para respetar
sus versiones fijadas. Esa combinación se verifica por separado; no requiere
fusionar las ramas para realizar una simulación local.

En Windows, Docker Desktop con backend WSL 2 permite usar la imagen del proyecto.
Si falta WSL, seguir la [instalación oficial de Microsoft](https://learn.microsoft.com/windows/wsl/install)
y después la [instalación de Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/).
Completar cualquier reinicio requerido antes de ejecutar los contenedores.

Usar exclusivamente el servicio `db_test` para la verificación y una base propia
del prototipo: `synapdesk_semantic_test`. La base `synapdesk_test` pertenece a las
pruebas del backend: no ejecutar allí `init-db` ni indexar documentos, porque su
tabla experimental interfiere con la comprobación de migraciones de Alembic.
Un esquema separado no sustituye esta separación por base.

Configurar localmente las variables de pruebas de `.env.example`, sin subir
credenciales, e iniciar:

```powershell
docker compose --profile testing up -d db_test
docker compose --profile testing ps db_test
```

Crear la base una sola vez en esa instancia de pruebas, sin borrar bases previas:

```powershell
docker compose --profile testing exec db_test psql -U synapdesk_test -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE synapdesk_semantic_test;"
```

El usuario del ejemplo corresponde a `POSTGRES_TEST_USER=synapdesk_test`;
ajustar `-U` si se configuró otro. Si la base ya existe, comprobar su identidad y
reutilizarla sin eliminarla. Si se recrea el contenedor temporal, crear nuevamente
la base. Conservar `POSTGRES_TEST_DB=synapdesk_test` para el backend; solo las
conexiones semánticas apuntan a `synapdesk_semantic_test`.

```powershell
$env:SYNAPDESK_SEMANTIC_DATABASE_URL = "postgresql://synapdesk_test:<clave-de-pruebas>@localhost:5433/synapdesk_semantic_test"
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli init-db
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli index --document-id 11111111-1111-4111-8111-111111111111 --title "Conectividad" --file ml/examples/conectividad.txt
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli index --document-id 22222222-2222-4222-8222-222222222222 --title "Impresora" --file ml/examples/impresora.txt
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli search --query "No puedo acceder a la red de la oficina" --limit 5
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli search --query "La impresora no imprime" --limit 5
```

Sustituir la contraseña de ejemplo por la de la base de pruebas y codificarla
para URL si contiene caracteres especiales. El CLI no carga `.env`
automáticamente. No pegar la conexión real ni sus credenciales en la evidencia.
La primera carga puede descargar el modelo; las siguientes reutilizan la caché.
`init-db` es repetible. Reindexar reemplaza atómicamente los fragmentos de ese
documento y modelo, con UUID estables para cada posición.

Archivos inexistentes, ilegibles, vacíos, UTF-8 inválido, tamaño excesivo y
consultas inválidas producen un error de argumentos controlado (salida 2).
Si no se puede acceder a PostgreSQL, se informa un error controlado sin traza,
URL ni detalles de credenciales; se configura un timeout de conexión de cinco segundos.
Los errores de programación o del esquema conservan su diagnóstico original.
Para comprobar el caso solicitado, repetir `index` con un archivo inexistente:
el error debe describir la lectura fallida, sin traza y antes de cargar el modelo.

### Criterios verificables y pruebas

Los siguientes criterios técnicos concretan la verificación del prototipo;
la aceptación del PR corresponde al equipo:

1. Inicializar PostgreSQL con pgvector e indexar ambos ejemplos con el modelo
   real fijado. Registrar versiones y salidas efectivamente obtenidas.
2. Recuperar conectividad primero para la consulta de red e impresora primero
   para la de impresión, con los cinco campos y orden descendente por similitud.
   Dos ejemplos no permiten estimar calidad general ni fijar umbrales.
3. Verificar vectores finitos, no nulos, normalizados y de 384 dimensiones;
   textos preparados dentro del límite del modelo, incluidos tokens especiales.
4. Reindexar sin duplicados y con identificadores estables. Comprobar rollback
   de una inserción fallida y aislamiento entre modelos.
5. Rechazar entradas inválidas, devolver lista vacía sin documentos del modelo
   y superar las pruebas automatizadas junto con las del clasificador.

Las pruebas rápidas no necesitan PostgreSQL ni descargar un modelo:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -t . -v
```

Para activar las pruebas del tokenizador con subpalabras y los vectores reales,
primero disponer del modelo/revisión en caché y ejecutar:

```powershell
$env:SYNAPDESK_RUN_SEMANTIC_MODEL_TESTS = "1"
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.ml.test_semantic_chunking tests.ml.test_semantic_integration.RealSemanticModelTests -v
```

La prueba de base de datos real requiere su variable específica, apuntando también
a `synapdesk_semantic_test`, para evitar usar por accidente la conexión del
producto o del backend. Crea un esquema de nombre único y
revierte su transacción completa al salir; no reemplaza documentos del producto.
Verifica el flujo real, reindexación, rollback y aislamiento, e imprime un JSON
`semantic_evidence` con resultados y versiones, sin la conexión ni contraseñas:

```powershell
$env:SYNAPDESK_SEMANTIC_TEST_DATABASE_URL = $env:SYNAPDESK_SEMANTIC_DATABASE_URL
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.ml.test_semantic_integration.RealSemanticDatabaseTests -v
```

Sin sus variables de activación, las pruebas reales se informan como omitidas;
no constituyen evidencia de integración ejecutada. Guardar la salida real de
los comandos del CLI y de esta prueba en la descripción o comentarios del PR.

### Decisiones futuras

Evaluar consultas anonimizadas con relevancia etiquetada mediante Recall@5,
MRR@5, latencia, tamaño y costo antes de elegir el modelo definitivo, el umbral
para «información insuficiente», un índice vectorial o la política de indexación.
Un fragmento puede comenzar a mitad de frase por el solapamiento; acordar su
presentación con frontend (por ejemplo, una elipsis) al conectar resultados
reales. Estas propuestas no autorizan cambiar el frontend ni la API pública.

Contrato experimental: [embeddings-recuperacion.md](../docs/contratos/embeddings-recuperacion.md).
