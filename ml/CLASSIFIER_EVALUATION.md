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

## Comparación con el catálogo vigente

El 12 de noviembre de 2026 se evaluaron los cuatro candidatos en `type`,
`priority` y `queue` con el derivado V2 validado. Se usó el evaluador de
`71f6b85` y Python 3.12.4 con las versiones de `ml/requirements.txt`.
Se conservaron 2.237 tickets en 2.237 grupos de texto. Los tres objetivos y
todos los candidatos compartieron cinco particiones con semilla 42, sin textos
compartidos entre entrenamiento y prueba. Se usaron configuraciones base, con
el catálogo `low`, `medium`, `high` y las reglas desactivadas.

- SHA-256 del CSV V2: `a3792862678c009ca66dad41aeb3e1fbc0a55d4213fd3c39e5cd2e6586e6740a`.
- SHA-256 del manifiesto V2: `489d95ba95c58cb38de279fc257631742472b2ab995ee9870efa6284aa57f1a1`.
- SHA-256 de las particiones: `22f72d96ef11508f6c12a2303597f00dbc4257fcb0e64d754fa3cd21b101ad1f`.

Cada celda muestra Macro F1 medio ± desviación poblacional / Weighted F1 medio.

| Candidato | Tipo | Prioridad | Cola |
| --- | --- | --- | --- |
| `sgd_words` | 0,6921 ± 0,0147 / 0,6948 | 0,6577 ± 0,0266 / 0,6865 | 0,6566 ± 0,0364 / 0,6290 |
| `sgd_words_chars` | 0,6816 ± 0,0180 / 0,6874 | 0,6598 ± 0,0231 / 0,6883 | 0,6481 ± 0,0581 / 0,6247 |
| `logistic_words` | 0,6617 ± 0,0155 / 0,6647 | 0,6239 ± 0,0258 / 0,6497 | 0,5643 ± 0,0185 / 0,5277 |
| `linear_svc_words` | 0,6955 ± 0,0155 / 0,7005 | 0,6556 ± 0,0203 / 0,6839 | 0,6457 ± 0,0181 / 0,6266 |

Para prioridad, los caracteres detectaron 741 de los 980 casos `high`, con
214 falsas alarmas. El baseline detectó 733 con 212 falsas alarmas. El
incremento observado es de 8 detecciones y 2 falsas alarmas. Los resultados
reproducen los Macro F1 medios de ambos SGD ya documentados para prioridad.

El equipo acordó dar más peso a detectar tickets de prioridad `high` que
a evitar que un ticket `low` o `medium` se sugiera como `high`. El agente
conserva la decisión final sobre la prioridad. Se aprobó usar SGD de palabras
y caracteres para sugerir prioridad. Tipo y cola usan SGD de palabras.
SGD obtuvo el mayor Macro F1 en cola. LinearSVC obtuvo el mayor Macro F1
observado en tipo, por 0,0034 sobre SGD, y requeriría resolver la ausencia de
probabilidades antes de considerarlo para la salida actual. Las diferencias
son descriptivas.

Para repetir la comparación, colocar el CSV y su manifiesto V2 juntos en la
ruta indicada o ajustar `$dataset`. Usar un directorio de salida nuevo.

```powershell
$dataset = 'ml/artifacts/mejoras_clasificador_tickets/final_v2/tickets_esp_entrenamiento_v2.csv'
$output = 'ml/artifacts/evaluacion_clasificador_vigente/reproduccion'
foreach ($target in 'type', 'priority', 'queue') {
    python -X utf8 ml/evaluate_ticket_classifier.py --input-csv $dataset --target $target --output "$output/$target.json"
    if ($LASTEXITCODE -ne 0) { throw "Falló la evaluación de $target" }
}
```

### Artefacto verificado para la variante aprobada

Se generó y verificó la carga del Joblib `20261112173515` con caracteres
solo para prioridad. Su SHA-256 es
`60a167ea7ca6ae94f6008e61385c62aff3defb8de4c6d7c62a0e76c760e85173`.
El manifiesto, el modelo y sus métricas están en
`ml/artifacts/evaluacion_clasificador_vigente/modelo_prioridad_caracteres/`.
Una inferencia con un ticket sintético devolvió los tres objetivos con
confianza y alternativas, con reglas desactivadas y el catálogo vigente.

El entrenamiento del artefacto reservó 448 registros para prueba y usó 1.789
para entrenar, sin textos compartidos. Su Macro F1 / Weighted F1 fue
0,6835 / 0,6899 en tipo, 0,6451 / 0,6670 en prioridad y 0,6500 / 0,5992
en cola. Esta partición pertenece al mismo corpus V2 usado en la comparación
y sus resultados son descriptivos. La tabla anterior resume los cinco pliegues.

```powershell
python -X utf8 ml/train_ticket_classifier.py --input-csv $dataset --character-ngram-targets priority --output-dir "$output/modelo_prioridad_caracteres"
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
en `oof_metrics.high_detection`. El reporte guarda métricas agregadas.
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
[validación anidada](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).
