# Correcciones reproducibles de prioridad

## Alcance

El CSV fuente no se modifica. Las decisiones humanas se registran en un archivo
aparte y el entrenamiento las aplica en memoria, antes de filtrar idioma,
eliminar duplicados, limitar clases o separar entrenamiento y evaluación.
La inferencia no carga este archivo ni activa reglas por su existencia.

## Criterios `prioridad-impacto-v1`

| Etiqueta | Evidencia necesaria |
| --- | --- |
| `high` | Servicio caído, varios usuarios o área afectados, persona sin poder trabajar y sin alternativa, incidente de seguridad o impacto directo en ventas/facturación/operación. |
| `medium` | Incidencia individual sin bloqueo total, alternativa temporal, lentitud que permite seguir trabajando. |
| `low` | Solicitud, consulta o cambio planificado sin impacto inmediato. |
| Dudoso | Evidencia insuficiente o contradictoria: conservar prioridad y registrar `dudoso` al inicio del motivo. |

Un solo usuario impedido de trabajar sin alternativa puede ser `high`. No
asignar `low` solo porque el tipo sea `request`, ni corregir por la palabra
`urgente` aislada. El catálogo vigente admite solo `low`, `medium` y `high`.
El dominio conserva esa prioridad; el aplicador rechaza introducirla mediante
una corrección hasta acordar su política. Puede conservar una etiqueta existente.

## Archivos

`correcciones_prioridad.csv`, UTF-8, con cabecera y orden exactos:

```csv
numero_fila,prioridad_original,prioridad_corregida,motivo
```

Los números identifican registros CSV del archivo fuente, incluida la cabecera
(primer ticket = 2). Un campo multilínea no incrementa este número. No se usa
el índice después de filtrar ni se confunde con `indice_original` del dataset.
Los motivos describen impacto sin copiar datos sensibles. Los CSV de tickets
y archivos de revisión que contengan información sensible deben guardarse en
`ml/data/` o `ml/artifacts/`, ambos excluidos de Git. Se pueden versionar
anotaciones sin textos ni identificadores personales junto con su manifiesto,
después de revisar su contenido.

`ml/annotations/correcciones_prioridad.csv` contiene las 63 decisiones revisadas
para el original identificado por el manifiesto del mismo directorio. No
contiene tickets ni se aplica automáticamente a otras fuentes. América Figueroa
confirmó la revisión de las 63 decisiones el 5 de noviembre de 2026. Esa es la
fecha de confirmación registrada; la fecha histórica de revisión no se conoce.
La confirmación no certifica todas las etiquetas del dataset ni el modelo.

El manifiesto JSON contiene `source_sha256`, `corrections_sha256` y
`criteria_version`. Los hashes se calculan sobre bytes: cambian al reexportar
el CSV o modificar saltos de línea. Una nueva versión del origen requiere
revisar las correspondencias antes de generar otro manifiesto.

Ejemplo ficticio: si el registro 3 realmente pasa de `low` a `high` por bloqueo
de facturación, escribir `3,low,high,Bloqueo de facturación sin alternativa`.
Para un registro dudoso, repetir la prioridad original y comenzar el motivo con
`dudoso:`. No se generan motivos ficticios para cambios ya realizados por otra persona.

Después de revisar el archivo, generar el manifiesto desde PowerShell:

```powershell
@'
from pathlib import Path
import hashlib, json
source = Path('ml/data/raw/tickets_esp.csv')
corrections = Path('ml/data/correcciones_prioridad.csv')
payload = {
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'corrections_sha256': hashlib.sha256(corrections.read_bytes()).hexdigest(),
    'criteria_version': 'prioridad-impacto-v1',
}
Path('ml/data/correcciones_prioridad.json').write_text(
    json.dumps(payload, indent=2), encoding='utf-8')
'@ | python -
```

Ejecutar entrenamiento (una línea, válida también en CMD):

```text
python ml/train_ticket_classifier.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/data/correcciones_prioridad.csv --corrections-manifest ml/data/correcciones_prioridad.json --output-dir ml/artifacts/ticket_classifier_es
```

Para reproducir las anotaciones incluidas en el repositorio, usar
`--corrections-csv ml/annotations/correcciones_prioridad.csv` y
`--corrections-manifest ml/annotations/correcciones_prioridad.json`. Su
manifiesto ya está generado; no regenerarlo para hacer coincidir otro origen.

El entrenamiento rechaza hashes incompatibles, registros repetidos o
inexistentes, prioridades originales distintas, etiquetas desconocidas, motivos
vacíos y casos dudosos que pretendan cambiar la etiqueta. Las métricas registran
hashes, versión de criterios, registros revisados, cambiados y dudosos.

## Evaluación

### Registro de validación humana

El manifiesto admite `validation: {"status": "pending"}`. La ausencia de este
campo en manifiestos anteriores también significa pendiente; no se interpreta
la lectura asistida ni la ejecución de pruebas como aprobación humana.

Solo después de que la persona responsable revise todas las decisiones,
incluidos los casos dudosos, puede declarar `validation` con estos campos:

| Campo | Requisito |
| --- | --- |
| `status` | `validated` |
| `reviewer` | Identidad no vacía de quien efectivamente validó. |
| `validated_at` | Fecha y hora ISO 8601 en UTC, con `Z` o `+00:00`. |
| `reviewed_rows` | Número entero de decisiones del CSV, no solo las modificadas. |

El lector valida estructura, fecha y cantidad, y conserva esta declaración en
la procedencia de métricas/artefactos. No acredita la identidad del firmante ni
realiza la revisión por él. En el manifiesto versionado `validated_at` registra
la confirmación explícita de América Figueroa el 5 de noviembre de 2026;
`validation_note` distingue esa confirmación de una fecha histórica desconocida.
Cambiar fuente o correcciones requiere revisar nuevamente sus hashes y la
validación vinculada a ellos.

### CSV derivado para entrenamiento

`export_training_dataset.py` produce un CSV UTF-8 con BOM y un manifiesto del
mismo nombre base. Conserva todos los campos y registros originales y modifica
únicamente las prioridades anotadas. No borra palabras de urgencia ni elimina
duplicados en la exportación; la preparación de entrenamiento hace su propia
deduplicación. Rechaza archivos destino existentes y correcciones incompatibles.

```text
python ml/export_training_dataset.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/annotations/correcciones_prioridad.csv --corrections-manifest ml/annotations/correcciones_prioridad.json --output-csv ml/data/raw/tickets_esp_entrenamiento_v1.csv
```

Con el original identificado por las anotaciones se conservan 2.239 registros:
37 cambios `medium` a `high`, uno `low` a `medium` y 25 casos dudosos sin cambio.
Estos conteos describen las decisiones registradas; no convierten todos los
candidatos léxicos de la auditoría en errores ni aprueban una taxonomía nueva.

El par compartible es `tickets_esp_entrenamiento_v1.csv` y
`tickets_esp_entrenamiento_v1.manifest.json`. Distribuirlo por un medio privado
autorizado mientras se verifican licencia y datos sensibles. Mantenerlo en
`ml/data/raw/`, excluido de Git; los colaboradores también pueden regenerarlo
desde la misma fuente y las anotaciones versionadas. No hay descarga automática
ni credenciales en el repositorio. El frontend no consume estos archivos.

El lector detecta el manifiesto junto al CSV, verifica nombre, hash y conteos,
y conserva la procedencia y validación en métricas y artefactos. Si se renombra
el CSV, actualizar también el nombre del manifiesto y su campo `dataset_file`,
sin cambiar el hash si los bytes siguen iguales. Al copiar solo el CSV se pierde
esa procedencia, aunque conserve un formato válido.

Para usar el derivado, pasar solo `--input-csv`: **no** volver a proporcionar
`--corrections-csv` ni `--corrections-manifest`. La reaplicación es rechazada.

```text
python ml/train_ticket_classifier.py --input-csv ml/data/raw/tickets_esp_entrenamiento_v1.csv --character-ngram-targets priority --disable-business-rules --output-dir ml/artifacts/ticket_classifier_training_v1
```

Para comparar con varias particiones agrupadas, candidatos y ajustes internos,
consultar [evaluación experimental](CLASSIFIER_EVALUATION.md). El siguiente
comando histórico conserva su comparación con una sola partición.

### V2 confirmada: revisión de los 80 candidatos restantes

`ml/annotations/correcciones_prioridad_v2.csv` conserva las 63 decisiones de V1
y añade la revisión asistida de los 80 candidatos solicitados, leyendo asunto y
cuerpo originales y sin consultar predicciones. Se aplican los mismos criterios
`prioridad-impacto-v1` del PR #13; no se modifica texto ni se decide por la
presencia de «urgente».

De los 80 casos nuevos se proponen 24 cambios: 18 `medium` a `high`, uno `low` a
`high` y cinco `low` a `medium`. Se conservan 56 etiquetas: 34 casos dudosos y 22
casos cuyo contexto permite mantener su prioridad. Las descripciones truncadas
o sin evidencia de impacto se conservan como dudosas.

La V2 completa contiene 143 decisiones y 62 cambios respecto al original.
América Figueroa confirmó explícitamente las 80 decisiones nuevas el 5 de
noviembre de 2026. El manifiesto `correcciones_prioridad_v2.json` registra
`validation: validated` para las 143 decisiones y conserva separadamente las
confirmaciones de las 63 anteriores y las 80 nuevas. La V1 se conserva intacta.

```text
python ml/export_training_dataset.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/annotations/correcciones_prioridad_v2.csv --corrections-manifest ml/annotations/correcciones_prioridad_v2.json --output-csv ml/data/raw/tickets_esp_entrenamiento_v2.csv
```

El conjunto de los 126 candidatos léxicos originales queda cubierto por una
decisión registrada en V2; esto no significa que todos sean errores ni que la
validación de anotaciones sea una evaluación independiente del modelo. La
retirada de `critical` y su regla fue confirmada posteriormente por América Figueroa y está implementada en esta rama.

La entrega vigente es `tickets_esp_entrenamiento_v2.csv` junto a
`tickets_esp_entrenamiento_v2.manifest.json`. La copia con sufijo `_propuesto`
corresponde al estado anterior a la confirmación y se conserva como antecedente.
El CSV confirmado tiene los mismos bytes; cambian el nombre y la validación
documentada en su manifiesto. No se vuelven a aplicar correcciones al entrenarlo:

```text
python ml/train_ticket_classifier.py --input-csv ml/data/raw/tickets_esp_entrenamiento_v2.csv --character-ngram-targets priority --disable-business-rules --output-dir ml/artifacts/ticket_classifier_training_v2
```

Comparar las versiones original y corregida con reglas desactivadas. Mantener
grupos y particiones comparables; declarar cambios de población por filtrado.
Revisar Macro F1, métricas por clase y errores que rebajan `high`. No cambiar
etiquetas para incrementar una métrica. Los candidatos de la auditoría léxica
requieren lectura humana; no son errores confirmados ni cubren todos los casos.

### Comparación controlada desde el original

Usar la descarga original intacta como `--input-csv` en ambos experimentos.
Una copia reexportada desde Excel puede haber cambiado textos, columnas o
registros, aunque tenga el mismo nombre. Comprobar su SHA-256 antes de usarla.

```text
python ml/compare_priority_corrections.py --input-csv ml/data/raw/tickets_esp.csv --corrections-csv ml/annotations/correcciones_prioridad.csv --corrections-manifest ml/annotations/correcciones_prioridad.json --output-dir ml/artifacts/priority_comparison --random-state 42
```

El comando entrena dos veces: sin correcciones y con ellas, siempre sin reglas.
Exige la misma población preparada, orden, textos y demás campos; solo admite
diferencias de prioridad. Si el filtrado o la deduplicación cambian la población,
falla antes de entrenar. Verifica también la misma partición, con grupos por
texto y semilla fija. No modifica el original ni ajusta motivos con predicciones.

`comparison.json` registra hashes de origen, población y partición, conteos,
Macro F1, Weighted F1, precisión/recall/F1 por clase y matrices de confusión:

- `native_reference`: cada modelo evaluado con sus propias etiquetas de prueba.
  Sirve para reproducir cada entrenamiento. Si cambiaron las etiquetas, sus
  valores no demuestran por sí solos una mejora.
- `common_corrected_reference`: ambos modelos evaluados contra las mismas
  etiquetas revisadas de los mismos tickets. Esta es la comparación principal.
  La referencia revisada sigue requiriendo validación de la responsable de datos.
- `high_detection`: cantidad de `high` según la referencia, detectados,
  omitidos, falsas alarmas y recall. Si no hay `high`, el recall es `null`.

Los directorios `baseline/` y `corrected/` conservan sus métricas y artefactos.
Una corrección trazable no garantiza mejorar el rendimiento: informar también
regresiones y no adoptar un modelo como superior sin evidencia. Las notas de
revisión y publicación corresponden al PR, no a documentos permanentes del módulo.
