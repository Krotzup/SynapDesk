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

El script elimina duplicados exactos por texto y etiquetas. En la ejecucion
local del 31 de octubre de 2026 con el CSV completo identificado en
[ml/README.md](README.md), 2.239 filas originales dejaron 2.237 entrenables.
`metrics.json` registro 1.789 filas de entrenamiento y 448 de prueba para cada
objetivo. La separacion train/test prioriza grupos por texto para evitar que el
mismo texto aparezca en ambos conjuntos; existe una ruta alternativa de
separacion cuando la agrupacion no se puede usar.

Las reglas de negocio estan desactivadas por defecto mientras se aprueban los
criterios funcionales de prioridad. Si se ejecuta con `--enable-business-rules`,
la regla actual marca como `critical` los tickets cuyo asunto o cuerpo contiene
señales fuertes como `urgente`,
`urgencia`, `emergencia`, `crítico`, `inmediatamente`, `alta prioridad` o
`caída total`. La salida informa si la decision provino del modelo, de la regla
o de ambos, y conserva `model_label` y `model_confidence` separados de la
prioridad final. En decisiones por regla, `confidence` queda en `null` y
`confidence_source` indica que no aplica confianza estadistica para la etiqueta
final.

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
python -m unittest discover -s tests
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
clasificador lo permite. La prioridad puede incluir `decision`,
`decision_source`, `rule`, `trigger`, `model_label`, `model_confidence` y
`confidence_source` cuando se aplico una regla.
El script rechaza una entrada si tanto el asunto como el cuerpo estan vacios.
La regla opcional ignora negaciones explicitas cercanas a la señal, como
`no es urgente` y `sin urgencia`.

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
