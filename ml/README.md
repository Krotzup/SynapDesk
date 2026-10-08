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

- Python 3.12 recomendado
- pip
- CSV de tickets en espanol ubicado localmente en `ml/data/raw/tickets_esp.csv`
  o el dataset sintetico versionado en `ml/samples/tickets_esp_sintetico.csv`
  para verificar el pipeline.

El dataset y los artefactos generados no se versionan en Git. Debe confirmarse
la licencia, procedencia y ausencia de informacion sensible antes de compartir
el CSV fuera del entorno local.

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

- Registros originales: 2.239.
- Registros entrenables: 2.237, despues de eliminar duplicados exactos.
- Idioma: todos los registros tienen `language = es`.
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
La separacion evita que textos duplicados queden al mismo tiempo en
entrenamiento y prueba.

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
| `predictions.clasificacion_sugerida.label` | `predictedCategory` | Categoria estimada por el modelo. |
| `predictions.prioridad_estimada.label` | `predictedPriority` | Puede venir del modelo o de una regla aprobada. |
| `predictions.area_responsable.label` | `predictedArea` | Area o cola sugerida. |
| `predictions.*.confidence` | `confidence` o detalle por salida | Confianza estadistica solo cuando `confidence_source = model`. |
| `modelName` | `modelName` | Nombre del artefacto cargado. |
| `modelVersion` | `modelVersion` | Version exacta del entrenamiento. |
| `predictions.*.top3` / `top_3` | metadata adicional | Probabilidades por clase para auditoria y UI. |
| `decision`, `decision_source`, `rule`, `trigger` | metadata adicional | Trazabilidad de reglas y procedencia. |
| `model_label`, `model_confidence` | metadata adicional | Resultado estadistico original cuando hubo regla. |

Si `decision_source = business_rule`, la prioridad final no debe interpretarse
como una prediccion estadistica con certeza total. En ese caso `confidence`
queda en `null` y la confianza del clasificador queda en `model_confidence`.

## Reglas de negocio

Las reglas de negocio estan desactivadas por defecto hasta que el equipo
apruebe sus criterios funcionales. La regla `urgent_priority`, cuando se activa
explicitamente, fuerza `priority = critical` cuando el asunto o cuerpo
contiene señales fuertes de urgencia, por ejemplo:

- `urgente`;
- `urgencia`;
- `emergencia`;
- `critico` o `crítico`;
- `inmediatamente`;
- `alta prioridad`;
- `caida total` o `caída total`;
- `interrupcion total` o `interrupción total`.

Cuando se aplica la regla, la respuesta incluye `decision = business_rule`,
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
| `python -m py_compile ml/*.py` | Comprueba la sintaxis de los scripts. |
| `python -m unittest discover -s tests` | Ejecuta las pruebas automatizadas. |
| `python ml/train_ticket_classifier.py --enable-business-rules` | Evalua con reglas deterministas aprobadas. |

## Resultados actuales

Metricas Macro F1 sobre el conjunto de prueba:

| Salida | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Clasificacion sugerida | 0,7131 | 0,7120 |
| Prioridad solo modelo | 0,6658 | 0,6859 |
| Area responsable | 0,7108 | 0,6479 |

Las reglas deterministas deben medirse aparte con `--enable-business-rules`
despues de aprobar los criterios funcionales de prioridad.

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

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.
