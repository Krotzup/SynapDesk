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
`urgente` aislada. Estos criterios no definen una asignación nueva de `critical`.
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
contiene tickets ni se aplica automáticamente a otras fuentes. La revisión
asistida no implica aprobación independiente de la responsable de datos.

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
