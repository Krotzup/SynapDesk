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

La ejecucion con el CSV completo encontro 2 duplicados exactos, ninguna fila
sin texto y ningun texto con prioridades contradictorias. Encontro tambien
132 candidatos: 113 etiquetados `medium` y 19 `low` pese a contener una señal
lexical de urgencia. Son casos para revisar, no errores confirmados. No se
cambio ninguna etiqueta ni se reentreno el modelo a partir de la lista. La
correccion de prioridades exige criterios funcionales aprobados y revision
humana de los tickets originales.

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

Negaciones explicitas cercanas a la señal, como `no es urgente`, `sin urgencia`
o `no es una emergencia`, no activan la regla. La deteccion es lexical y no
resuelve todos los matices del lenguaje; sus criterios requieren validacion
funcional antes de activar la regla por defecto.

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
| `python ml/audit_ticket_dataset.py --input-csv <ruta>` | Genera una lista local de prioridades para revision humana, sin corregir etiquetas. |
| `python -m py_compile ml/*.py` | Comprueba la sintaxis de los scripts. |
| `python -m unittest discover -s tests` | Ejecuta las pruebas automatizadas. |
| `python ml/train_ticket_classifier.py --enable-business-rules` | Evalua con reglas deterministas aprobadas. |

## Resultados del CSV completo

El 31 de octubre de 2026 se ejecuto el codigo del commit
`5c9942457569555554b08174ee6a960794b4c354` con el CSV identificado arriba,
`--language es` y los demas parametros predeterminados: `test_size=0.2`,
`random_state=42`, `min_target_count=2`, `max_features=120000` y reglas de
negocio desactivadas. Entorno de la ejecucion: Python 3.14.7, pandas 3.0.6,
scikit-learn 1.9.1 y joblib 1.6.0. Las cifras se tomaron del `metrics.json`
generado en esa misma ejecucion.

Para repetirla con una copia autorizada del mismo CSV (verifica su SHA-256
antes de comparar resultados):

```bash
python ml/train_ticket_classifier.py \
  --input-csv "<ruta-local-a-tickets_esp.csv>" \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

| Salida | train_rows | test_rows | Macro F1 | Weighted F1 |
| --- | ---: | ---: | ---: | ---: |
| Clasificacion sugerida (`type`) | 1.789 | 448 | 0,6835 | 0,6899 |
| Prioridad solo modelo (`priority`) | 1.789 | 448 | 0,6225 | 0,6313 |
| Area responsable (`queue`) | 1.789 | 448 | 0,6500 | 0,5992 |

En esta particion, la interseccion de textos entre entrenamiento y prueba fue
0 para cada uno de los tres objetivos.

El CSV completo solo contiene `low`, `medium` y `high` como prioridades. Por
ello, el modelo entrenado con este CSV no puede predecir `critical` por si
solo; la regla experimental puede imponer esa etiqueta cuando se habilita.
Sus criterios funcionales y su evaluacion siguen pendientes. Estas metricas
no miden el efecto de la regla ni constituyen umbrales de aceptacion aprobados.

### Interpretacion segura de la prioridad

La prioridad tuvo Macro F1 de 0,6225 en la particion de prueba. En una prueba
local, el texto `URGENTE: no puedo entrar al correo` produjo `low` con
`confidence` aproximada de 0,638 cuando las reglas estaban desactivadas. Esto
demuestra que esa salida puede contradecir una señal de urgencia; no es una
prioridad lista para aplicarse automaticamente. La probabilidad del clasificador
no se ha calibrado ni validado como medida de seguridad. El agente humano debe
revisar el contexto antes de decidir la prioridad final.

En el CSV completo, 627 tickets contienen una señal detectada por la regla
lexical actual: 495 estan etiquetados `high`, 113 `medium` y 19 `low`.
Tampoco existe la etiqueta `critical` en ese CSV. Por eso activar la regla por
defecto o cambiar la prioridad de salida exige acordar criterios de negocio y
evaluarlos con datos etiquetados para ese fin.

## Verificacion reproducible con la muestra sintetica

Los siguientes resultados proceden de `metrics.json` generado con el commit
`5c9942457569555554b08174ee6a960794b4c354`, la muestra versionada de 12
tickets y el comando de verificacion de arriba. Entorno de esta ejecucion:
Python 3.14.7, pandas 3.0.6, scikit-learn 1.9.1 y joblib 1.6.0. Las reglas de
negocio estuvieron desactivadas.

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

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.
