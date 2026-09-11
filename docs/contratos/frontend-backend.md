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

En desarrollo local:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Las solicitudes del frontend utilizarán:

```text
http://localhost:8000/api/v1
```

El puerto `3000` corresponde al frontend Next.js y no debe utilizarse como URL del backend.

## Autenticación

El mecanismo definitivo de autenticación todavía debe documentarse mediante una decisión técnica.

Rutas iniciales previstas:

| Método | Ruta                  | Propósito                      |
| ------ | --------------------- | ------------------------------ |
| `POST` | `/api/v1/auth/login`  | Iniciar sesión                 |
| `POST` | `/api/v1/auth/logout` | Cerrar sesión                  |
| `GET`  | `/api/v1/auth/me`     | Obtener el usuario autenticado |

El frontend no deberá almacenar contraseñas ni recibir hashes de contraseñas.

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

* mecanismo de autenticación y almacenamiento de sesión;
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
