# Contrato inicial entre frontend y backend

## Estado

**Provisional por módulo; autenticación formalizada en el alcance aprobado AUTH-07D.3.** El resto del contrato conserva sus estados y acuerdos propios.

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
BACKEND_INTERNAL_URL=https://127.0.0.1:8000
BACKEND_SERVICE_CREDENTIAL=<32 bytes en base64url, 43 caracteres; sin valor en el repositorio>
AUTH_COOKIE_PROFILE=local
```

Ejemplo local: navegador en `http://localhost:3000`, solicitud pública `http://localhost:3000/api/v1/...` y destino FastAPI `https://127.0.0.1:8000/api/v1/...` (SEC-01B exige TLS directo también en local; ver [comunicación interna segura](comunicacion-interna-segura-v1.md)). FastAPI escucha solo en `127.0.0.1`. La regla de no mezclar `localhost` y `127.0.0.1` se aplica al origen del navegador, que es donde viven las cookies; el destino interno no recibe cookies propias del navegador. El origen permitido por el backend (`AUTH_ORIGENES_PERMITIDOS`) es el del navegador, `http://localhost:3000`, no el destino interno. El ingreso del navegador a Next.js y el salto de servicio Next.js→FastAPI son perfiles distintos: entrar a Next.js por `http://localhost:3000` en local no acredita TLS público ni la IP del navegador, y un destino FastAPI por HTTP no admite la credencial de servicio en claro (el proxy lo rechaza por configuración).

El puerto `3000` corresponde al frontend Next.js y no debe utilizarse como destino del proxy. `BACKEND_INTERNAL_URL` no se expone mediante `NEXT_PUBLIC_*` ni se acepta desde parámetros, cabeceras o cuerpos del cliente. `NEXT_PUBLIC_API_URL` ya no se utiliza en el frontend.

Comportamiento del proxy (detalle en `frontend/src/lib/backend-proxy.ts`):

* El proxy y el adaptador SSR usan el mismo canal (`frontend/src/lib/backend-proxy.ts`). Cada petición lleva exactamente una cabecera `Authorization: Bearer <credencial de servicio>` generada en el servidor desde `BACKEND_SERVICE_CREDENTIAL` (SEC-01B; nombre provisional, decisión C07). La `Authorization` del navegador se descarta. La credencial no aparece en `NEXT_PUBLIC_*`, respuestas, errores ni registros.
* La conexión con FastAPI es HTTPS con la verificación de CA y nombre del certificado de Node; nunca se desactiva. `BACKEND_INTERNAL_URL` debe ser exactamente un origen `https://`, sin usuario, ruta, query ni `#`. Una CA local de prueba se agrega solo al proceso de Next con `NODE_EXTRA_CA_CERTS`.
* Hacia FastAPI reenvía solo `Accept`, `Content-Type`, `Origin` (sin modificarlo ni inventarlo), `Sec-Fetch-Site`, `X-CSRF-Token` y las cookies con nombre reservado de **los dos** perfiles (`synapdesk_session_dev`, `synapdesk_csrf_context_dev`, `__Host-synapdesk_session`, `__Host-synapdesk_csrf_context`), con todas sus apariciones y sin modificarlas: una cookie reservada sin `=`, repetida, vacía o de otro perfil llega al backend para que la rechace (política P1); el proxy no elige un valor ni la oculta. Descarta `X-Forwarded-*`, `Forwarded`, `X-Real-IP`, `X-SynapDesk-Client-IP`, `X-Request-ID` y el resto de las cookies.
* Hacia el navegador conserva estado y cuerpo, `Content-Type`, `Retry-After` y cada `Set-Cookie` **del perfil activo** como cabecera separada, sin modificar sus atributos (también los de borrado). Descarta los `Set-Cookie` de otros nombres o del otro perfil y registra solo cuántos descartó, sin nombres ni valores. Agrega `Cache-Control: no-store` a todas las respuestas, incluidos los errores.
* `AUTH_COOKIE_PROFILE` es obligatoria y acepta solo `local` o `production`. Ausente, vacía u otro valor es un error de configuración: el proxy y el adaptador SSR responden 503 sin contactar al backend y no eligen un perfil en silencio. Lo mismo ocurre si falta `BACKEND_SERVICE_CREDENTIAL` o no tiene el formato de SEC-01B (32 bytes en base64url, 43 caracteres).
* El plazo de 30 segundos es único por operación: cubre la lectura del cuerpo que envía el navegador, la conexión y TLS, la espera y la lectura completa de la respuesta. Límites provisionales de tamaño (decisiones C05/C06): 1 MiB para el cuerpo de la petición (si lo supera, 413 `VALIDATION_ERROR` sin contactar al backend) y 5 MiB para la respuesta (si la supera, 503).
* No sigue redirecciones. Si el backend no responde, falla la verificación TLS, tarda más de 30 segundos en entregar la respuesta completa (cabeceras y cuerpo), corta la conexión a mitad del cuerpo, responde con una redirección o la configuración no es válida, responde 503 `SERVICE_UNAVAILABLE` con el formato de error del contrato y un `requestId` nuevo, generado en el servidor. El adaptador SSR aplica las mismas reglas: tiempo de espera, rechazo de redirecciones y errores con `requestId`.
* No envía ninguna cabecera con la IP del cliente: no existe una cabecera IP interna aprobada y las que envíe el navegador se descartan. La credencial de servicio no acredita la IP; su procedencia sigue pendiente de evidencia en el despliegue (SEC-01B, sección 6; decisión C08).

Los nombres de cookies (C02), el nombre de la variable de la credencial (C07), el tiempo de espera y los límites de tamaño (C05/C06) son propuestos y siguen sujetos a revisión con el backend.

## Autenticación

El Product Owner aprobó sesiones opacas persistidas en PostgreSQL, administradas por FastAPI y transportadas mediante cookie HttpOnly, con acceso público a través de un proxy del mismo origen. La especificación, sus propuestas y decisiones pendientes se concentran en el [contrato de autenticación V1](autenticacion-v1.md). Los servicios internos y adaptadores están implementados; GET csrf está registrado con cierre seguro, sin emisión, y login/me/logout HTTP siguen sin registrar (404). No hay administración HTTP. La [especificación HTTP V1](autenticacion-http-adaptadores-v1.md) separa aprobación, implementación y evidencia.

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

**AUTH-07D.3, APPROVED P1–P10:** cookies malformadas/duplicadas/perfiles mezclados se rechazan antes de filtrarlos, sin convertirlas en anónimas. No recuperación automática de sesión vencida/revocada/inválida. /me no renueva treinta minutos de inactividad ni ocho horas absolutas. Logout puede únicamente revocar una sesión verificable de cuenta inactiva con controles restantes, sin acceso/identidad activa/contexto privilegiado nuevo; este último caso aún requiere un ajuste interno de backend.

Arquitectura B aprobada: navegador → Next.js público → FastAPI privado → PostgreSQL, Render pendiente de evidencia. SEC-01B usa credencial opaca por entorno solo servidor, TLS con CA/hostname y rotación controlada; servicio, usuario, IP, Origin y CSRF son controles independientes. No existe cabecera IP interna aprobada. Falta de control obligatorio mantiene cierre, sin bypass local. Cuotas productivas necesarias deben aprobarse/configurarse: ensayo no equivale a producción.

Se conserva renovación preventiva coordinada CSRF, solo en memoria y sin ampliar actividad/expulsar tokens vigentes. **P8 sustituye el reenvío automático de escrituras anteriormente permitido tras CSRF_INVALID:** renovar prueba no repite la mutación. Tampoco retry automático ante 429, timeout/red/TLS, 500/503 o resultado incierto. Presupuestos numéricos por operación/tramo pendientes de medición/decisión, sin cambios de consumo de cuotas.

Los [atributos de cookies](autenticacion-http-adaptadores-v1.md#cookies-y-tratamiento-de-credenciales-obsoletas) quedan formalizados: HttpOnly, Secure producción, SameSite=Lax, Path=/ y sin Domain __Host-. Nombres/mapeo concreto, 200/DTO CSRF/cuerpo logout y códigos adicionales siguen como propuestas C01–C04, según [matriz D.3](auth07d3-compatibilidad-y-plan-integracion.md). AuthUser no incorpora name.

Origin es obligatorio en mutaciones públicas: debe coincidir exactamente con un origen permitido configurado. Origin ausente, null, ambiguo/múltiple o externo no permitido produce HTTP 403 ORIGIN_INVALID con ApiErrorBody antes de efectos, incluso en logout sin sesión. No hay excepciones implícitas para Server Actions, scripts o clientes externos; las reglas de solo lectura/SSR no son un bypass para mutaciones.

Logout es idempotente respecto al cierre y conserva validación de origen: devuelve 204 cuando no existe sesión válida que revocar. Si la sesión es válida, exige CSRF válido antes de confirmar su revocación; CSRF inválido devuelve 403 sin revocar ni borrar la cookie. Si PostgreSQL impide verificar una cookie presentada o confirmar una revocación requerida, devuelve 503, no un 204 ficticio. Sin cookie no hay credencial que consultar o revocar. La [precedencia de logout](autenticacion-v1.md#post-apiv1authlogout) precisa los casos; la idempotencia no evita los controles. La estructura de AuthUser y ApiErrorBody permanece intacta. D.3 no autoriza registrar rutas. ServicioLogout actual rechaza cuenta inactiva: debe implementar la excepción estrecha P4 en otra tarea y conservar rechazo de /me/administración. Las [especificaciones PR30/PR32](integracion-http-pr30-pr32-v1.md) indican responsabilidades y aceptación sin modificar sus ramas.

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
| `PATCH`  | `/api/v1/tickets/{id}` | Cambiar el estado del ticket            |

El borrado de tickets no forma parte del MVP (MVP02, 16-11-2026); el cierre se hace cambiando el estado a `closed`.

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
  "updatedAt": "2026-09-11T18:30:00Z",
  "resolvedAt": null
}
```

Los valores predichos mediante Machine Learning deberán identificarse claramente y no confundirse con decisiones validadas.

### Creación de tickets (`POST /api/v1/tickets`)

Reglas acordadas entre frontend y backend el 03-11-2026. El frontend ya las aplica con datos de ejemplo (PR #27); el endpoint todavía no está implementado en el backend.

**Solicitud.** El cliente envía únicamente `title` y `description`. El servidor asigna los demás campos: `id`, `status`, `priority`, `createdBy`, fechas y, más adelante, la clasificación. Cualquier otro campo en la solicitud responde `422` (propuesta en [Campos no previstos](#campos-no-previstos)).

**Normalización.** Se eliminan los espacios en blanco al inicio y al final de `title` y `description` **antes de validar**, y se guarda el valor recortado. El frontend envía los valores ya recortados, pero el backend debe recortarlos igualmente y no confiar en el cliente.

**Validación.** Las longitudes se cuentan sobre el valor recortado:

| Campo         | Tipo  | Obligatorio | Mínimo | Máximo |
| ------------- | ----- | ----------- | -----: | -----: |
| `title`       | texto | Sí          |      5 |    150 |
| `description` | texto | Sí          |     10 |   5000 |

Un valor vacío, o que quede vacío tras recortar, es inválido.

**Valores iniciales.** Un ticket recién creado tiene `status: "open"`, `priority: "medium"`, `category: null`, `area: null`, `assignedTo: null` y `resolvedAt: null`. `createdBy` corresponde al usuario autenticado que crea el ticket.

**Respuesta exitosa.** `201 Created`, con el ticket completo en el mismo formato de `GET /api/v1/tickets/{id}`, como en el ejemplo anterior. El frontend navega al detalle del ticket con el `id` recibido.

**Clasificación.** La creación es independiente de la clasificación ML: primero se guarda el ticket y la clasificación se ejecuta en un flujo separado. Una falla del clasificador no impide crear el ticket ni cambia la respuesta `201`. El endpoint de clasificación sigue pendiente ([contrato backend–ML](backend-ml.md)).

**Autenticación y permisos — APPROVED MVP02 (16-11-2026).** El Product Owner aprueba para `admin` y `agent` las cinco operaciones: crear, listar, consultar detalle, actualizar exclusivamente el estado y consultar conteos de tickets. Listado, detalle, estado y conteos tienen alcance global de tickets para ambos roles; el anónimo no tiene acceso. Se exige sesión persistente vigente, cuenta activa y rol actual consultado en PostgreSQL. Un UUID, rol enviado por el cliente o credencial SEC-01B no acredita usuario. Esta aprobación sustituye la propuesta anterior de alcance restringido del agente; no se encontró una restricción de propiedad/asignación previamente aprobada que la limite. No concede asignaciones, borrado, edición libre ni administración de usuarios.

Como toda mutación de V1, creación y cambio de estado se enviarán con `fetch` desde el cliente, a través del proxy de mismo origen, con `X-CSRF-Token` y `Origin` válido, según el [contrato de autenticación V1](autenticacion-v1.md). Revalidación de sesión, permisos y CSRF comparten la transacción de escritura; un rechazo posterior al trabajo SQL exige rollback y no se representa como un rechazo previo a efectos ni autoriza reintento automático.

**Estado de integración MVP02.** Los [servicios y DTO internos](../../backend/app/tickets/README.md) y los [adaptadores candidatos](../../backend/app/api/adaptadores_tickets.py) están preparados. No hay rutas de tickets registradas. La matriz de permisos ya está aprobada; siguen pendientes la unidad Unicode/recorte/campos extra de creación, filtros y máximo de página públicos, transiciones/resolvedAt/actividad, concurrencia pública y representación final del resumen. `TicketSummary` calcula solo total y los cuatro estados; no sustituye `Metrics` completo ni permite inventar promedios o métricas de IA. Las URLs de esta sección siguen siendo contratos de integración, no evidencia de endpoints operativos.

**Errores.**

| HTTP  | `error.code`                     | Caso                                                     |
| ----: | -------------------------------- | -------------------------------------------------------- |
| `401` | `AUTHENTICATION_REQUIRED`        | Sin sesión válida                                        |
| `403` | `CSRF_INVALID`, `ORIGIN_INVALID` | Token CSRF u `Origin` inválidos (rechazo previo a efectos) |
| `403` | `FORBIDDEN`                      | El rol no puede crear tickets                            |
| `422` | `VALIDATION_ERROR`               | `title` o `description` no cumplen las reglas, o la solicitud trae campos no previstos |
| `503` | `SERVICE_UNAVAILABLE`            | Servicio temporalmente no disponible                     |

Ejemplo de `422`, con el formato descrito en [Errores de validación](#errores-de-validación):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos del ticket no son válidos.",
    "details": [
      { "field": "title", "message": "Debe tener al menos 5 caracteres." },
      { "field": "description", "message": "Ingresa una descripción." }
    ],
    "requestId": "8d1f3c52-7a4e-4b9a-9c2d-5e6f7a8b9c0d"
  }
}
```

### Cambio de estado (`PATCH /api/v1/tickets/{id}`)

**Propuesta pendiente de aprobación.** En MVP02 (16-11-2026) el Product Owner aprobó que `admin` y `agent` actualicen **exclusivamente el estado** de un ticket. Esta sección propone la forma de la operación, tal como la usa el frontend (PR #43) y como la resuelve el núcleo de tickets del backend (PR #39). La ruta todavía no está implementada.

**Solicitud.** El cliente envía solo `status`:

```json
{
  "status": "in_progress"
}
```

Valores admitidos: `open`, `in_progress`, `resolved` y `closed`. Un `status` ausente o fuera de esa lista responde `422` con `details` en el campo `status`. No se pueden editar otros campos (título, descripción, prioridad, categoría, área ni asignación): si la solicitud trae cualquier campo distinto de `status`, responde `422` sin cambiar el ticket (ver [Campos no previstos](#campos-no-previstos)).

**Efectos.** Cambia `status` y `updatedAt`. No modifica ningún otro campo. El cambio a un estado no deduce ni borra `resolvedAt` mientras su regla siga pendiente (ver más abajo).

**Respuesta exitosa.** `200 OK`, con el ticket completo en el mismo formato de `GET /api/v1/tickets/{id}`.

**Autenticación y permisos.** Requiere sesión válida y rol `admin` o `agent`. Como toda mutación de V1, se envía con `fetch` desde el cliente, a través del proxy de mismo origen, con `X-CSRF-Token` y `Origin` válido, según el [contrato de autenticación V1](autenticacion-v1.md).

**Errores.**

| HTTP  | `error.code`                     | Caso                                                       |
| ----: | -------------------------------- | ---------------------------------------------------------- |
| `401` | `AUTHENTICATION_REQUIRED`        | Sin sesión válida                                          |
| `403` | `CSRF_INVALID`, `ORIGIN_INVALID` | Token CSRF u `Origin` inválidos (rechazo previo a efectos) |
| `403` | `FORBIDDEN`                      | El rol no puede cambiar el estado                          |
| `404` | `TICKET_NOT_FOUND`               | El ticket no existe                                        |
| `409` | Por definir                      | El ticket cambió y la operación entra en conflicto         |
| `422` | `VALIDATION_ERROR`               | `status` ausente o no válido, o campos distintos de `status` |
| `503` | `SERVICE_UNAVAILABLE`            | Servicio temporalmente no disponible                       |

El frontend identifica el `409` y el `503` por estado HTTP, sin depender de `error.code`. Ante un `409` pide recargar el ticket; no reintenta automáticamente ninguna mutación. En todos los errores muestra `error.requestId` como código de referencia.

**Pendiente de decisión** (no implementar hasta acordarlo):

* **`resolvedAt`:** si se fija al pasar a `resolved`, qué ocurre al pasar a `closed` y si se borra al reabrir el ticket;
* **transiciones:** si se permite pasar de cualquier estado a cualquier otro (comportamiento actual de frontend y backend) o se restringen;
* **concurrencia (`409`):** cuándo se emite, con qué `error.code` y si el cliente envía alguna precondición (por ejemplo, el estado esperado). Hoy no hay ninguna aprobada y prevalece la última escritura.

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
  "status": "results",
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

La [recuperación semántica V1](recuperacion-semantica-v1.md) implementa esta ruta de forma optativa y protegida. `status` distingue `results`, `no_documents` e `insufficient_information`; los dos últimos conservan `items: []`. Cada fragmento puede incluir `sourceUrl` HTTPS e `language` si existen metadatos válidos. `score = 1 - distancia_coseno` expresa similitud en [-1, 1], no probabilidad ni confianza calibrada. Se requiere un perfil experimental V2 ligado al modelo y revisión del corpus, sin umbral global aprobado para producción. Se conservan 1000 caracteres; superar los 128 tokens reales produce 422 `QUERY_TOKEN_LIMIT_EXCEEDED`, sin truncamiento. La implementación no sustituye las rutas y dependencias HTTP de autenticación V1.

## Recomendaciones

El comportamiento implementado, sus controles de acceso, abstención y revisión se detallan en el [contrato RAG V1](recomendaciones-rag-v1.md).

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

**Propuesta pendiente de aprobación.** En MVP02 (16-11-2026) se aprobó que `admin` y `agent` consulten los conteos globales de tickets. Esta sección propone la representación del resumen, igual a `TicketSummary` del backend (PR #39) y a lo que muestra el frontend (PR #44).

Respuesta (`200 OK`):

```json
{
  "totalTickets": 14,
  "openTickets": 6,
  "inProgressTickets": 3,
  "resolvedTickets": 4,
  "closedTickets": 1
}
```

Reglas:

* todos los campos son enteros mayores o iguales a 0 y siempre se envían, incluso cuando valen 0;
* cada ticket se cuenta una sola vez, en el campo de su estado actual;
* `openTickets + inProgressTickets + resolvedTickets + closedTickets` es igual a `totalTickets`;
* el alcance es global (todos los tickets) para ambos roles.

Requiere sesión válida. Errores: `401 AUTHENTICATION_REQUIRED`, `403 FORBIDDEN` y `503 SERVICE_UNAVAILABLE`.

**Fuera del MVP, pendientes de aprobación.** No forman parte de la respuesta y el frontend no los muestra:

* tiempo promedio de resolución (depende de la regla de `resolvedAt`);
* recomendaciones aceptadas, modificadas y rechazadas.

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

### Errores de validación

Acordado el 03-11-2026 para todos los endpoints que validan datos de entrada. Un error de validación responde `422` con `error.code: "VALIDATION_ERROR"`, dentro de la misma envoltura `error` de los demás errores. `error.details` es una lista de objetos `{ field, message }`:

* `field`: nombre del campo en la solicitud JSON, en `camelCase`, igual que en el contrato (por ejemplo, `title`);
* `message`: mensaje en español que el frontend puede mostrar junto a ese campo.

El backend debe adaptar la respuesta de validación predeterminada de FastAPI (`{"detail": [...]}`), que no cumple este formato. Si `details` no trae la lista esperada, el frontend muestra un mensaje general. Si un campo trae varios mensajes, se muestra el primero.

#### Campos no previstos

**Propuesta pendiente de aprobación.** En la creación de tickets y en el cambio de estado, una solicitud con cualquier campo que el contrato no define para esa operación responde `422` con `error.code: "VALIDATION_ERROR"` y no produce efectos. El campo no se ignora ni se aplica.

* `details` no nombra los campos no previstos: llega como `null` o como lista vacía. Si además hay campos previstos inválidos, puede incluir solo esos.
* El frontend envía únicamente los campos del contrato. Si recibe este `422` sin campos en `details`, muestra el mensaje general de la operación con `error.requestId` como código de referencia.

El núcleo de tickets rechaza campos adicionales (`extra="forbid"` en `EsquemaTicket`); la composición HTTP debe conservar ese rechazo antes de cualquier efecto.

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

La [composición local MVP09](ingreso-local-mvp04.md#registro-y-recomposición-mvp09)
permite repetir el CRUD con servicios persistentes y la UI actual, exclusivamente
en testing propio. No habilita la fábrica productiva ni ratifica las decisiones
pendientes. Conserva DTO, paginación y PATCH de estado; los filtros ampliados,
PATCH de otros campos y clasificación ML no forman parte de esta incorporación.

* detalles pendientes del [contrato de autenticación V1](autenticacion-v1.md), sobre la arquitectura de sesiones ya aprobada;
* política de CORS;
* límites de paginación;
* límite de tamaño y formatos de documentos;
* códigos definitivos de errores;
* filtros disponibles para tickets;
* en la creación de tickets: unidad de conteo de las longitudes (el frontend cuenta unidades de JavaScript `string.length`, que pueden diferir de los caracteres de Python en emojis y otros símbolos);
* aprobación de la propuesta de respuesta ante [campos no previstos](#campos-no-previstos) en la creación y el cambio de estado de tickets;
* forma de representar categorías y áreas;
* estrategia para operaciones de IA que requieran procesamiento prolongado;
* presupuestos numéricos por operación/tramo pendientes; P8 ya prohíbe reintentos automáticos de escrituras de autenticación;
* aprobación de la representación propuesta para el resumen de métricas y de las métricas adicionales (tiempo promedio de resolución y revisiones de recomendaciones);
* en el cambio de estado de tickets: regla de `resolvedAt`, transiciones permitidas y concurrencia (`409` y su `error.code`).

## Criterios de aceptación

Este contrato se considerará aceptado cuando:

* frontend y backend acuerden las rutas y estructuras principales;
* Machine Learning confirme los campos necesarios para predicciones;
* los estados compartidos estén documentados;
* las decisiones pendientes se encuentren registradas;
* los ejemplos no contengan secretos ni datos personales reales;
* los tres integrantes aprueben el documento mediante el pull request correspondiente.
