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

El pipeline actual utiliza `ml/data/raw/tickets_esp.csv`.

- Registros originales: 2.239.
- Registros entrenables: 2.237, despues de eliminar duplicados exactos.
- Idioma: todos los registros tienen `language = es`.
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

## Reglas de negocio

La regla `urgent_priority` fuerza `priority = high` cuando el asunto o cuerpo
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
`rule`, `trigger` y la confianza original del modelo en `model_confidence`.

Para comparar únicamente el resultado estadistico del modelo:

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "URGENTE: no puedo entrar al correo" \
  --body "Necesito recuperar el acceso inmediatamente para trabajar." \
  --disable-business-rules
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
| `python ml/train_ticket_classifier.py --disable-business-rules` | Evalua sin reglas deterministas. |

## Resultados actuales

Metricas Macro F1 sobre el conjunto de prueba:

| Salida | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Clasificacion sugerida | 0,7131 | 0,7120 |
| Prioridad solo modelo | 0,6658 | 0,6859 |
| Prioridad con reglas | 0,6602 | 0,6793 |
| Area responsable | 0,7108 | 0,6479 |

La regla se aplico en 133 casos del conjunto de prueba. La diferencia entre
prioridad solo modelo y prioridad con reglas se debe a que algunos registros
del CSV contienen palabras de urgencia, pero fueron etiquetados como `medium`
o `low`.

## Estado de implementacion

- [x] Dataset en espanol analizado y preparado.
- [x] Entrenamiento de modelos para tipo, prioridad y area.
- [x] Prediccion local mediante artefacto `.joblib`.
- [x] Regla de urgencia compartida entre evaluacion y prediccion.
- [x] Metricas y contrato backend-ML documentados.
- [ ] Integracion del modelo dentro de un backend FastAPI.
- [ ] Pruebas automatizadas del modulo ML.
- [ ] Montaje del modelo dentro de un servicio Docker.

## Documentacion relacionada

- [Pipeline de dataset y modelo](DATASET_ML_PIPELINE.md)
- [Contrato entre backend y ML](../docs/contratos/backend-ml.md)
- [Estrategia de entornos](../docs/arquitectura/entornos.md)

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.
