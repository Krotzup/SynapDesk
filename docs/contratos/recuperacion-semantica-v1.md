# Recuperación semántica V1 — implementación optativa

## Alcance y dependencias

FastAPI conserva la autoridad de sesión, permisos y CSRF. La búsqueda utiliza
los servicios internos existentes y una base semántica propia, separada de las
migraciones del backend. No implementa login, logout ni bootstrap HTTP de CSRF.
Esas rutas y la validación operativa del despliegue de autenticación continúan
como dependencias; no se introduce autenticación ficticia para evitarlas.

El servicio está deshabilitado por defecto. Requiere conexión semántica, perfil
V2 calibrado y un perfil de cookies explícito compartido con Next.js. Para
compatibilidad con el proxy de #30, `AUTH_COOKIE_PROFILE=local` selecciona
`synapdesk_session_dev` y `AUTH_COOKIE_PROFILE=production` selecciona
`__Host-synapdesk_session`. El despliegue y el flujo HTTP siguen sujetos a
AUTH-07. En ensayos se admite el nombre explícito anterior. Si el nombre y el
perfil se configuran juntos y discrepan, se rechaza la búsqueda.

## Solicitud

`POST /api/v1/search`, JSON con `query` de 1–1000 caracteres no vacíos y `limit`
entero de 1–20 (5 por defecto). El modelo también impone 128 tokens incluidos
los especiales. Se conserva el límite de caracteres y se comunica el exceso
real de tokens; no se trunca ni divide silenciosamente la consulta.

La petición requiere una única cookie de sesión del nombre configurado, Origin
público explícitamente permitido y un único `X-CSRF-Token` válido ligado a esa
sesión. Las cookies duplicadas no conceden identidad. Se reutilizan las
verificaciones de usuario activo, rol admitido, revocación y vencimientos de los
servicios existentes. La consulta no renueva actividad de sesión; su política
general sigue pendiente. La transacción de autorización termina antes de emitir
la respuesta y no produce cookies nuevas.

## Respuesta

```json
{
  "status": "results",
  "items": [{
    "documentId": "11111111-1111-4111-8111-111111111111",
    "documentChunkId": "22222222-2222-4222-8222-222222222222",
    "title": "Procedimiento",
    "excerpt": "Contenido del documento...",
    "score": 0.7,
    "sourceUrl": "https://learn.microsoft.com/es-es/",
    "language": "es"
  }]
}
```

El ejemplo ilustra la estructura, no una inferencia. Se conservan los cinco
campos de trazabilidad; `sourceUrl` y `language` son opcionales y se omiten si no
hay metadatos válidos. La fuente es un enlace HTTPS sin credenciales, nunca una
ruta interna ni una descarga ejecutada por el backend. El idioma refleja el
original, sin traducciones automáticas.

| status | Significado |
| --- | --- |
| `results` | Hay fragmentos que alcanzan el corte del perfil. No garantiza una respuesta correcta. |
| `no_documents` | No hay fragmentos indexados para el modelo activo. |
| `insufficient_information` | Hay documentos, pero ninguno alcanza el corte para esta consulta. |

Los dos últimos estados devuelven `items: []` con HTTP 200. Un fallo de modelo,
perfil o infraestructura no se presenta como falta de información. Todas las
respuestas son privadas y llevan `Cache-Control: no-store`.

## Errores

Se conserva `ApiErrorBody`: `error.code`, `message`, `details` y `requestId` UUID.
No se serializan entradas Pydantic, secretos, cookies, consultas SQL, mensajes
del driver ni contenido de la consulta original en los errores.

| HTTP | code | Significado |
| --- | --- | --- |
| 401 | `AUTHENTICATION_REQUIRED` | Sesión ausente, ambigua, inválida o vencida. |
| 403 | `ORIGIN_INVALID` | Origen ausente, ambiguo o no permitido. |
| 403 | `CSRF_INVALID` | Contexto o prueba CSRF inválidos, antes de efectuar la búsqueda. |
| 422 | `VALIDATION_ERROR` | JSON, consulta o límite inválidos. |
| 422 | `QUERY_TOKEN_LIMIT_EXCEEDED` | Consulta que supera los 128 tokens reales. |
| 503 | `SEARCH_PROFILE_STALE` | Cambió el corpus; requiere recalibrar. |
| 503 | `SEARCH_NOT_READY` | Esquema semántico no preparado. |
| 503 | `SEARCH_CONFIGURATION_ERROR` | Base no independiente o configuración incompatible. |
| 503 | `SEARCH_UNAVAILABLE` | Servicio deshabilitado o fallo de búsqueda/modelo. |
| 503 | `DEPENDENCY_UNAVAILABLE` | No se pudo verificar la sesión o confirmar su transacción. |
| 503 | `SERVICE_UNAVAILABLE` | El proxy no pudo comunicarse con el backend o recibió una respuesta incompatible. |

Solo 403 + `CSRF_INVALID` admite el reintento ya aprobado por autenticación V1,
tras renovar su prueba y confirmar que la sesión no cambió. No se agregan
reintentos para otros errores.

## Perfiles V2 y costo de consulta

El perfil guarda identidad UUID y revisión del corpus por modelo, además de su
huella de auditoría. Los triggers de INSERT, UPDATE, DELETE y TRUNCATE invalidan
la revisión dentro de la transacción de escritura, también desde SQL externo.
Reindexar invalida el perfil incluso si conserva los UUID de fragmento.

La API verifica una fila de versión en una instantánea de solo lectura; no lee
todos los embeddings para recomputar una huella por búsqueda. La huella completa
se calcula al calibrar. La identidad evita reutilizar el mismo número de revisión
en otra base. El CLI conserva perfiles V1 para consultas experimentales, con su
verificación anterior; la API y la evaluación nueva requieren V2.

`expectedDocumentId` opcional permite medir aciertos, Recall@5 por fragmentos y
MRR@5 separados de la decisión de abstención. `evaluate-relevance` usa consultas
nuevas y un perfil existente sin modificar su umbral; rechaza identificadores o
consultas normalizadas reutilizados desde la calibración. Etiquetas sintéticas
no se convierten en validación humana ni certificación de producción.
