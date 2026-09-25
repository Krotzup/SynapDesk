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

La carpeta `data/` no se versiona en Git. Lo mismo aplica para los artefactos generados en `ml/artifacts/`.

## Instalacion

Desde la raiz del repositorio:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r ml/requirements.txt
```

## Entrenamiento en español

```bash
python ml/train_ticket_classifier.py ^
  --input-csv ml/data/raw/tickets_esp.csv ^
  --language es ^
  --output-dir ml/artifacts/ticket_classifier_es
```

El script genera:

- `prepared_tickets.csv`: dataset limpio y filtrado.
- `ticket_classifier.joblib`: artefacto de modelo listo para cargar desde Python/FastAPI.
- `metrics.json`: metricas por objetivo, incluyendo Macro F1 y Weighted F1.
- `sample_prediction.json`: ejemplo de salida.

El script elimina duplicados exactos por texto y etiquetas, por lo que el CSV
de 2.239 filas produce 2.237 filas entrenables.

Durante la evaluación y la inferencia se aplica por defecto una regla de
negocio: si el asunto o cuerpo contiene señales fuertes como `urgente`,
`urgencia`, `emergencia`, `crítico`, `inmediatamente`, `alta prioridad` o
`caída total`, la prioridad final se fuerza a `high`. La salida informa si la
decisión provino del modelo, de la regla o de ambos. Se puede desactivar con
`--disable-business-rules`.

## Prediccion local

```bash
python ml/predict_ticket.py ^
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib ^
  --subject "No puedo acceder al correo" ^
  --body "Desde la manana Outlook rechaza mi clave y necesito enviar reportes."
```

La salida incluye `clasificacion_sugerida`, `prioridad_estimada` y `area_responsable`, cada una con confianza y top 3 de clases cuando el clasificador lo permite. La prioridad puede incluir `decision`, `rule`, `trigger` y `model_confidence` cuando se aplico una regla.

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
