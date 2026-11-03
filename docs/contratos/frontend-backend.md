# Contrato inicial entre frontend y backend

## Estado

**Provisional**

## Propósito

Este documento define el contrato inicial previsto entre el frontend Next.js y el backend FastAPI de SynapDesk.

Su objetivo es evitar diferencias en los nombres de rutas, campos, estados, errores y estructuras de respuesta.

Las rutas descritas todavía no representan funcionalidades implementadas. El contrato deberá revisarse antes de desarrollar cada módulo y actualizarse junto con cualquier cambio que afecte a ambos componentes.

## Convenciones generales

* La API utilizará el prefijo `/api/v1`.
* Los datos se intercambiarán en formato JSON, salvo la carga o descarga de archivos.
* Los nombres de campos enviados a la aplicación utilizarán `camelCase`.
* Los identificadores utilizarán UUID representados como texto.
* Las fechas utilizarán ISO 8601 en UTC.
* Los estados y roles utilizarán valores técnicos en inglés.
* Los mensajes visibles para el usuario podrán entregarse en español.
* Los códigos HTTP deberán representar correctamente el resultado de cada operación.
* Los secretos y campos internos nunca deberán incluirse en las respuestas.

Ejemplo de fecha:

```text
2026-09-11T18:30:00Z
```

## URL base

El navegador no llama directamente a FastAPI: consume rutas relativas `/api/v1/*` bajo el origen del frontend y el proxy de mismo origen de Next.js (Route Handler `frontend/src/app/api/v1/[...path]/route.ts`) las reenvía al backend, conservando el prefijo `/api/v1`. Las páginas del servidor (SSR) leen datos directamente del mismo destino. El [contrato de transporte de autenticación](autenticacion-v1.md#3-arquitectura-y-despliegue) define proxy de mismo origen, adaptador SSR seguro por petición, cookies necesarias, respuestas privadas sin caché compartida y secretos exclusivamente en servidor.

Configuración local (`frontend/.env.local`, variables solo de servidor):

```env
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
AUTH_COOKIE_PROFILE=local
```

Ejemplo local: navegador en `http://localhost:3000`, solicitud pública `http://localhost:3000/api/v1/...` y destino FastAPI `http://127.0.0.1:8000/api/v1/...`. FastAPI escucha solo en `127.0.0.1`. La regla de no mezclar `localhost` y `127.0.0.1` se aplica al origen del navegador, que es donde viven las cookies; el destino interno no recibe cookies propias del navegador. El origen permitido por el backend (`AUTH_ORIGENES_PERMITIDOS`) es el del navegador, `http://localhost:3000`, no el destino interno.

El puerto `3000` corresponde al frontend Next.js y no debe utilizarse como destino del proxy. `BACKEND_INTERNAL_URL` no se expone mediante `NEXT_PUBLIC_*` ni se acepta desde parámetros, cabeceras o cuerpos del cliente. `NEXT_PUBLIC_API_URL` ya no se utiliza en el frontend.

Comportamiento del proxy (detalle en `frontend/src/lib/backend-proxy.ts`):

* Hacia FastAPI reenvía solo `Accept`, `Content-Type`, `Origin` (sin modificarlo ni inventarlo), `Sec-Fetch-Site`, `X-CSRF-Token` y las cookies de sesión y de contexto CSRF del perfil elegido con `AUTH_COOKIE_PROFILE` (`local`: `synapdesk_session_dev`, `synapdesk_csrf_context_dev`; `production`: `__Host-synapdesk_session`, `__Host-synapdesk_csrf_context`). Descarta `X-Forwarded-*`, `Forwarded`, `X-Real-IP`, `X-SynapDesk-Client-IP`, `Authorization` y el resto de las cookies. Una cookie permitida repetida se reenvía con todas sus apariciones para que el backend rechace la ambigüedad.
* Hacia el navegador conserva estado y cuerpo, `Content-Type`, `Retry-After` y cada `Set-Cookie` como cabecera separada, y agrega `Cache-Control: no-store` a todas las respuestas, incluidos los errores.
* No sigue redirecciones. Si el backend no responde, tarda más de 30 segundos, responde con una redirección o falta `BACKEND_INTERNAL_URL`, responde 503 `SERVICE_UNAVAILABLE` con el formato de error del contrato.
* Todavía no envía la IP del cliente: la cabecera interna `X-SynapDesk-Client-IP` queda condicionada a la frontera de confianza que se implementará en AUTH-07.

Los nombres de cookies, el tiempo de espera y el perfil por variable son propuestos y siguen sujetos a revisión con el backend.

## Autenticación

El Product Owner aprobó sesiones opacas persistidas en PostgreSQL, administradas por FastAPI y transportadas mediante cookie HttpOnly, con acceso público a través de un proxy del mismo origen. La especificación, sus propuestas y decisiones pendientes se concentran en el [contrato de autenticación V1](autenticacion-v1.md). La autenticación todavía no está implementada.

Rutas iniciales previstas:

| Método | Ruta                  | Propósito                      |
| ------ | --------------------- | ------------------------------ |
| `GET`  | `/api/v1/auth/csrf`   | Obtener contexto/token CSRF     |
| `POST` | `/api/v1/auth/login`  | Iniciar sesión                 |
| `POST` | `/api/v1/auth/logout` | Cerrar sesión                  |
| `GET`  | `/api/v1/auth/me`     | Obtener el usuario autenticado |

El frontend no deberá almacenar contraseñas ni recibir hashes de contraseñas. Login y `/me` utilizarán el DTO documental específico `AuthUser`, sin modificar el tipo público `User`. Se aprueban los campos obligatorios `id` (UUID como texto), `email` (correo electrónico normalizado) y `role` (`admin` o `agent`), contenidos en la envoltura `user`. No se incorporan otros campos obligatorios ni contraseñas, hashes o tokens. Los errores de autenticación conservarán `error.code`, `error.message`, `error.details` y `error.requestId`; el contrato especializado también contempla `429` y `503` cuando correspondan.

El [contrato de seguridad](autenticacion-v1.md#6-cookies-y-csrf) formaliza como `APPROVED` Synchronizer Token, contextos del servidor anónimo y autenticado vinculado a sesión, X-CSRF-Token, origen estricto y rotación/invalidez de contextos. Solo el token CSRF se entregaría por el campo previsto para esa prueba; las credenciales de sesión/contexto no se exponen en JSON ni se añaden a AuthUser. Los valores CSRF, Argon2id y límites mantienen `PROVISIONAL_CONFIGURATION` / `PENDING_MEASUREMENT`; la retención de auditoría necesita aprobación. Los campos de respuesta CSRF, nombres concretos de cookies y códigos no aprobados expresamente siguen como propuestas. La matriz detallada de permisos tiene estado `PROPOSAL_PENDING_TEAM_REVIEW`, con denegación por defecto de operaciones sin autorización definida. Las etiquetas y sus dimensiones se definen en el contrato especializado; aprobación no significa implementación ni medición completada.

Para V1, las mutaciones autenticadas de negocio se realizan con fetch desde componentes o servicios cliente a `/api/v1/*`, incluido login/logout con sus respectivos requisitos, creación/modificación de tickets y acciones mutables del asistente. No se usan Server Actions o Server Functions para esas mutaciones. Las lecturas SSR conservan el adaptador por petición y la ausencia de caché compartida. El proxy transporta cookies/cabeceras permitidas y múltiples Set-Cookie separados; no fabrica Origin ni confía en cabeceras de proxy arbitrarias.

Se permite renovar CSRF preventivamente cerca de expiresAt, solo en memoria del contexto cliente y coordinando solicitudes; no se extiende por ello la inactividad ni se expulsan tokens vigentes en uso. Solo tras un 403 explícito con error.code CSRF_INVALID garantizado antes de efectos de negocio puede obtenerse otro token y reintentarse una vez, confirmando que sigue el contexto esperado. Si cambió sesión/contexto, la continuidad no se puede confirmar o vuelve a fallar, se devuelve el error. No se reintentan automáticamente otros 403, timeouts, fallos de red, 500/503 ni resultados desconocidos. Los valores de duración y capacidad siguen provisionales.

Origin es obligatorio en mutaciones públicas: debe coincidir exactamente con un origen permitido configurado. Origin ausente, null, ambiguo/múltiple o externo no permitido produce HTTP 403 ORIGIN_INVALID con ApiErrorBody antes de efectos, incluso en logout sin sesión. No hay excepciones implícitas para Server Actions, scripts o clientes externos; las reglas de solo lectura/SSR no son un bypass para mutaciones.

Logout es idempotente respecto al cierre y conserva validación de origen: devuelve 204 cuando no existe sesión válida que revocar. Si la sesión es válida, exige CSRF válido antes de confirmar su revocación; CSRF inválido devuelve 403 sin revocar ni borrar la cookie. Si PostgreSQL impide verificar una cookie presentada o confirmar una revocación requerida, devuelve 503, no un 204 ficticio. Sin cookie no hay credencial que consultar o revocar. La [precedencia de logout](autenticacion-v1.md#post-apiv1authlogout) precisa los casos; la idempotencia no evita los controles. La estructura de AuthUser y ApiErrorBody permanece intacta. No se autoriza implementación; servicios, proxy y protección de rutas se adaptarán en otra tarea.

## Usuarios

| Método   | Ruta                 | Propósito                   |
| -------- | -------------------- | --------------------------- |
| `GET`    | `/api/v1/users`      | Listar usuarios             |
| `GET`    | `/api/v1/users/{id}` | Obtener un usuario          |
| `POST`   | `/api/v1/users`      | Crear un usuario            |
| `PATCH`  | `/api/v1/users/{id}` | Actualizar datos permitidos |
| `DELETE` | `/api/v1/users/{id}` | Desactivar un usuario       |

La operación `DELETE` representará inicialmente una desactivación lógica y no una eliminación irreversible.

Respuesta resumida de usuario:

```json
{
  "id": "af3a1e41-c838-46fb-bcdc-c85c260e556b",
  "name": "Agente de soporte",
  "email": "agente@synapdesk.local",
  "role": "agent",
  "isActive": true,
  "createdAt": "2026-09-11T18:30:00Z",
  "updatedAt": "2026-09-11T18:30:00Z"
}
```

## Tickets

| Método   | Ruta                   | Propósito                               |
| -------- | ---------------------- | --------------------------------------- |
| `GET`    | `/api/v1/tickets`      | Listar tickets                          |
| `GET`    | `/api/v1/tickets/{id}` | Obtener el detalle de un ticket         |
| `POST`   | `/api/v1/tickets`      | Crear un ticket                         |
| `PATCH`  | `/api/v1/tickets/{id}` | Actualizar campos permitidos            |
| `DELETE` | `/api/v1/tickets/{id}` | Cerrar o eliminar lógicamente un ticket |

Solicitud inicial para crear un ticket:

```json
{
  "title": "Equipo sin acceso a la red",
  "description": "El usuario informa que no puede conectarse a la red corporativa."
}
```

Respuesta resumida:

```json
{
  "id": "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f",
  "title": "Equipo sin acceso a la red",
  "description": "El usuario informa que no puede conectarse a la red corporativa.",
  "status": "open",
  "priority": "medium",
  "category": null,
  "area": null,
  "createdBy": {
    "id": "af3a1e41-c838-46fb-bcdc-c85c260e556b",
    "name": "Agente de soporte",
    "email": "agente@synapdesk.local",
    "role": "agent"
  },
  "assignedTo": null,
  "createdAt": "2026-09-11T18:30:00Z",
  "updatedAt": "2026-09-11T18:30:00Z"
}
```

Los valores predichos mediante Machine Learning deberán identificarse claramente y no confundirse con decisiones validadas.

## Documentos

| Método   | Ruta                     | Propósito                           |
| -------- | ------------------------ | ----------------------------------- |
| `GET`    | `/api/v1/documents`      | Listar documentos                   |
| `GET`    | `/api/v1/documents/{id}` | Obtener información de un documento |
| `POST`   | `/api/v1/documents`      | Incorporar un documento             |
| `DELETE` | `/api/v1/documents/{id}` | Retirar un documento                |

La carga utilizará `multipart/form-data`. Los formatos, tamaños máximos y validaciones se definirán antes de implementar esta ruta.

El backend nunca deberá confiar únicamente en la extensión del archivo enviada por el navegador.

## Recuperación semántica

| Método | Ruta             | Propósito                       |
| ------ | ---------------- | ------------------------------- |
| `POST` | `/api/v1/search` | Realizar una búsqueda semántica |

Solicitud inicial:

```json
{
  "query": "Cómo recuperar la conexión a la red corporativa",
  "limit": 5
}
```

Respuesta inicial:

```json
{
  "items": [
    {
      "documentId": "5e923ab0-5cee-4c50-b0dc-35fa54ca54aa",
      "documentChunkId": "77223789-bd19-4642-a550-b4f52210320c",
      "title": "Procedimiento de conectividad",
      "excerpt": "Verifique la configuración del adaptador de red...",
      "score": 0.89
    }
  ]
}
```

El significado y rango del campo `score` deberán documentarse cuando se seleccione la estrategia de recuperación.

## Recomendaciones

| Método | Ruta                                   | Propósito                         |
| ------ | -------------------------------------- | --------------------------------- |
| `POST` | `/api/v1/tickets/{id}/recommendations` | Generar una recomendación         |
| `GET`  | `/api/v1/tickets/{id}/recommendations` | Listar recomendaciones del ticket |
| `GET`  | `/api/v1/recommendations/{id}`         | Consultar una recomendación       |
| `POST` | `/api/v1/recommendations/{id}/reviews` | Registrar la revisión humana      |

Respuesta inicial de recomendación:

```json
{
  "id": "459235aa-e33a-4e19-9055-b085319ff895",
  "ticketId": "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f",
  "content": "Verifique primero el estado del adaptador de red y la configuración asignada.",
  "status": "pending",
  "sources": [
    {
      "documentId": "5e923ab0-5cee-4c50-b0dc-35fa54ca54aa",
      "documentChunkId": "77223789-bd19-4642-a550-b4f52210320c",
      "title": "Procedimiento de conectividad",
      "excerpt": "Verifique la configuración del adaptador de red...",
      "score": 0.89
    }
  ],
  "createdAt": "2026-09-11T18:35:00Z"
}
```

Solicitud para registrar una revisión:

```json
{
  "decision": "modified",
  "modifiedContent": "Verifique el adaptador de red y posteriormente renueve la configuración de red.",
  "feedback": "La recomendación original necesitaba un paso adicional."
}
```

Las decisiones permitidas son:

* `accepted`;
* `modified`;
* `rejected`.

El backend determinará el usuario revisor mediante la sesión autenticada. El frontend no deberá enviar libremente un `reviewerId`.

## Métricas

| Método | Ruta                      | Propósito                  |
| ------ | ------------------------- | -------------------------- |
| `GET`  | `/api/v1/metrics/summary` | Obtener un resumen general |

Las métricas específicas deberán aprobarse antes de considerar estable esta respuesta.

Datos inicialmente previstos:

* total de tickets;
* tickets resueltos;
* tiempo promedio de resolución;
* recomendaciones aceptadas;
* recomendaciones modificadas;
* recomendaciones rechazadas.

## Paginación

Las operaciones de listado deberán admitir, cuando corresponda:

| Parámetro  | Descripción                       |
| ---------- | --------------------------------- |
| `page`     | Número de página, comenzando en 1 |
| `pageSize` | Cantidad de resultados            |
| `search`   | Búsqueda textual opcional         |
| `sort`     | Criterio de orden                 |
| `order`    | Orden ascendente o descendente    |

Respuesta paginada prevista:

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "totalItems": 0,
  "totalPages": 0
}
```

## Errores

Formato inicial de error:

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "No se encontró el ticket solicitado.",
    "details": null,
    "requestId": "4762428a-c356-44d7-8f43-e48fc16e393a"
  }
}
```

Códigos HTTP principales:

| Código | Uso                                |
| -----: | ---------------------------------- |
|  `200` | Operación completada               |
|  `201` | Recurso creado                     |
|  `204` | Operación completada sin contenido |
|  `400` | Solicitud inválida                 |
|  `401` | Usuario no autenticado             |
|  `403` | Usuario sin autorización           |
|  `404` | Recurso no encontrado              |
|  `409` | Conflicto con el estado actual     |
|  `422` | Error de validación                |
|  `500` | Error interno no controlado        |

Los errores internos no deberán revelar contraseñas, consultas SQL, rutas del servidor, variables de entorno ni trazas completas.

### Servicio temporalmente no disponible

HTTP 503 significa indisponibilidad temporal. Se aprueba SERVICE_UNAVAILABLE como código general de operaciones de aplicación cuando la causa específica no sea parte del contrato público. GET `/api/v1/ready` conserva DATABASE_UNAVAILABLE cuando falla su comprobación PostgreSQL, con la misma estructura error.code, error.message, error.details y error.requestId. Ese comportamiento existente no se modifica. El frontend maneja 503 por estado HTTP sin asumir un único error.code y sin revelar detalles de infraestructura ni reintentar mutaciones automáticamente. Un fallo PostgreSQL que impide comprobar o confirmar una revocación requerida debe devolver 503, nunca un 204 ficticio.

## Relación con la estructura actual del frontend

Los tipos y servicios agregados inicialmente al frontend se consideran provisionales.

Antes de implementar cada módulo deberán revisarse:

* el prefijo `/api/v1`;
* las rutas de recomendaciones;
* la estructura de paginación;
* los campos de predicción;
* los estados de procesamiento documental;
* el formato uniforme de errores;
* el mecanismo de autenticación;
* la diferencia entre eliminar, desactivar y cerrar recursos.

Cuando se apruebe este contrato, los servicios de `frontend/src/services/` deberán adaptarse mediante un pull request independiente.

## Decisiones pendientes

* detalles pendientes del [contrato de autenticación V1](autenticacion-v1.md), sobre la arquitectura de sesiones ya aprobada;
* política de CORS;
* límites de paginación;
* límite de tamaño y formatos de documentos;
* códigos definitivos de errores;
* filtros disponibles para tickets;
* forma de representar categorías y áreas;
* estrategia para operaciones de IA que requieran procesamiento prolongado;
* política de reintentos y tiempos máximos;
* métricas definitivas del MVP.

## Criterios de aceptación

Este contrato se considerará aceptado cuando:

* frontend y backend acuerden las rutas y estructuras principales;
* Machine Learning confirme los campos necesarios para predicciones;
* los estados compartidos estén documentados;
* las decisiones pendientes se encuentren registradas;
* los ejemplos no contengan secretos ni datos personales reales;
* los tres integrantes aprueben el documento mediante el pull request correspondiente.
