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
Los motivos describen impacto sin copiar datos sensibles. Los archivos reales
deben guardarse en `ml/data/` o `ml/artifacts/`, ambos excluidos de Git.

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

## Exportación de Excel con columnas encapsuladas

Para el caso observado (una fila CSV con comas dentro de la primera de tres
columnas externas separadas por punto y coma), hay una utilidad acotada:

```text
python ml/reconcile_ticket_export.py --original "ruta/csv original.csv" --edited "ruta/tickets_esp_utf8.csv" --original-encoding cp932 --output-dir ml/artifacts/data_reconciliation
```

CP932 es la codificación comprobada de esa referencia concreta; no se adopta
como codificación general del dataset. El editado debe ser UTF-8. El resultado
usa la información editada y la referencia solo para comprobar la estructura.
Si se eliminó un tag junto con su separador y la correspondencia es única,
se restituye una celda vacía; no se recupera el valor eliminado. No se reparan
cuerpos/respuestas ambiguos. Los registros se conservan completos en el JSON
de revisión, separados de la copia entrenable; el informe cuenta ambos grupos,
registra cada reparación y conserva hashes para comprobar reproducibilidad.

Esta separación estructural no sustituye la revisión semántica de prioridades.
Las métricas de una copia parcial deben indicar cuántos registros quedaron
fuera del entrenamiento y no atribuirse al archivo completo.
