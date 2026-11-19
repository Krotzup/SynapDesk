# Integración de pendientes del MVP

19 de noviembre de 2026. **Implementación preparada para revisión del equipo.**
Las decisiones de este incremento son una propuesta ejecutable solicitada para
completar los pendientes; no se presentan como aprobación histórica del PO o
como despliegue productivo. Este documento actualiza los pendientes específicos
de filtros, estados, clasificación e ingestión de los contratos anteriores.

## Condiciones pendientes antes del merge

La revisión de `2e6beb7` no constituye aprobación. Registrar expresamente en el
PR quién ratifica cada decisión; ninguna casilla se considera aprobada por
aparecer en el código o por pasar CI:

- [ ] PO/equipo: tabla de transiciones y política de `resolvedAt` (HU04).
- [ ] PO/equipo: precondición y códigos 409, semántica de filtros.
- [ ] PO/equipo: formatos/límites de documentos y mapeos por variables (HU05/HU06/EQUIPO).
- [ ] PO/equipo: resolver la contradicción entre «Aceptar y resolver» del 03-11
  y «aceptar no resuelve» del #59. La implementación conserva el comportamiento
  del #59 mientras se decide; no se interpreta como una ratificación nueva.
- [ ] Felipe: revisar tickets, autenticación, origen alternativo de identidad,
  registro optativo de rutas habituales y preparación de Render.
- [x] Valentina: interfaz revisada y conforme sobre `607482a`, según la
  devolución compartida por el solicitante el 19-11-2026. La aprobación formal
  en GitHub sigue pendiente de las ratificaciones del PO/equipo y Felipe.

La segunda revisión declara resueltos los puntos técnicos de la ronda anterior
y conformes filtros, precondición de estado, gestión documental, predicción,
citas e historial. Esta constancia registra la devolución recibida; no emite
una aprobación en nombre de la revisora ni extiende la conformidad a cambios
posteriores de implementación. La revisora no verificó localmente PostgreSQL,
Alembic/ML, navegador ni despliegue Render; su entorno fue macOS.

El PR mantiene este alcance integrado a petición del solicitante. Se explicita
la excepción al criterio de una tarea por PR; cada responsable debe revisar su
parte antes del merge. No se atribuye aprobación al equipo sin evidencia.

### Perfil de demo

El lanzador `ingreso_local/demo.py` fija `DOCUMENTS_ENABLED=false`, incluso si
el entorno heredado lo activa. Las páginas y rutas de gestión ya pueden atravesar
el ingreso de testing, pero las escrituras documentales permanecen cerradas en
esa demo para conservar el perfil V2. Un ensayo separado de carga debe configurar
el origen, indexador y base semántica propios. Para habilitar gestión documental
durante una demo futura, el equipo debe nombrar operador y ventana de
recalibración; no se recalibra ni se reutiliza un umbral automáticamente.

El sello de ingreso local ahora se exige también para documentos y predicciones
antes de su autorización de sesión/CSRF; SSR permite únicamente las nuevas
navegaciones y lecturas acotadas. Esto no acredita ingreso productivo AUTH-07D.3.

## Tickets, filtros y estados

`GET /api/v1/tickets` combina `search`, `status`, `priority`, `category` y `area`
con AND. Estado/prioridad usan los catálogos del dominio; categoría/área son
coincidencias exactas sobre **valores confirmados**, no sobre predicciones.
`search` busca subcadenas sin distinguir mayúsculas en título, descripción,
categoría, área, nombre del creador y UUID textual. `%` y `_` son literales.
No se promete equivalencia de acentos. Textos de filtro: hasta 150 caracteres,
sin NUL; espacios exteriores recortados. Parámetros desconocidos o repetidos
responden 422. Página desde 1, tamaño de 1 a 100. El conteo y los resultados
comparten snapshot y orden estable por creación/UUID descendentes.

`PATCH /api/v1/tickets/{id}` admite `status` y `expectedStatus` opcional. El
frontend envía ambos; los clientes anteriores pueden seguir omitiendo la
precondición. El backend bloquea la fila y compara el estado dentro de la misma
transacción. Una comparación fallida responde 409 `TICKET_STATE_CONFLICT`.
La precondición detecta cambios de estado, no revisiones generales ni un ciclo
que termine de nuevo en el mismo estado.

| Estado actual | Destinos permitidos |
| --- | --- |
| `open` | `in_progress`, `resolved` |
| `in_progress` | `open`, `resolved` |
| `resolved` | `in_progress`, `closed` |
| `closed` | `in_progress` |

Enviar el estado actual es idempotente. Otros saltos responden 409
`TICKET_TRANSITION_INVALID`. Resolver fija `resolvedAt` con el reloj del servidor;
cerrar conserva la fecha; reabrir limpia la fecha. No se rellenan fechas
históricas desconocidas. Cambiar estado no altera prioridad/categoría/área.
Se conserva la autorización y revalidación transaccional de sesiones y CSRF.

Las rutas habituales de tickets se registran solo con
`TICKETS_HTTP_ENABLED=true`, `APPLICATION_PUBLIC_ORIGIN`, perfil de cookies,
canal SEC-01B, base y políticas de autenticación configurados. El ensayo local
registra sus propias rutas. Este incremento no activa login de producción ni
sustituye la acreditación de procedencia IP pendiente de AUTH-07.

## Clasificación

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | `/api/v1/tickets/{id}/prediction` | Última predicción persistida, o `null` si no hay |
| POST | `/api/v1/tickets/{id}/prediction` | Obtiene/persiste la estimación del artefacto actual |

POST recibe `{}`; exige sesión de agente/administrador, Origin y CSRF.
La lectura exige sesión y el mismo canal interno. Respuestas privadas sin caché.
El ticket debe existir. Sin servicio preparado, POST responde 503
`CLASSIFICATION_UNAVAILABLE`. GET puede leer predicciones históricas aunque la
inferencia esté deshabilitada. Cada predicción conserva ID, ticket, fecha y
versión; la migración `0008_predicciones_ticket` es explícita.

`CLASSIFIER_ENABLED=true` carga una vez por proceso los mismos bytes cuyo SHA-256
coincide con `CLASSIFIER_MODEL_SHA256`, desde `CLASSIFIER_MODEL_PATH`. Un checksum
no convierte un Joblib de origen desconocido en seguro. No se entrena durante
peticiones. La creación de tickets intenta guardar una estimación después de
confirmar el ticket; un fallo ML deja el ticket creado. El detalle permite
solicitarla para tickets previos. Texto, hash del artefacto y mapeos determinan
una clave única: repetir la inferencia con esa entrada reutiliza el resultado.

La representación conserva `MlPrediction` y agrega `predictedType`,
`suggestedQueue` y `confidences: {type, priority, queue}`. Se exige probabilidad
finita en [0,1] por objetivo y el catálogo `low|medium|high` de prioridad.
`confidence` global permanece `null`; no se agregan probabilidades.
`predictedCategory` y `predictedArea` permanecen `null` salvo correspondencia
explícita en `CLASSIFIER_CATEGORY_MAPPING` y `CLASSIFIER_AREA_MAPPING`.
El tipo `incident` no se convierte por sí solo en una categoría temática.

La interfaz muestra estas salidas como predicción, su modelo y versión, y
separa tipo de categoría. No modifica los valores confirmados del ticket ni
presenta la probabilidad como garantía de acierto. **Falta entregar/configurar
un artefacto autorizado y los catálogos acordados para activar datos reales.**

## Documentos

Lecturas (`GET /documents`, `GET /documents/{id}`): agentes y administradores.
Carga y retiro (`POST /documents`, `DELETE /documents/{id}`): administradores,
con Origin/CSRF. `DOCUMENTS_ENABLED=true`, base semántica separada y origen de
aplicación son obligatorios. No depende de la clave ni de habilitar Gemini.

Carga `multipart/form-data`: `file`, `title` (1–150 caracteres recortados) y
`description` opcional (hasta 2.000). Solo `.txt` y `.md`, hasta 64 KiB,
decodificación UTF-8 estricta con BOM opcional. Se rechazan archivos vacíos,
controles binarios y nombres con rutas. No se usa el MIME declarado como prueba
de formato. PDF/DOCX requieren una ampliación con extractores; no se aceptan
archivos que este incremento no pueda procesar.

La carga es síncrona y responde 201 `processed` después de fragmentar con el
tokenizador del modelo (96 tokens, solapamiento 16), limitar a 128 fragmentos y
generar los embeddings locales. Comparte modelo y lock con búsqueda cuando
está disponible. Puede iniciar un indexador independiente de un perfil de
relevancia, para permitir el primer ingreso. Ficha, texto y vectores confirman
en **una transacción de la base semántica**; los fallos revierten juntos.
No se devuelve un estado `processed` antes de esa confirmación.

`semantic_uploaded_documents` se prepara mediante el `init-db` semántico
existente; no se crea esquema durante solicitudes. El listado gestiona las
cargas web; el corpus oficial importado por CLI conserva su gestión por CLI.
Esta limitación se comunica en la pantalla. La ficha conserva una instantánea
pública del autor porque ambas bases están separadas.

El retiro es lógico y repetible: marca fecha/actor y elimina los vectores y
metadatos de búsqueda en la misma transacción. La ficha deja de aparecer en
lecturas públicas. Las fuentes de borradores anteriores son instantáneas en la
base de tickets y permanecen intactas.

Cada inserción/retiro de fragmentos invalida el perfil V2 por sus triggers.
La búsqueda responderá `SEARCH_PROFILE_STALE` hasta recalibrar y cargar el
perfil de la revisión nueva. No se actualiza artificialmente su revisión ni
se conserva un umbral como si hubiera sido reevaluado.

| Código | HTTP | Caso |
| --- | --- | --- |
| `DOCUMENT_FORMAT_UNSUPPORTED` | 422 | Extensión no admitida |
| `DOCUMENT_TOO_LARGE` | 413 | Bytes o fragmentos excedidos |
| `VALIDATION_ERROR` | 422 | Formulario, texto o metadatos no válidos |
| `DOCUMENT_INDEXING_FAILED` | 503 | Error de fragmentación/embeddings |
| `DOCUMENTS_NOT_READY` | 503 | Falta preparar esquema |
| `DOCUMENTS_UNAVAILABLE` | 503 | Servicio/base no disponibles |
| `DOCUMENT_NOT_FOUND` | 404 | Documento inexistente o retirado |

Los errores usan el envoltorio común sin detalles del proveedor/SQL. No se
reintentan automáticamente cargas con resultado incierto. Los datos de ejemplo
no simulan una indexación real.

## Asistente y despliegue

El [contrato RAG](recomendaciones-rag-v1.md) ya implementa abstención, salida
inválida y dependencia caída. La interfaz ahora diferencia esos mensajes y
enlaza las citas `[fragmentId, ...]` a sus fuentes conservadas; una referencia
desconocida no genera un enlace inventado. Las revisiones del historial muestran
fecha, comentario y versión modificada cuando existen.

[Render](../../infra/render/README.md) incluye Blueprint, imagen ligera, opción
ML y arranque TLS. La configuración queda preparada; faltan acceso al servicio,
certificados, artefactos y validación operativa. No se afirma que haya un
despliegue realizado ni se activan rutas/ML productivos por defecto.

## Validación local

### Repetición del recorrido RAG con db_test exclusiva

Tras conciliar el #62 integrado en main, se repitieron en Windows/Edge los
escenarios del lanzador `--rag --rag-fixture draft` y
`--rag --rag-fixture abstention`, con la composición de testing y una base
temporal propia en loopback:5433 por ejecución. Se verificó la búsqueda nueva
junto con el Asistente, sesiones y CSRF reales, fuentes navegables y persistencia
SQL. El driver valida los enlaces de citas renderizados, no el UUID crudo del
contenido que la interfaz transforma.

El borrador respondió 201 y su aceptación 204 persistió después de recargar;
la abstención respondió 422 `INSUFFICIENT_INFORMATION`, sin recomendación
guardada ni cambio de estado del ticket. Ambas ejecuciones finalizaron con
cierre de Next/FastAPI y eliminación de su base temporal. Los informes locales
quedan bajo `artifacts/rag-integrado-draft-v3.json` y
`artifacts/rag-integrado-abstention-v1.json`, excluidos de Git.
Los proveedores de recuperación/generación son sintéticos en estos recorridos:
esto acredita integración y revisión humana, no calidad, tokens o latencia de
Gemini real. La matriz MLOps, consultas reales anonimizadas con etiquetas
independientes, cuota del proyecto Gemini, artefacto autorizado y mapeos siguen
pendientes y se solicitaron en un comentario del PR #60.

Se aprobaron además 39 integraciones PostgreSQL del conjunto conciliado y
48 pruebas Node del protocolo de ingreso. El alcance adicional se limita a la
parte ML/LLM/RAG; HU10 queda fuera de esta ronda por indicación del solicitante.

### Evidencia anterior

Pasaron 1.063 pruebas unitarias del backend y 474 de integración con PostgreSQL,
con Alembic `upgrade/current/heads/check` y eliminación de las bases temporales.
Las integraciones nuevas comprueban filtros literales, idempotencia de
predicciones, indexación/retiro y rollback de ficha y vectores. Los vectores de
esas pruebas son deterministas: no acreditan calidad semántica del modelo.
También pasaron 132 pruebas del frontend, TypeScript, ESLint y compilación de
producción; 27 pruebas ML de inferencia, repositorio y CLI. Las pruebas de
componentes usan servicios simulados. No se ejecutó un despliegue ni una
construcción de imagen Linux con los extras de ML.
