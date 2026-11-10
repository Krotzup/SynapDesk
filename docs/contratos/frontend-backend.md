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

Configuración provisional documentada para desarrollo local:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

En esa configuración local provisional, las solicitudes del frontend se dirigen directamente a:

```text
http://localhost:8000/api/v1
```

El puerto `3000` corresponde al frontend Next.js y no debe utilizarse como URL directa del backend. Para autenticación V1, el navegador consumirá rutas relativas `/api/v1/*` bajo el origen público del frontend; el proxy reenviará las solicitudes al backend en Render como destino interno. El navegador no consumirá directamente la URL de Render. El [contrato de transporte de autenticación](autenticacion-v1.md#3-arquitectura-y-despliegue) formaliza proxy de mismo origen, adaptador SSR seguro por petición, cookies necesarias, respuestas privadas sin caché compartida y secretos exclusivamente en servidor. Set-Cookie debe llegar al navegador sin exponer la credencial en JSON. La configuración concreta y el perfil HTTP local siguen sujetos a revisión; no cambian los valores de entorno ni el cliente actual por documentarlos.

El destino del proxy se configurará en el servidor Next.js mediante BACKEND_INTERNAL_URL, requisito futuro todavía no implementado ni incorporado a los archivos de entorno. Ejemplo local: navegador en `http://localhost:3000`, destino FastAPI `http://localhost:8000` y solicitud pública `http://localhost:3000/api/v1/...`. Mantener un host consistente para cookies, sin mezclar localhost y 127.0.0.1. No aceptar destinos elegidos por el cliente ni exponer BACKEND_INTERNAL_URL mediante NEXT_PUBLIC_*. NEXT_PUBLIC_API_URL no se usará para autenticación del navegador mediante proxy; sus usos actuales fuera de ese flujo permanecen hasta que se migren expresamente.

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
  "updatedAt": "2026-09-11T18:30:00Z",
  "resolvedAt": null
}
```

Los valores predichos mediante Machine Learning deberán identificarse claramente y no confundirse con decisiones validadas.

### Creación de tickets (`POST /api/v1/tickets`)

Reglas acordadas entre frontend y backend el 03-11-2026. El frontend ya las aplica con datos de ejemplo (PR #27); el endpoint todavía no está implementado en el backend.

**Solicitud.** El cliente envía únicamente `title` y `description`. El servidor asigna los demás campos: `id`, `status`, `priority`, `createdBy`, fechas y, más adelante, la clasificación.

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

**Autenticación y permisos.** Requiere sesión válida. Pueden crear tickets los roles `admin` y `agent`. Como toda mutación de V1, se envía con `fetch` desde el cliente, a través del proxy de mismo origen, con `X-CSRF-Token` y `Origin` válido, según el [contrato de autenticación V1](autenticacion-v1.md). La asignación, la modificación y la visibilidad de tickets quedan para la matriz de permisos.

**Errores.**

| HTTP  | `error.code`                     | Caso                                                     |
| ----: | -------------------------------- | -------------------------------------------------------- |
| `401` | `AUTHENTICATION_REQUIRED`        | Sin sesión válida                                        |
| `403` | `CSRF_INVALID`, `ORIGIN_INVALID` | Token CSRF u `Origin` inválidos (rechazo previo a efectos) |
| `403` | `FORBIDDEN`                      | El rol no puede crear tickets                            |
| `422` | `VALIDATION_ERROR`               | `title` o `description` no cumplen las reglas            |
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

En el [prototipo experimental de recuperación](embeddings-recuperacion.md), `score = 1 - distancia_coseno` expresa similitud en [-1, 1], no probabilidad ni confianza calibrada. El CLI admite perfiles experimentales de relevancia asociados al modelo y corpus, con abstención mediante `items: []`; esto no establece un umbral ni campos nuevos para la API pública. La estrategia definitiva del producto y su perfil de relevancia para producción siguen pendientes de evaluación. La ruta HTTP todavía no está implementada por este prototipo.

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

### Errores de validación

Acordado el 03-11-2026 para todos los endpoints que validan datos de entrada. Un error de validación responde `422` con `error.code: "VALIDATION_ERROR"`, dentro de la misma envoltura `error` de los demás errores. `error.details` es una lista de objetos `{ field, message }`:

* `field`: nombre del campo en la solicitud JSON, en `camelCase`, igual que en el contrato (por ejemplo, `title`);
* `message`: mensaje en español que el frontend puede mostrar junto a ese campo.

El backend debe adaptar la respuesta de validación predeterminada de FastAPI (`{"detail": [...]}`), que no cumple este formato. Si `details` no trae la lista esperada, el frontend muestra un mensaje general. Si un campo trae varios mensajes, se muestra el primero.

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
* en la creación de tickets: unidad de conteo de las longitudes (el frontend cuenta unidades de JavaScript `string.length`, que pueden diferir de los caracteres de Python en emojis y otros símbolos) y respuesta ante campos no previstos en la solicitud;
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
