# Integración de pendientes del MVP

19 de noviembre de 2026. **Implementación preparada para revisión del equipo.**
Las decisiones de este incremento son una propuesta ejecutable solicitada para
completar los pendientes; no se presentan como aprobación histórica del PO o
como despliegue productivo. Este documento actualiza los pendientes específicos
de filtros, estados, clasificación e ingestión de los contratos anteriores.

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

Pasaron 1.063 pruebas unitarias del backend y 474 de integración con PostgreSQL,
con Alembic `upgrade/current/heads/check` y eliminación de las bases temporales.
Las integraciones nuevas comprueban filtros literales, idempotencia de
predicciones, indexación/retiro y rollback de ficha y vectores. Los vectores de
esas pruebas son deterministas: no acreditan calidad semántica del modelo.
También pasaron 132 pruebas del frontend, TypeScript, ESLint y compilación de
producción; 27 pruebas ML de inferencia, repositorio y CLI. Las pruebas de
componentes usan servicios simulados. No se ejecutó un despliegue ni una
construcción de imagen Linux con los extras de ML.
