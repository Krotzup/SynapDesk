# Contrato de recomendaciones RAG V1

Estado: **implementado y verificado de extremo a extremo en el ensayo local de testing; integración de despliegue pendiente**. Complementa [frontend–backend](frontend-backend.md), [recuperación semántica V1](recuperacion-semantica-v1.md) y el [modelo de dominio](../arquitectura/modelo-dominio.md). La generación es optativa y permanece cerrada por defecto.

## Responsabilidades

- FastAPI autentica la sesión y el canal Next.js→FastAPI, valida Origin y CSRF en escrituras, lee el ticket persistido y conserva el borrador y las decisiones humanas.
- La recuperación V2 consulta la base semántica separada con su perfil ligado al corpus. Su `score` es similitud, nunca confianza del LLM.
- El orquestador envía a Gemini 3.5 Flash-Lite el ticket y hasta cinco fragmentos recuperados, con correo y asignaciones evidentes de credenciales redactados. Solo acepta JSON estructurado con pasos y referencias a identificadores recuperados.
- La revisión humana es obligatoria para pasar de `pending` a `accepted`, `modified` o `rejected`. Aceptar no resuelve el ticket. El texto original y las fuentes no se sobrescriben.

## API pública

| Método | Ruta | Respuesta |
| --- | --- | --- |
| `POST` | `/api/v1/tickets/{ticketId}/recommendations` | `201` recomendación `pending` |
| `GET` | `/api/v1/tickets/{ticketId}/recommendations` | `200` lista descendente por creación |
| `GET` | `/api/v1/recommendations/{recommendationId}` | `200` recomendación |
| `POST` | `/api/v1/recommendations/{recommendationId}/reviews` | `204` sin cuerpo |

Los identificadores son UUID en texto. Las fechas son ISO 8601 con zona horaria. El JSON usa camelCase. Los nombres técnicos de estado y decisión usan inglés. Se exige sesión de `agent` o `admin`; el revisor se deriva de ella. El proxy de servidor debe presentar credencial de servicio sobre TLS directo. POST exige Origin válido y token CSRF. GET de SSR puede omitir Origin, pero uno presente se valida.

La recomendación contiene `id`, `ticketId`, `content`, `status`, `sources`, `createdAt` y `review` (objeto o `null`). Cada fuente contiene `documentId`, `documentChunkId`, `title`, `excerpt`, `score` y opcionalmente `sourceUrl`. La revisión contiene `decision`, `modifiedContent`, `feedback` y `reviewedAt`. La fuente queda registrada como instantánea de la evidencia usada. El contenido modificado pertenece a `review`, nunca reemplaza `content`.

La solicitud de revisión admite `decision` (`accepted`, `modified`, `rejected`), `modifiedContent` solo para `modified` (no vacío, máximo 10 000 caracteres) y `feedback` opcional (máximo 2 000). Solo se permite una revisión por borrador. Solo se permite un borrador `pending` por ticket; la generación siguiente exige revisarlo antes. Un fallo o abstención no crea recomendación.

## Errores y abstención

Las respuestas de error siguen el envoltorio común `{ "error": { "code", "message", "details", "requestId" } }` y `Cache-Control: no-store`. No incluyen el ticket, fragmentos, clave de API ni respuesta del proveedor.

| Código | HTTP | Significado |
| --- | --- | --- |
| `AUTHENTICATION_REQUIRED`, `FORBIDDEN`, `ORIGIN_INVALID`, `CSRF_INVALID` | `401`/`403` | Solicitud no autorizada |
| `TICKET_NOT_FOUND`, `RECOMMENDATION_NOT_FOUND` | `404` | Recurso inexistente |
| `RECOMMENDATION_PENDING`, `RECOMMENDATION_ALREADY_REVIEWED` | `409` | Conflicto de estado |
| `INSUFFICIENT_INFORMATION` | `422` | Sin resultados útiles o el modelo devolvió `steps: []` |
| `GENERATION_INVALID`, `GENERATION_UNAVAILABLE`, `RECOMMENDATIONS_UNAVAILABLE` | `503` | Salida inválida o dependencia no preparada |

Los errores de recuperación conservan los códigos de su contrato. No se publica una respuesta inventada si la búsqueda no devuelve evidencia, el proveedor falla o una cita no pertenece al contexto. Las citas verificadas **no prueban** por sí solas que el paso esté correctamente sustentado; el especialista debe revisar el contenido.

## Activación y datos

Requiere `SEARCH_ENABLED=true`, perfil V2 vigente, base semántica independiente, backend migrado, sesión/CSRF operativos, `RAG_ENABLED=true`, `GEMINI_API_KEY`, `RAG_PUBLIC_ORIGIN` y `RAG_EXTERNAL_DATA_APPROVED=true`. Este último flag exige una decisión operativa explícita sobre el envío de tickets a Google. Según los [términos oficiales de Gemini](https://ai.google.dev/gemini-api/terms), los servicios gratuitos pueden usar entradas para mejorar productos; antes de tickets reales se necesita un proyecto con tratamiento de datos aprobado y las políticas de la organización. El redactor de patrones evidentes no garantiza anonimización. El identificador del modelo se corresponde con la [documentación oficial de Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

La recuperación se evalúa con consultas representativas y documentos cuya procedencia/derechos sean conocidos. Cualquier cambio de corpus exige recalibrar el perfil V2. El piloto sintético y sus métricas no certifican calidad en producción.

El orquestador registra únicamente resultado, etapa, cantidad de fuentes y duración en milisegundos. La llamada al proveedor registra estado HTTP si falla y, si Gemini los entrega, contadores de tokens de entrada, salida, razonamiento y total; nunca el ticket, fragmentos, salida, credenciales ni identificadores de usuario. El operador debe medir latencia, errores, cobertura, calidad de citas y consumo del proveedor antes de fijar capacidad o cuotas de producción.
