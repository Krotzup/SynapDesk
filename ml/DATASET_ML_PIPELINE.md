# Pipeline local de dataset y modelo ML

Este pipeline prepara el CSV de tickets en español y entrena modelos para:

- `type` -> clasificacion sugerida del ticket.
- `priority` -> prioridad estimada.
- `queue` -> area responsable.

Para evitar fuga de informacion, el modelo solo usa `subject` y `body` como entrada. No usa `answer`, porque al crear un ticket nuevo esa respuesta todavia no existe.

## Ubicacion local esperada

El CSV actual se guarda localmente en:

```bash
ml/data/raw/tickets_esp.csv
```

Para trabajar con la versión corregida y compartible se admite el par
`tickets_esp_entrenamiento_v2.csv` / `tickets_esp_entrenamiento_v2.manifest.json`.
Se genera con el comando versionado de
[exportación reproducible](CORRECCIONES_PRIORIDAD.md#csv-derivado-para-entrenamiento).
El manifiesto se verifica automáticamente al leer el CSV y conserva la fuente,
correcciones y validación humana en las métricas y el modelo. No reaplicar al
derivado las correcciones del original. La V1 y la propuesta V2 se mantienen
como antecedentes; la V2 vigente registra las 143 decisiones confirmadas.

La carpeta `data/` no se versiona en Git. Lo mismo aplica para los artefactos
generados en `ml/artifacts/`. Para comprobar el pipeline sin usar datos reales
se incluye un dataset sintetico en:

```bash
ml/samples/tickets_esp_sintetico.csv
```

La preparacion normaliza texto y etiquetas, descarta filas sin texto y elimina
duplicados exactos. La auditoria opcional `ml/audit_ticket_dataset.py` genera
un resumen de calidad y una lista local de filas con señales de urgencia y
prioridad `low` o `medium`. Solo registra candidatos a revision humana: no
reetiqueta el CSV ni altera el entrenamiento. Las filas se identifican por su
numero de registro en el CSV original y la lista no copia el texto del ticket.

## Instalacion

Desde la raiz del repositorio:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r ml/requirements.txt
```

## Entrenamiento en español

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

El script genera:

- `prepared_tickets.csv`: dataset limpio y filtrado.
- `ticket_classifier.joblib`: artefacto de modelo listo para cargar desde Python/FastAPI.
- `metrics.json`: metricas por objetivo, incluyendo Macro F1 y Weighted F1.
- `sample_prediction.json`: ejemplo de salida.
- `artifact_manifest.json`: SHA-256 del modelo, versión, entorno, catálogos y
  procedencia del dataset para verificar la entrega antes de cargar Joblib.

El hash verifica identidad e integridad, no la confiabilidad de su origen.
Compartir únicamente artefactos autorizados y conservar el manifiesto junto al
modelo; no aceptar Joblib de usuarios finales.

El script elimina duplicados exactos por texto y etiquetas. La separación
train/test agrupa por texto para que el mismo texto no aparezca en ambos
conjuntos. Si no hay grupos suficientes o la partición de entrenamiento queda
con una sola clase, informa un error sin recurrir a separar filas del mismo grupo.
Los conteos y métricas reproducidos del CSV original están en
[README.md](README.md). Para comparar correcciones sobre los mismos registros,
usar `compare_priority_corrections.py` según
[CORRECCIONES_PRIORIDAD.md](CORRECCIONES_PRIORIDAD.md).

El catálogo vigente es `low`, `medium`, `high`. Se retiraron `critical` y
la regla de urgencia. Las señales léxicas se usan solo para auditar candidatos
a revisión; no cambian predicciones. `--enable-business-rules` se rechaza y
`--disable-business-rules` se conserva por compatibilidad. Los datasets con
prioridades fuera del catálogo se rechazan antes del filtrado de clases raras.

## Verificacion con dataset sintetico

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/samples/tickets_esp_sintetico.csv \
  --language es \
  --min-target-count 1 \
  --max-features 2000 \
  --output-dir ml/artifacts/ticket_classifier_sample
```

Pruebas automatizadas:

```bash
python -m unittest discover -s tests -t . -v
```

## Prediccion local

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "No puedo acceder al correo" \
  --body "Desde la manana Outlook rechaza mi clave y necesito enviar reportes."
```

La salida incluye `clasificacion_sugerida`, `prioridad_estimada` y
`area_responsable`, cada una con confianza y top 3 de clases cuando el
clasificador lo permite. Todos los objetivos incluyen `decision`,
`decision_source`, `rule`, `trigger`, `model_label`, `model_confidence` y
`confidence_source`, con la misma estructura en muestra e inferencia. Los
campos que no aplican son `null`; `top3` conserva el ranking estadístico.
El script rechaza una entrada si tanto el asunto como el cuerpo estan vacios.
La regla opcional ignora negaciones explicitas cercanas a la señal, como
`no es urgente` y `sin urgencia`.

El preprocesamiento de asunto/cuerpo se comparte desde `text_preprocessing.py`.
La muestra de entrenamiento y la inferencia usan `prediction_output.py` para
construir las diez claves de cada objetivo. Para correcciones de etiquetas,
consulta [CORRECCIONES_PRIORIDAD.md](CORRECCIONES_PRIORIDAD.md).

## Modelo elegido

La primera version usa `TF-IDF` + `SGDClassifier(loss="log_loss")` con `class_weight="balanced"`.

Funciona bien como modelo base para SynapDesk porque:

- Es rapido de entrenar y facil de explicar en el informe APT.
- Maneja texto corto y mediano de tickets usando palabras y bigramas.
- Entrega probabilidades para mostrar confianza al agente humano.
- Permite comparar metricas objetivas por salida antes de integrar modelos mas pesados.
- Es liviano para integrarlo despues en FastAPI sin depender de GPU.

Modelos recomendados para comparar en una siguiente iteracion:

- `LinearSVC` calibrado: suele rendir muy bien en clasificacion de texto, pero requiere calibracion para probabilidades.
- `ComplementNB`: baseline muy rapido para datasets grandes y desbalanceados.
- BETO o RoBERTa en espanol: buena opcion cuando el dataset espanol este completo, si las metricas del baseline no alcanzan.

Para el MVP conviene partir por este baseline, medir Macro F1 por `type`, `priority` y `queue`, y recien despues justificar un modelo transformer si mejora lo suficiente frente al costo de complejidad.
