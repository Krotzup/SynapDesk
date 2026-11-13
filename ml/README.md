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

El dataset de tickets y los artefactos generados no se versionan en Git. Su
[fuente, cadena de transformación y licencia](DATASET_PROVENANCE.md) están
documentadas por separado. La fuente externa usa CC BY-NC 4.0: cualquier
distribución debe atribuirla, enlazar la licencia, indicar los cambios, limitarse
a usos no comerciales y revisar antes la presencia de información sensible.

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

El original local es una selección/adaptación del archivo externo
[`aa_dataset-tickets-multi-lang-5-2-50-version.csv`](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/main/aa_dataset-tickets-multi-lang-5-2-50-version.csv).
La [procedencia detallada](DATASET_PROVENANCE.md) distingue su hash del archivo
externo y de la V2 corregida, y registra las limitaciones de reproducción de la
selección y traducción.

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
- Prioridad: `low`, `medium`, `high`.
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
  --body "Necesito recuperar el acceso inmediatamente para trabajar."
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
| `predictions.prioridad_estimada.label` | `predictedPriority` | Resultado del modelo dentro de `low`, `medium`, `high`. |
| `predictions.area_responsable.label` | `predictedArea` | Correspondencia de cola con área pendiente de aprobación. |
| `predictions.*.confidence` | `confidence` o detalle por salida | Confianza estadistica solo cuando `confidence_source = model`. |
| `modelName` | `modelName` | Nombre del artefacto cargado. |
| `modelVersion` | `modelVersion` | Version exacta del entrenamiento. |
| `predictions.*.top3` | metadata adicional | Ranking estadístico, también en la muestra generada durante entrenamiento. |
| `decision`, `decision_source`, `rule`, `trigger` | metadata adicional | Trazabilidad de reglas y procedencia. |
| `model_label`, `model_confidence` | metadata adicional | Resultado estadistico original cuando hubo regla. |

Cada objetivo devuelve siempre estas diez claves internas: `label`,
`confidence`, `top3`, `decision`, `decision_source`, `confidence_source`,
`model_label`, `model_confidence`, `rule`, `trigger`. Sin regla aplicada,
los resultados estadísticos conservan `decision_source: model`; `rule` y
`trigger` son `null`. Un clasificador sin probabilidades devuelve confianza y
procedencia de confianza `null`, con `top3: []`.

Se conservan los nombres internos existentes para evitar una migración
innecesaria. El futuro adaptador traducirá a camelCase según el acuerdo del
PR #14. No se agregan DTO ni se aprueba el mapeo de confianza pública en este PR.

## Prioridad sin regla de urgencia

El catálogo vigente contiene únicamente `low`, `medium` y `high`. Se retiró
`critical` y la regla `urgent_priority`: escribir «urgente» no fuerza una
prioridad. El texto sigue siendo una entrada del modelo; no se promete que
las palabras carezcan de influencia estadística.

La detección léxica se conserva exclusivamente en la auditoría del dataset
para localizar candidatos a revisión por contexto e impacto. No interviene
en entrenamiento, métricas ni inferencia como regla de asignación.

`--enable-business-rules` produce un error explícito. Se conserva
`--disable-business-rules` como opción compatible con los comandos anteriores.
Un artefacto con prioridades fuera del catálogo se rechaza y debe
reentrenarse. Si un artefacto antiguo habilita la regla retirada, la inferencia
predeterminada lo rechaza; `--disable-business-rules` permite usar solo sus
modelos si sus clases pertenecen al catálogo vigente.

La salida conserva sus diez claves internas. `businessRulesEnabled` es
`false`; `decision` y `decision_source` son `model`, y `rule` y `trigger` son
`null`. No cambia el contrato público ni se incorpora un adaptador FastAPI.

## Artefactos generados

El entrenamiento genera localmente:

```text
ml/artifacts/ticket_classifier_es/
├── prepared_tickets.csv
├── ticket_classifier.joblib
├── artifact_manifest.json
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
| `python ml/export_training_dataset.py --help` | Exporta el CSV corregido y su manifiesto sin alterar el original. |
| `python ml/evaluate_ticket_classifier.py --help` | Evalúa candidatos mediante particiones agrupadas y ajustes internos optativos. |
| `python ml/audit_ticket_dataset.py --input-csv <ruta>` | Genera una lista local de prioridades para revision humana, sin corregir etiquetas. |
| `python -m py_compile ml/*.py` | Comprueba la sintaxis de los scripts. |
| `python -m unittest discover -s tests -t . -v` | Ejecuta las pruebas sin colisión entre `tests.ml` y el módulo `ml`. |
| `--disable-business-rules` | Opción compatible; no hay reglas automáticas de prioridad. |

## Entrega V2 confirmada y evaluación del 5 de noviembre de 2026

La versión vigente es `tickets_esp_entrenamiento_v2.csv` junto a su
`tickets_esp_entrenamiento_v2.manifest.json`. América Figueroa confirmó las
80 decisiones adicionales; sumadas a las 63 anteriores, son 143 decisiones
confirmadas. Se conservan 2.239 registros y todos los textos: 62 prioridades
cambian respecto al original y 59 casos dudosos mantienen su etiqueta. La
preparación conserva 2.237 registros tras eliminar dos duplicados exactos.

- Original SHA-256: `ade38dba719f54bfd06d3fcd12a4c6ff031887eca5545a98c74fac97b10db11a`.
- Correcciones V2 SHA-256: `4886b5a67b3f6ef1c1d38e572537f006c3f00c1af87b82de32b307d758dfbb72`.
- CSV V2 SHA-256: `a3792862678c009ca66dad41aeb3e1fbc0a55d4213fd3c39e5cd2e6586e6740a`.

La fecha de validación registra la confirmación de las decisiones; no se
inventa una fecha histórica para la revisión anterior. Los archivos de
anotaciones y manifiestos están versionados en `ml/annotations/`; datasets,
modelos y reportes completos permanecen locales y excluidos de Git.

### Validación cruzada de prioridad

Cinco particiones por texto con `GroupKFold`, semilla 42, sin textos compartidos.
Los dos entrenamientos se evalúan contra las mismas etiquetas V2 de los mismos
2.237 tickets, con 980 casos `high`. Los candidatos comparten las particiones.
Las confianzas no se calibran y no se activan reglas ni umbrales adicionales.

| Etiquetas de entrenamiento | Candidato | Macro F1 media ± desviación | Weighted F1 media | Recall `high` | Falsas alarmas `high` |
| --- | --- | ---: | ---: | ---: | ---: |
| Originales | SGD palabras | 0,6470 ± 0,0277 | 0,6747 | 0,7143 | 205 |
| Originales | SGD palabras + caracteres | 0,6482 ± 0,0212 | 0,6763 | 0,7224 | 204 |
| V2 | SGD palabras | 0,6577 ± 0,0266 | 0,6865 | 0,7480 | 212 |
| V2 | SGD palabras + caracteres | 0,6598 ± 0,0231 | 0,6883 | 0,7561 | 214 |

Media y desviación poblacional corresponden a los pliegues; recall y falsas
alarmas usan todas las predicciones fuera de pliegue. La mejora de recall tiene
un costo de falsas alarmas. No se afirma significancia estadística ni se
presenta la validación cruzada como prueba externa independiente. Los valores
de la V1 se conservan como antecedente y no se comparan directamente con esta
tabla, cuya referencia es V2.

```text
python ml/evaluate_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/annotations/correcciones_prioridad_v2.csv --corrections-manifest ml/annotations/correcciones_prioridad_v2.json --candidates sgd_words sgd_words_chars --output ml/artifacts/evaluacion_v2.json
```

### Artefacto de la entrega V2

Se entrenó el artefacto `20261105184927` con caracteres únicamente para
`priority`; tipo y cola mantienen el baseline. Cada objetivo utiliza 1.789
registros para entrenar y 448 para prueba, sin textos compartidos. Estas
métricas pertenecen a esa partición, no al promedio de validación cruzada:

| Objetivo | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Tipo | 0,6835 | 0,6899 |
| Prioridad V2 con caracteres | 0,6451 | 0,6670 |
| Área/cola | 0,6500 | 0,5992 |

SHA-256 del artefacto generado en esta ejecución:
`92c8ea256c3b2330ecd7aa4d0e9b22ce774c1b2692bfcd3423c92f7d8c8cfabe`.
Python 3.12.4 y las seis versiones de `requirements.txt` constan en
`artifact_manifest.json` y `metrics.json`, junto a la procedencia y validación
de las 143 decisiones. El checksum identifica esa entrega, no garantiza un
hash idéntico para un nuevo entrenamiento con otra marca temporal.

```text
python ml/train_ticket_classifier.py --input-csv ml/data/raw/tickets_esp_entrenamiento_v2.csv --character-ngram-targets priority --disable-business-rules --output-dir ml/artifacts/ticket_classifier_training_v2
```

Los datos y pesos no se publican en Git. La integración FastAPI queda fuera
de este cambio. América Figueroa confirmó el 10 de noviembre de 2026 que se
retiren `critical` y su regla en ML, frontend y catálogo de persistencia. La
migración nueva `0003_retirar_prioridad_critical` convierte registros existentes a `high` y
restringe el catálogo; no se reescribe la migración inicial ni se ejecuta la
migración automáticamente. El downgrade restaura el catálogo anterior, pero
no reconstruye qué tickets eran `critical`.

## Antecedente: evaluación del original y V1 del 1 de noviembre

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
previa al entrenamiento y sin consultar predicciones. América Figueroa confirmó
esas 63 decisiones el 5 de noviembre; los números de esta sección corresponden
al experimento anterior del 1 de noviembre. El manifiesto vincula las decisiones al SHA-256 del
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

El original solo contiene prioridades `low`, `medium` y `high`. Las métricas
históricas de esta sección no evalúan reglas ni son umbrales de aceptación
aprobados. En la implementación vigente se retiraron `critical` y su regla. Las probabilidades no están calibradas; la prioridad final requiere
revisión del contexto por el agente humano.

## Verificacion reproducible con la muestra sintetica

Antecedente del 1 de noviembre de 2026, anterior a la retirada de `critical`
de la muestra sintética. Sus resultados no representan el catálogo actual.
Se usaron 12 tickets sintéticos y el comando de verificación de arriba.
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

- [Procedencia, transformaciones y licencia del dataset](DATASET_PROVENANCE.md).
- [Evaluación cruzada por grupos, candidatos, grilla y umbral experimental](CLASSIFIER_EVALUATION.md).
- [CSV de entrenamiento reproducible y manifiesto de procedencia](CORRECCIONES_PRIORIDAD.md#csv-derivado-para-entrenamiento).

- [Pipeline de dataset y modelo](DATASET_ML_PIPELINE.md)
- [Estrategia de entornos](../docs/arquitectura/entornos.md)
- [Correcciones de prioridad](CORRECCIONES_PRIORIDAD.md)

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.

## Prototipo de embeddings y recuperación semántica

`semantic_retrieval/` implementa el flujo local de textos UTF-8 controlados →
fragmentos → embeddings → PostgreSQL + pgvector → búsqueda. Es un prototipo
experimental; dispone de una API HTTP protegida optativa y una interfaz conectada.
El login HTTP, extracción de PDF y RAG siguen pendientes. Su tabla experimental
no fija el esquema documental del producto.

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

### Información insuficiente y calibración experimental

La búsqueda admite un perfil opcional de relevancia. Se prioriza conservar
resultados potencialmente útiles: la calibración mantiene todas las consultas
etiquetadas con cobertura que obtuvieron resultados y, bajo esa condición,
rechaza tantas consultas sin cobertura como permiten sus scores. Si hay un
intervalo entre muestras, se usa su punto medio. No se impone un número universal.
Si hay solapamiento se informa: el perfil puede seguir aceptando consultas sin
cobertura. El score no se convierte en una probabilidad de respuesta correcta.

Preparar un JSON local con consultas representativas, diferentes entre sí y
etiquetadas **antes de observar sus scores**. `answerable` significa que la
colección contiene información para la consulta, no que el primer resultado sea
correcto. Debe haber consultas con y sin cobertura. Ejemplo de formato, sin
valor como evaluación de calidad:

```json
{"queries": [
  {"queryId": "covered-1", "query": "La impresora no imprime", "answerable": true},
  {"queryId": "uncovered-1", "query": "¿Cómo preparo pan de masa madre?", "answerable": false}
]}
```

Con la conexión semántica propia configurada y documentos ya indexados, crear
la carpeta de salida y ejecutar (ajustar las rutas a los archivos locales):

```powershell
New-Item -ItemType Directory -Force ml/artifacts | Out-Null
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli calibrate-relevance --cases ml/data/consultas_relevancia.json --output ml/artifacts/relevancia.json
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli search --query "La impresora no imprime" --relevance-profile ml/artifacts/relevancia.json
```

El perfil registra modelo/revisión, huella de los fragmentos y vectores, huella
del archivo de consultas, fecha UTC, umbral y decisiones de calibración. No se
sobrescriben perfiles existentes. La lectura del corpus y su búsqueda se hacen
en una misma instantánea de solo lectura. Si cambia el modelo o el corpus, el
perfil se rechaza explícitamente y debe recalibrarse; no hay fallback silencioso.

Con perfil, solo se devuelven fragmentos con `score >= minScore`. Si ninguno
alcanza el corte, stdout conserva `{"items": []}` y stderr muestra
«Información insuficiente». Es una búsqueda válida (salida 0), no una avería.
Sin perfil se conserva la búsqueda original sin umbral, útil para evaluar.
La API y el frontend implementan esa señal según el contrato de recuperación V1;
el CLI conserva stdout compatible. No se presenta el score como confianza.

La calibración no es una evaluación independiente. Reservar consultas nuevas
para medir cobertura conservada, rechazos correctos y falsos positivos; revisar
también si los fragmentos aceptados responden realmente. Un perfil experimental
no demuestra calidad de producción ni garantiza respuestas suficientes.

### Decisiones futuras

Evaluar consultas anonimizadas con relevancia etiquetada mediante Recall@5,
MRR@5, latencia, tamaño y costo antes de elegir el modelo definitivo, aprobar un
perfil de relevancia para producción, un índice vectorial o la política de indexación.
Un fragmento puede comenzar a mitad de frase por el solapamiento. El frontend
lo presenta como extracto y enlaza su fuente e idioma cuando están disponibles.

Contrato experimental: [embeddings-recuperacion.md](../docs/contratos/embeddings-recuperacion.md).

### Perfiles V2, evaluación y fuentes reproducibles

`init-db` prepara también la identidad/revisión por modelo y sus triggers. No
borra documentos previos ni pertenece a las migraciones Alembic del backend.
Cualquier escritura del corpus invalida su perfil V2, incluido reindexar con
UUID estables; recalibrar en un archivo nuevo. La API exige V2 para verificar
una fila de versión por consulta, sin escanear los vectores. El CLI mantiene
compatibilidad con perfiles V1 para experimentación.

Los casos admiten `expectedDocumentId` UUID opcional. Se informa top-1,
documento esperado entre los primeros cinco fragmentos y MRR@5, separados de
aceptación/rechazo por similitud. Para reproducir sin fuentes externas, indexar
los dos ejemplos y ejecutar:

```powershell
python -m ml.semantic_retrieval.cli calibrate-relevance --cases ml/examples/relevancia/calibracion.json --output ml/artifacts/perfil_v2.json
python -m ml.semantic_retrieval.cli evaluate-relevance --cases ml/examples/relevancia/evaluacion.json --relevance-profile ml/artifacts/perfil_v2.json --output ml/artifacts/evaluacion_v2.json
```

La evaluación rechaza consultas normalizadas o identificadores reutilizados
desde calibración y no modifica el umbral. Estos casos son sintéticos y están
marcados como pendientes de validación humana.

El [registro de 15 procedimientos oficiales](sources/README.md) permite
reconstruir exactamente los textos archivados y sus avisos. El preparador genera
también `retrieval/`: título y cuerpo oficiales, separados de la atribución
editorial. No se mezclan en los embeddings pies de procedencia, URLs o licencias
añadidos por el proyecto. Originales, snapshots y huellas se preservan.

```powershell
python -m pip install -r ml/requirements-corpus.txt
python -m ml.tools.build_procedure_corpus --output ml/data/procedimientos_v1
python -m ml.tools.index_procedure_corpus --corpus ml/data/procedimientos_v1
```

El indexador comprueba UUID, rutas internas, huellas y destino independiente;
carga el modelo una sola vez e indexa todo el corpus en una transacción. Al
cambiar la preparación del texto se genera otro perfil, nunca se reutiliza
automáticamente el corte histórico. Las condiciones de distribución de textos
oficiales y traducciones siguen pendientes de revisión; no se incluyen en Git.

La API optativa, configuración y dependencias de autenticación se describen en
[backend/README.md](../backend/README.md#búsqueda-semántica-protegida-optativa).
