# Evaluación experimental del clasificador

`evaluate_ticket_classifier.py` compara candidatos locales mediante validación
cruzada por grupos de texto. No cambia la inferencia, activa reglas, exporta un
artefacto de producción ni interpreta una sugerencia experimental como aprobada.
Usa Python 3.12 y las dependencias existentes de `ml/requirements.txt`.

## Datos y correcciones

Usar el CSV original intacto en UTF-8 y conservar su SHA-256. La preparación
comparte las validaciones y normalización del entrenamiento. Un archivo
reexportado con columnas desalineadas no se arregla cambiando su nombre,
ignorando errores de codificación o descartando filas. Conservarlo aparte para
revisión; volver a la fuente antes de preparar otra exportación.

El término «original» en esta guía se refiere al original local
`tickets_esp.csv`, no al archivo externo completo. La
[procedencia documentada](DATASET_PROVENANCE.md) enlaza el archivo exacto de
Hugging Face y distingue los hashes de la fuente externa, la selección/adaptación
local y el derivado V2.

La presencia de «urgente» con prioridad `medium` o `low` es una señal para
revisión, no una contradicción demostrada. Leer el contexto e impacto con
`prioridad-impacto-v1`; una negación o urgencia expresada por el solicitante no
justifica por sí sola subir prioridad. No eliminar palabras para que el texto
coincida con una etiqueta o para mejorar métricas. Una corrección textual real
necesita evidencia y trazabilidad separadas; no forma parte de la normalización.

Las prioridades revisadas se aplican mediante CSV de correcciones y manifiesto
vinculados al original; nunca se sobreescribe el origen. Consultar
[correcciones reproducibles](CORRECCIONES_PRIORIDAD.md). El manifiesto conserva
el estado de validación humana; una evaluación no aprueba sus etiquetas.

La entrega vigente admite el CSV derivado `tickets_esp_entrenamiento_v2.csv`
junto a `tickets_esp_entrenamiento_v2.manifest.json`. Se lee sin volver a
aplicar las correcciones: el lector verifica el sidecar y conserva fuente,
validación y huella del manifiesto en el reporte. La variante se llama `derived`
y la referencia `derived_input_labels`, para no presentar este archivo como
original.
La exportación reproducible y la distribución privada se describen en la guía
de correcciones.

## Candidatos y particiones

| Candidato | Características y clasificador |
| --- | --- |
| `sgd_words` | Baseline vigente: TF-IDF de palabras (1–2) y SGD con log loss. |
| `sgd_words_chars` | Palabras (1–2) más `char_wb` (3–5), con SGD. |
| `logistic_words` | TF-IDF de palabras y regresión logística. |
| `linear_svc_words` | TF-IDF de palabras y LinearSVC, sin probabilidades. |

Se usan cinco particiones `GroupKFold` con mezcla reproducible por semilla,
agrupando el texto preparado completo. Los candidatos reciben exactamente las
mismas particiones. Cada registro aparece una vez en prueba y un texto repetido
permanece en un único grupo, incluso si tiene etiquetas diferentes. No hay
alternativa que separe por filas cuando faltan grupos o clases entrenables.

La vectorización se ajusta dentro de cada entrenamiento: no aprende vocabulario
ni IDF de la prueba. `max_features` limita cada vectorizador; la variante con
caracteres puede utilizar hasta dos veces ese número de características.

El entrenamiento existente admite `--character-ngram-targets` para generar un
artefacto experimental con la unión de palabras y caracteres únicamente en los
objetivos indicados (`type`, `priority`, `queue`). Se registra en configuración
y en un nombre de modelo diferenciado; conserva el formato de inferencia. Sin
esa opción se conserva el baseline en los tres objetivos. Evaluar cada objetivo
antes de adoptar la variante, ya que una mejora de prioridad no garantiza
mejorar tipo o área. Usar un destino nuevo para conservar el modelo anterior:

```text
python ml/train_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --character-ngram-targets priority --output-dir ml/artifacts/ticket_classifier_priority_chars
```

Ejemplo de una línea, válido en PowerShell, CMD y Git Bash:

```text
python ml/evaluate_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --output ml/artifacts/evaluacion_clasificador/modelos.json
```

El objetivo predeterminado es `priority`; también admite `--target type` y
`--target queue`. `--candidates` permite limitar el trabajo y `--folds` controla
el número de particiones. No se reducen silenciosamente por falta de datos.

Para comparar etiquetas originales y corregidas sobre la misma población:

```text
python ml/evaluate_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/annotations/correcciones_prioridad_v2.csv --corrections-manifest ml/annotations/correcciones_prioridad_v2.json --output ml/artifacts/evaluacion_clasificador/correcciones_v2.json
```

Este modo admite solo prioridad. Exige idénticos registros, textos, orden y
campos ajenos a prioridad. Los dos entrenamientos se evalúan contra la referencia
corregida común; `native_metrics` conserva además la referencia propia de cada
entrenamiento. La referencia común no implica que la responsable haya aprobado
las correcciones. Si las correcciones cambian la población preparada, se rechaza
la comparación en lugar de presentar métricas como equivalentes.

## Búsqueda de hiperparámetros optativa

`--tune-hyperparameters` habilita una grilla con tres particiones internas por
grupos (`--inner-folds`). Para SGD prueba `alpha` 1e-5/1e-4; para regresión
logística y LinearSVC, `C` 0.5/1/2. En todos compara `class_weight` balanced/None
y palabras de 1–2/1–3. En la unión, modifica únicamente los n-gramas de palabras.

La selección maximiza Macro F1 en los grupos internos del entrenamiento
externo. El conjunto de prueba externo no elige parámetros. Se informa qué
parámetros se eligieron en cada partición; no se adopta una configuración global
como superior. Es más costoso: limitar candidatos antes de activar la grilla.

## Umbral para high optativo

`--tune-high-threshold` evalúa, únicamente para prioridad, una política
experimental de promoción de `low`/`medium` a `high` cuando la probabilidad de
`high` alcanza un corte. No rebaja una predicción `high` existente.
No utiliza coincidencias léxicas de urgencia ni altera la confianza del modelo.

El corte se elige entre 0.2/0.35/0.5/0.65/0.8/1 usando predicciones fuera de
pliegue **solo del entrenamiento externo**, con grupos internos separados. Se
maximiza F-beta de `high` (`--high-beta`, 2 por defecto experimental). En empate
se prefieren menos falsas alarmas y después el corte mayor. Ni esos candidatos
ni beta constituyen una política aprobada para el producto.

La prueba externa se usa después, una vez congelado el corte. Si también hay
grilla, ambos ajustes permanecen dentro del entrenamiento externo. LinearSVC
registra `not_applicable`, porque no ofrece `predict_proba`; no se inventan
probabilidades. La ausencia de `high` en un entrenamiento interno produce error
explícito. Las probabilidades siguen sin calibración estadística.

Ejemplo acotado:

```text
python ml/evaluate_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --candidates sgd_words --tune-hyperparameters --tune-high-threshold --output ml/artifacts/evaluacion_clasificador/sgd_ajustado.json
```

## Reporte y límites

El JSON registra fuente y correcciones por hash, versiones de Python y seis
dependencias, configuración, catálogo, huella de particiones, conteos y cero
textos compartidos. Incluye métricas por partición, promedio/desviación
poblacional, precisión/recall/F1 por clase y matriz de confusión fuera de
pliegue. Usa el catálogo común para Macro F1; las clases ausentes puntúan cero.
Si no hay `high` real en un pliegue, su recall es `null` y `valid_folds` indica
cuántos pliegues contribuyen al resumen; no se informa un recall perfecto.

Las falsas alarmas de `high` del resumen son conteos por pliegue; el total está
en `oof_metrics.high_detection`. Los resultados con umbral aparecen por
separado. No se guardan textos ni predicciones individuales en el reporte.
El destino debe ser nuevo y se rechaza una fuente que cambie durante la
evaluación. Los reportes permanecen en `ml/artifacts/`, excluido de Git.

Media y desviación describen variación, no significancia estadística. Los
resultados deben identificarse como validación cruzada, no como una evaluación
externa independiente. Datos sintéticos prueban funcionamiento, no calidad real.
La integración FastAPI, taxonomías públicas y embeddings como características
quedan fuera de esta herramienta.

La finalización de estas herramientas experimentales no exige declarar óptimo
el CSV ni promover un modelo. El dataset V2 conserva los textos y solo las
correcciones confirmadas; las señales léxicas restantes se revisan según impacto
y no se convierten automáticamente en nuevas etiquetas. El catálogo vigente se
limita a `low`, `medium` y `high`; América Figueroa confirmó el 10 de noviembre
de 2026 que `critical` y la regla de urgencia se retiren también del dominio. El
alcance solicitado en GitHub es validación cruzada por grupos; obtener otro
corpus independiente no es una condición de cierre de esta rama.

Referencias metodológicas: [GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html),
[validación anidada](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)
y [selección de umbrales](https://scikit-learn.org/stable/modules/classification_threshold.html).
