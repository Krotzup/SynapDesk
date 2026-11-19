# Evaluación RAG: matriz EA3, sección 2.4

Fuente: extracto aportado por la responsable del proyecto del documento del
curso **Gestión de Datos e Inteligencia Artificial**, versión corte EA3,
sección **2.4 Matriz de Evaluación RAG y Métricas**. El documento completo no
está en el repositorio y no se ha revisado. Esta especificación implementa
el extracto recibido; no declara una evaluación realizada ni un umbral
global de producción aprobado.

| Caso | Tema | Criterio recibido |
| --- | --- | --- |
| RAG-001 | Red corporativa | Al menos un fragmento relevante en los tres primeros: Precision@3 ≥ 1/3 |
| RAG-002 | Impresora | Primer resultado relevante en posición 1–3: rango recíproco ≥ 1/3 |
| RAG-003 | Correo | Fuente esperada entre los cinco primeros; registrar Recall@5 |
| RAG-004 | Sin documentación | Fallback correcto y ninguna fuente ni cita inventada |
| RAG-005 | Términos ambiguos | Promedio de relevancia humana del equipo ≥ 4 |

Además, un resultado apto necesita fuentes visibles y citas conservadas y
revisadas. No se añade una escala máxima de puntuación ni se deducen etiquetas
desde el score del recuperador: ambas cosas requieren evidencia del equipo.
Los criterios de recuperación no autorizan un umbral de similitud del servicio.

## Registro y cálculo reproducible

`backend/herramientas/evaluar_matriz_rag.py` consume un JSON local con una lista
`records`, un registro por caso. No llama a Gemini, no altera el corpus ni
genera etiquetas. Conservar consultas, respuestas e informes bajo `artifacts/`
(excluido de Git); utilizar únicamente datos sintéticos o anonimizados autorizados.

Cada registro incluye estos campos obligatorios:

| Campo | Contenido |
| --- | --- |
| `caseId`, `evaluatedAt`, `commit` | Caso, fecha ISO con zona horaria, SHA completo de 40 caracteres |
| `indexedDocumentIds` | Inventario de documentos indexados de esa ejecución |
| `models` | Nombres/versiones exactos en `retrieval` y `generation` |
| `query`, `topK` | Consulta y límite solicitado, entre 1 y 20 |
| `executionKind`, `dataKind` | `live` o `fixture`; `synthetic` o `anonymized_real` |
| `annotationStatus` | `pending` o `reviewed_independently`, según la revisión real |
| `results` | Orden de búsqueda original: `chunkId`, `documentId`, `score`, `relevant` (booleano o null), `judgedBy` |
| `groundTruth` | `relevantDocumentIds`, `expectedDocumentId` (o null), `complete` |
| `rag` | `outcome` (`draft` o `fallback`), `content`, `sourceChunkIds`, `sourcesVisible`, `fallbackAppropriate`, `citations` |
| `rag.citations` | Todas las citas de la respuesta: `chunkId`, `supportsClaim` (booleano o null), `reviewedBy` |
| `humanReviews` | Revisión del equipo: `reviewer` (identificador seudónimo), `rating`; lista vacía si pendiente |
| `observations` | Limitaciones, revisión del fallback, versión del corpus y contexto de la ejecución |

Los booleanos de visibilidad y fallback admiten null si aún no se revisaron.
La revisión humana debe cotejar la respuesta completa con el inventario de
citas; el evaluador no interpreta lenguaje natural ni acredita por sí solo
que una afirmación esté sustentada. Identificar por separado a quien etiquetó
y a quien revisó de forma independiente, conservando el procedimiento en las
observaciones. No cambiar `annotationStatus` para eludir esa revisión.

Desde la raíz del repositorio, con el entorno del backend activo:

```powershell
$env:PYTHONPATH = 'backend;.'
python -m herramientas.evaluar_matriz_rag --records artifacts/mi-evaluacion.json --output artifacts/informe-ea3.json
```

El destino debe ser nuevo y estar bajo `artifacts/`; nunca sobrescribe evidencia.
Los errores no imprimen consultas, respuestas ni rutas privadas.
Se conservan fecha, commit, modelos, inventario, top K, juicios, salida RAG y
observaciones originales junto al resultado calculado de cada caso.

Precision@K usa fragmentos y divide por K, incluso si se recuperan menos
resultados. Recall@5 usa documentos distintos sobre un catálogo completo de
fuentes relevantes, porque el criterio recibido habla de la fuente esperada.
Sin catálogo completo se registra null. El rango recíproco es 1/posición del
primer acierto; MRR es su promedio sobre los casos de recuperación presentes
(excluye RAG-004). Los juicios pendientes anteriores al primer acierto impiden
calcular el rango. El score promedio requiere juicios completos.

Exactitud de citas es la proporción de citas trazables que un revisor confirma
que sustentan la afirmación; sin revisión queda null. Una fuente desconocida
falla aunque las demás citas sean correctas. La tasa de fallback correcto se
calcula sobre RAG-004 e impide inventar fuentes o citas.

El informe distingue `apto`, `no_apto` y `pendiente`. Los fixtures, casos
faltantes o revisiones incompletas impiden declarar la suite apta. Un resultado
`apto` con consultas sintéticas solo acredita esa suite: **no sustituye la
evaluación con consultas reales anonimizadas ni la autorización productiva**.
`productionApproved` siempre es false. Las pruebas unitarias son sintéticas y
solo verifican el evaluador; no son resultados del modelo.

## Pendiente de ejecución y ratificación

Faltan el documento completo o su enlace, consultas reales anonimizadas,
etiquetas revisadas de forma independiente y los cinco registros de ejecución
con recuperación/modelos reales. Después corresponde contrastar esta
implementación con el documento completo, ejecutar la matriz y proponer un
umbral con esos datos. El límite de generaciones exige además latencia,
consumo y cuota de Gemini; no se deduce de esta matriz.
