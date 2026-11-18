# Tickets persistentes — MVP01/MVP02

Núcleo interno, sin routers nuevos. Reutiliza [Ticket ORM](../persistencia/modelos/ticket.py),
[Usuario](../persistencia/modelos/usuario.py), las migraciones 0001–0006 y las
[sesiones existentes](../seguridad/sesiones.py). No modifica autenticación,
frontend, ML ni esquema. No depende de clasificación para guardar un ticket.

## Operaciones y transacciones

[RepositorioTickets](repositorio.py) ejecuta crear/listar/detalle/actualizar_estado/resumen
en una Session PostgreSQL con transacción activa. Es una primitiva de confianza:
**no autentica ni autoriza**. Su creador_id identifica la FK, no acredita identidad.
No usarlo directamente como dependencia o handler HTTP.

[ServicioTickets](servicio.py) coordina una Session y un commit por operación,
reutilizando ReferenciaSesion y ServicioSesiones. Deriva el creador de la sesión
reconsultada; rechaza UUID, AuthUser, roles o credenciales de servicio presentados
como identidad. Revalida vigencia/autorización después de la consulta/escritura y
de las esperas, antes de commit. No renueva actividad automáticamente. Devuelve
DTO independiente del ORM solo si el commit terminó; los errores revierten.
No cierra el motor recibido: su ciclo de vida pertenece a la aplicación.

- Crear: title 5–150 y description 10–5000 tras recorte; UUID/fechas/defaults de
  PostgreSQL, open/medium, sin categoría, área, asignado o resolvedAt iniciales.
- Listar: page desde 1, pageSize=20, máximo interno candidato 100; orden fijo
  createdAt DESC, id DESC. Un SELECT devuelve total, página y usuarios con el
  mismo snapshot, incluso cuando no hay registros o la página está fuera de rango.
  Si la posición calculada supera `bigint` de PostgreSQL, la subconsulta de filas
  se vacía sin enviar OFFSET; el conteo sigue en la misma sentencia. Se conservan
  `page` y `pageSize` solicitados, sin límites nuevos ni cambios del DTO.
  No hay consultas N+1 ni lectura de hashes por las proyecciones de tickets.
- Detalle: misma representación que listado; ausencia tiene código interno
  NO_ENCONTRADO, distinto de infraestructura/transacción.
- Estado: solo open/in_progress/resolved/closed, bloqueo FOR UPDATE de la fila,
  actualización del estado y updatedAt con reloj PostgreSQL posterior al lock,
  sin retroceder fechas. Una repetición del mismo estado no cambia updatedAt.
  estado_esperado optativo permite detectar un conflicto antes de escribir. Sin
  él, las escrituras se serializan; prevalece la última, sin sobrescribir campos
  ajenos. Esta precondición es interna, no un campo/If-Match HTTP aprobado.
- Conteos: totalTickets, openTickets, inProgressTickets, resolvedTickets y
  closedTickets, calculados en una sola consulta, incluidos ceros reales.

No existe una matriz de transiciones ratificada en los contratos inspeccionados:
el núcleo admite los cuatro estados del modelo sin inventar una máquina de
estados. Conserva resolvedAt: **no deduce resolución, reapertura ni cierre lógico**
a partir de un cambio de estado. Esa política requiere acuerdo antes del adaptador
HTTP. Tampoco implementa edición libre, asignación, DELETE o auditoría de tickets.
La auditoría de autenticación existente no se presenta como auditoría de tickets.

## Autorización y cierre

El [contrato frontend–backend](../../../docs/contratos/frontend-backend.md) recoge
la matriz V1 aprobada por el Product Owner para MVP02: admin y agent pueden crear,
listar, consultar detalle, cambiar estado y consultar conteos globales de tickets.
Las cinco operaciones requieren sesión persistente vigente y cuenta activa; el rol
se consulta en PostgreSQL. El anónimo, UUID de usuario y credencial SEC-01B no
autorizan ninguna. La antigua restricción por propiedad era una propuesta, no una
regla aprobada. No se conceden asignación, borrado, edición libre u otros recursos.

El autorizador opcional es una dependencia de código de confianza; nunca se
deserializa de JSON, se activa por variable de entorno ni recibe un rol del
cliente. Debe devolver exactamente True y recibe la identidad vigente consultada
en PostgreSQL, la operación y el UUID del recurso. Solo puede restringir la matriz
aprobada, nunca ampliarla. Si se acuerda visibilidad por propietario/asignación,
hay que agregar el predicado
de alcance tanto a la página como al total/conteos, no filtrar después de paginar.

El núcleo no interpreta HTTP. Los [adaptadores candidatos](../api/adaptadores_tickets.py)
comprueban método/configuración, Origin de mutaciones (y de GET si está presente),
SEC-01B, evidencia de esquema HTTPS y cookies canónicas con la infraestructura
AUTH-07D.1. Luego usan la sesión persistente del coordinador. Un control interno
de escritura valida CSRF ligado a esa sesión antes y después del trabajo SQL en
la misma Session/transacción. Un CSRF que vence tras el INSERT produce rollback
y 503, sin reintento ni clasificación falsa de rechazo previo a efectos.

No hay APIRouter ni import/instancia del adaptador en la fábrica: **cero rutas de
tickets registradas**. Invocar un candidato con Request ASGI no certifica TLS ni
un flujo de navegador. Deben acreditarse listener TLS/proxy_headers=False, canal
PR #30 y sesión obtenida mediante autenticación HTTP real. CSRF HTTP sigue cerrado;
login/me/logout no están registrados. P4, C01–C09 y procedencia IP exigida por
autenticación siguen pendientes en sus contratos. No se modifica esa seguridad.
No se inventan cuotas ni requisito IP adicional de tickets por analogía con login.
La política de actividad aceptada para tickets también necesita ratificación.

## DTO para Valentina — preparados, endpoints no operativos

Los modelos están en [esquemas.py](esquemas.py). Los ejemplos son formas de
consumo propuestas para la integración posterior, no URLs habilitadas ahora.

| Operación propuesta | Solicitud | Respuesta preparada |
|---|---|---|
| POST /api/v1/tickets | TicketCreate: title, description | Ticket; 201 según contrato |
| GET /api/v1/tickets?page=1&pageSize=20 | TicketPagination | TicketList: items, page, pageSize, totalItems, totalPages |
| GET /api/v1/tickets/{id} | UUID | Ticket, idéntico al elemento de listado |
| PATCH /api/v1/tickets/{id} | TicketStatusUpdate: status exclusivamente | Ticket; candidato con sesión/CSRF transaccionales, sin ruta |
| GET /api/v1/metrics/summary | Sin cuerpo | TicketSummary candidato; **no implementa Metrics completo** |

Ticket conserva id/title/description/status/priority/category/area/createdBy/
assignedTo/createdAt/updatedAt/resolvedAt. createdBy y assignedTo proyectan la
interfaz User de TS: id/name/email/role/isActive/createdAt/updatedAt, sin contraseñas,
hashes, digests o credenciales. AuthUser no sustituye a User. En JSON UUID y fechas
son cadenas, items es una lista; internamente se usan UUID, fechas aware y tuplas
inmutables. Se reutiliza Ticket para listado/detalle, sin variantes duplicadas.

Creación candidata:

```json
{"title":"Equipo sin conexión","description":"El equipo de soporte no puede conectarse a la red."}
```

Cambio de estado candidato:

```json
{"status":"in_progress"}
```

Conteos internos:

```json
{"totalTickets":4,"openTickets":1,"inProgressTickets":1,"resolvedTickets":1,"closedTickets":1}
```

Pendientes de ratificación, sin cambiar los contratos vigentes:

- Política de transiciones/resolvedAt/actividad y precondición concurrente pública.
  La matriz admin/agent y alcance global de estas cinco operaciones ya están aprobados.
- El contrato deja pendiente la unidad Unicode y los campos extra. Aquí se
  propone conteo UTF-16 como string.length del frontend y extra=forbid, sin
  coerción de tipos, rechazando NUL y Unicode no representable en PostgreSQL.
  El recorte interno usa str.strip; sus diferencias con trim de JavaScript para
  algunos espacios Unicode también deben conciliarse antes de abrir HTTP.
- pageSize máximo 100/orden fijo son candidatos internos. No se implementan aún
  search/sort/order/status/priority/area del filtro de frontend; no ignorarlos
  silenciosamente en un futuro endpoint.
- TicketSummary incluye closedTickets y omite promedios/revisiones de IA; no
  rellenar Metrics con valores ficticios para hacer encajar la pantalla.
- El [listado frontend](../../../frontend/src/app/%28dashboard%29/tickets/page.tsx)
  también requiere metrics/summary; el
  [detalle](../../../frontend/src/app/%28dashboard%29/tickets/%5Bid%5D/page.tsx)
  requiere recomendaciones. Desacoplar esas cargas opcionales al conectar el MVP.

Los errores internos ErrorTickets y ErrorSeguridad no son respuestas HTTP.
El adaptador candidato usa ApiErrorBody/requestId del servidor/no-store y el
catálogo existente: validación 422, ausencia TICKET_NOT_FOUND/404, sesión 401,
Origin/CSRF previo y permisos 403, indisponibilidad 503. Debe acordarse la clasificación
pública de conflicto; no crear códigos públicos por
analogía. Sanear ValidationError con errors(include_input=False,
include_context=False), sin exponer objetos de excepción, SQL ni parámetros.
No hay cuota nueva aprobada para tickets por analogía con login.

Valentina puede preparar login/sesión, listado, detalle, creación y cambio de
estado con esos DTO, pero conectar URLs solo al habilitar el canal seguro. El
proxy conserva cookies canónicas, Origin real y token CSRF, agrega SEC-01B solo
en servidor y exige TLS verificado; no inventa X-User-ID/rol. Lecturas SSR por
petición sin caché compartida pueden omitir Origin cuando realmente no existe.
No repetir mutaciones automáticamente ante 503. Métricas y recomendaciones son
cargas opcionales: sus errores no deben impedir mostrar listado/detalle.

Puntos de conexión existentes: [servicio de tickets](../../../frontend/src/services/tickets.ts),
[servicio de métricas](../../../frontend/src/services/metrics.ts),
[servicio de recomendaciones](../../../frontend/src/services/recommendations.ts) y
[dashboard](../../../frontend/src/app/%28dashboard%29/inicio/page.tsx). Cambiar los
mocks por consumo real corresponde al incremento frontend posterior. PR #30
aporta el proxy catch-all, backend-proxy y adaptación SSR; al HEAD inspeccionado
`594310c2cc2cb082a55a1fa49a04dcee3420de82` siguen en su rama, sin integrar aquí.
Requiere BACKEND_INTERNAL_URL HTTPS, perfil de cookies explícito y distribución
privada SEC-01B con CA/hostname verificados; no exponer esas credenciales al cliente.

## Punto de extensión para América

Ticket ya proporciona UUID persistente, title, description, category, area y status.
Para clasificación usar el título/descripción leídos de ese UUID autorizado,
mapear a subject/body según el [contrato backend–ML](../../../docs/contratos/backend-ml.md)
y conservar la versión del artefacto en el flujo ML futuro. No aceptar una ruta
Joblib ni un creador desde el navegador. Las sugerencias no sobrescriben campos
validados del ticket y una falla ML no revierte una creación ya confirmada.

No se agregan imports ML, tablas de predicción, generador RAG, DTO ML paralelo o
dependencia circular. La adaptación type→category/queue→area, confianza por objetivo
y persistencia/endpoint de resultados siguen pendientes de su contrato.
requestId es correlación creada por el servidor en la frontera de error, no una
identidad ni un campo persistido de Ticket. No hay resultados ML asociados nuevos
en este incremento; América debe conservar ticketId y versión del modelo cuando
se implemente el flujo de clasificación separado.

## Validación reproducible

Desde backend, con Python 3.12 del entorno del proyecto:

```text
python -B -m pytest pruebas/test_tickets.py -q
python -B -m pytest pruebas/test_adaptadores_tickets.py -q
python -B -m pytest pruebas --ignore=pruebas/integracion -q
python -B -m pip check
```

Para PostgreSQL usar la instancia testing existente **solo después de acreditar
identidad/puerto**; el [runner CI existente](../../herramientas/CI.md) crea una base
propia efímera, verifica vector, aplica upgrade/current/heads/check y elimina
únicamente su base. La suite incorpora automáticamente las nuevas pruebas:

```text
python -B -m herramientas.ci_backend postgresql
```

Las [pruebas PostgreSQL de servicios](../../pruebas/integracion/test_tickets.py) y
[adaptadores internos](../../pruebas/integracion/test_tickets_http.py) exigen
loopback:5433, nombre completo propio del arnés, usuario/base acreditados,
PostgreSQL 17, pgvector y head 0006. Limpian exclusivamente sus filas. Comprueban
commits desde otra conexión, rollback, CAS concurrente, fechas/estado, relaciones,
proyecciones sin secretos/N+1, totales, ambos roles, las cinco denegaciones por
sesión inválida/inactividad/cuenta inactiva, bloqueo de revocación/desactivación
concurrente, CSRF persistido y rollback si vence durante la escritura. No ejecutarlas
contra una base de desarrollo ni localhost:5432. Si testing no está disponible,
la colección de casos no prueba persistencia y debe declararse pendiente.
