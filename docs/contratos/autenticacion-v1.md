# Contrato API de autenticación V1

## 1. Estado, responsables y alcance

- Estado del documento: borrador para revisión humana.
- Responsables de revisión: Product Owner y equipo SynapDesk.
- Estado funcional: autenticación no implementada en la rama documental actual.
- Propósito: acordar interfaces compatibles para la implementación posterior de frontend y backend.

Este documento distingue cuatro estados:

| Estado | Significado |
| --- | --- |
| Decisión aprobada | Requisito autorizado por el Product Owner; no implica implementación existente. |
| Propuesta | Representación o valor que requiere confirmación o calibración. |
| Pendiente | Aspecto todavía sin definición suficiente para implementarlo. |
| No implementado | Funcionalidad prevista que no existe en esta rama. |

V1 incluye obtención de contexto CSRF, login, consulta de identidad y logout individual. No incluye registro público, MFA, OAuth ni recuperación de contraseña por correo. El alta inicial se realizará mediante comando administrativo, sin contraseñas predeterminadas. No se especifican aquí el nombre ni las opciones de ese comando.

## 2. Referencias y convenciones

- [Contrato general frontend–backend](frontend-backend.md): convenciones compartidas y formato de errores.
- [Modelo de dominio](../arquitectura/modelo-dominio.md): usuarios, roles y auditoría.
- [Estrategia de entornos](../arquitectura/entornos.md).
- [Estrategia de staging](../arquitectura/staging.md).
- [ADR del monolito modular](../adr/0001-monolito-modular.md).
- [ADR de staging](../adr/0004-estrategia-staging.md).
- [Tipos públicos provisionales del frontend](../../frontend/src/types/index.ts).

Se conservan JSON, prefijo /api/v1, campos camelCase, UUID representados como texto y fechas ISO 8601 en UTC. Los valores técnicos de roles permanecen en inglés; documentación y mensajes públicos se redactan en español. Los ejemplos utilizan datos ficticios.

El contrato general conserva las reglas comunes. Este documento concentra los detalles de autenticación. Una decisión pendiente no constituye una autorización para elegir su comportamiento durante la implementación.

## 3. Arquitectura y despliegue

**Decisiones aprobadas:** FastAPI es la autoridad de autenticación y autorización. Las sesiones son opacas y persistidas en PostgreSQL. JWT no será el mecanismo principal.

El flujo público previsto es:

1. Navegador → Next.js bajo el mismo origen público del frontend en Vercel → proxy /api/v1/*.
2. Proxy → backend FastAPI en Render.
3. FastAPI → PostgreSQL para validar usuarios, sesiones y controles persistentes.

Render será el destino del proxy, no la URL que consumirá directamente el navegador. La URL directa al backend descrita en documentación previa corresponde a la configuración provisional; no define el acceso público de autenticación V1.

HTTPS será obligatorio en producción. El proxy no sustituye la autorización del backend. El diseño operativo deberá garantizar el transporte de cookies y respuestas Set-Cookie, así como la validación del origen público sin confiar en cabeceras reenviadas arbitrariamente por clientes.

**Pendiente:** mecanismo y configuración del proxy, confianza en intermediarios, tratamiento de cabeceras reenviadas, restricciones del acceso directo a Render y configuración CORS. No se aprueba ninguna excepción de origen por la existencia del proxy.

## 4. Identidad y DTO AuthUser

**Decisión aprobada:** AuthUser será un DTO específico de autenticación, reutilizado por login y /me. No reemplaza ni modifica el tipo público User. Esta tarea lo define únicamente en documentación.

**Decisión aprobada:** AuthUser tiene exactamente los siguientes tres campos obligatorios, basados en los nombres públicos existentes:

| Campo obligatorio | Representación | Significado |
| --- | --- | --- |
| id | UUID como texto | Identificador público del usuario. |
| email | Texto | Correo electrónico normalizado del usuario. |
| role | admin o agent | Rol vigente verificado por el backend. |

No se incorporan otros campos obligatorios: name, isActive, createdAt y updatedAt pertenecen al tipo público User y no se requieren en AuthUser. No se inventan equivalencias con atributos físicos de otra rama. Las reglas exactas de normalización del correo siguen pendientes en la sección de login.

Cuerpo de respuesta aprobado, compartido por login y /me:

~~~json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "agente@example.invalid",
    "role": "agent"
  }
}
~~~

AuthUser representa el objeto contenido en user. La envoltura user y los campos obligatorios id, email y role son decisiones aprobadas. Esta definición documental no implica que la funcionalidad esté implementada.

Nunca se incluirán contraseñas, hashes, tokens de sesión ni datos internos. El servicio provisional que espera User directo para /me requerirá adaptación posterior a esta definición aprobada; no se modifica en esta tarea.

## 5. Gestión de sesiones

**Decisiones aprobadas:**

- Cada login exitoso crea una nueva sesión opaca.
- Vigencia absoluta máxima: 8 horas desde la creación; la actividad no amplía ese máximo.
- Tiempo máximo de inactividad: 30 minutos.
- FastAPI verifica vigencia, revocación, usuario activo y rol vigente.
- Se permiten sesiones simultáneas.
- Logout revoca únicamente la sesión actual.
- Una sesión revocada o caducada no puede reutilizarse.

**Decisión aprobada:** si un login se completa exitosamente y el navegador presenta una sesión anterior válida, el backend la reemplaza y revoca, creando una credencial opaca nueva. La credencial anterior no podrá reutilizarse. Las sesiones independientes de otros dispositivos no se revocan. El backend determina la identidad mediante sus verificaciones, sin confiar en una identidad indicada por el cliente, y conserva los controles CSRF y de origen.

**Pendiente:** orden transaccional y tratamiento de fallos parciales del reemplazo. Si la sesión anterior es inválida o ha expirado, el procedimiento exacto de limpieza y recuperación sigue pendiente.

La sesión deja de ser válida cuando alcanza cualquiera de los dos límites. Las comprobaciones del backend son obligatorias aunque el navegador conserve la cookie. El rol no debe quedar congelado como autoridad en el cliente ni en una copia desactualizada de la sesión.

El secreto opaco se entrega mediante cookie; no se devuelve en JSON. PostgreSQL conservará una representación no recuperable del secreto, nunca el token portador en texto plano. Las contraseñas se protegerán con Argon2id. No se persistirán secretos en almacenamiento del navegador ni en registros de auditoría.

**Pendiente:** representación criptográfica del token almacenado, esquema de persistencia, definición de actividad que actualiza la sesión, frecuencia de actualización, sincronización temporal, resolución de solicitudes concurrentes y limpieza de registros. No se prescribe un algoritmo adicional ni un esquema físico.

## 6. Cookies y CSRF

### Cookie de producción

Los siguientes atributos constituyen una **propuesta**, no una configuración implementada:

| Atributo | Propuesta |
| --- | --- |
| Nombre | __Host-synapdesk_session |
| HttpOnly | Sí |
| Secure | Sí |
| SameSite | Lax |
| Path | / |
| Domain | Ausente; cookie de solo host. |

HTTPS en producción y el uso de HttpOnly son decisiones aprobadas. La persistencia de la cookie en el navegador, Max-Age/Expires y su relación con las caducidades del servidor quedan por especificar. La recarga debe conservar una sesión todavía vigente.

La eliminación de la cookie deberá dirigirse a la misma cookie emitida, conservando su ámbito efectivo. Borrar la cookie no sustituye la revocación en PostgreSQL.

**Pendiente:** configuración local y cualquier excepción HTTP. No debe suponerse que la propuesta de producción puede trasladarse sin cambios a desarrollo.

### Contexto CSRF y origen

**Decisiones aprobadas:** CSRF para operaciones mutables, incluidos login y logout; validación estricta del origen. SameSite y CORS no reemplazan estos controles.

GET /api/v1/auth/csrf permitirá obtener contexto/token para solicitudes anónimas y autenticadas. El contexto anterior al login no se reutilizará como contexto de la sesión autenticada. Después del login, el cliente deberá obtener el contexto correspondiente y vinculado a esa sesión antes de realizar operaciones mutables; la vinculación criptográfica exacta sigue pendiente.

**Dependencia bloqueante:** el protocolo CSRF deberá estar completamente definido antes de implementar un login funcional con cookies.

- CSRF_PROTOCOL_STATUS: PENDING_DESIGN.
- CSRF_IMPLEMENTATION_GATE: BLOCKED_UNTIL_DEFINED.

Estos estados bloquean la implementación, no la revisión del contrato documental.

**Pendiente:** vinculación criptográfica, protocolo exacto del contexto previo y posterior al login, transporte y cabeceras, formato de respuesta, rotación y caducidad, tratamiento de orígenes y cabeceras del proxy, y comportamiento frente a errores. También queda pendiente el tratamiento exacto de Origin ausente y Referer. Se conserva la separación aprobada entre el contexto anónimo y el autenticado, sin seleccionar automáticamente un protocolo, mecanismo alternativo ni configuración.

## 7. Endpoints de autenticación

Todos los endpoints siguientes están **no implementados** en esta rama.

| Método | Ruta pública relativa | Finalidad |
| --- | --- | --- |
| GET | /api/v1/auth/csrf | Obtener contexto/token CSRF. |
| POST | /api/v1/auth/login | Iniciar sesión. |
| GET | /api/v1/auth/me | Consultar identidad. |
| POST | /api/v1/auth/logout | Revocar la sesión actual. |

### GET /api/v1/auth/csrf

Disponible para contextos anónimos y autenticados. La respuesta permitirá preparar las operaciones mutables posteriores sin exponer el secreto de sesión. Un token anónimo anterior al login no será válido como token de la sesión autenticada.

**Propuesta:** éxito 200. **Pendiente:** cuerpo, cabeceras, efectos sobre cookies o persistencia anónima y errores específicos. La existencia de contexto CSRF no acredita autenticación.

### POST /api/v1/auth/login

No requiere una sesión autenticada previa; sí exige contexto CSRF y validación estricta de origen. Entrada prevista: objeto JSON con email y password, ambos campos de texto requeridos.

~~~http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json

{"email":"agente@example.invalid","password":"ejemplo-ficticio-no-utilizar"}
~~~

El ejemplo muestra solo el cuerpo y la ruta; no es una solicitud completa para ejecutar: se omiten origen y prueba CSRF porque su transporte está pendiente.

El backend deberá validar el formato del correo y normalizarlo coherentemente con el alta administrativa y su unicidad. **Pendiente:** reglas exactas de normalización y validación, límites de entrada y política de contraseñas. No se deducen reglas de una implementación de otra rama ni se normaliza la contraseña como si fuera un correo.

Antes de conceder acceso deberán cumplirse origen, CSRF y límites persistentes. Se verificarán credenciales mediante Argon2id y el estado activo del usuario. Las cuentas inexistentes, contraseñas incorrectas y cuentas inactivas recibirán un error público indistinguible. El orden preciso y la estrategia para evitar diferencias observables quedan por especificar.

Al tener éxito se crea una nueva sesión con una credencial opaca nueva y se emite su cookie. Si el navegador presenta una sesión anterior válida, el backend la reemplaza y revoca según la sección 5, sin revocar sesiones independientes de otros dispositivos ni confiar en la identidad indicada por el cliente. La respuesta utilizará el cuerpo aprobado de la sección 4, con AuthUser dentro de user; el estado 200 continúa como propuesta. No se expone el token portador en JSON. Se conservan CSRF y origen; el contexto CSRF previo al login no se convierte en contexto autenticado.

Errores previstos según la causa: 400, 401, 403, 422, 429, 500 y 503; véase la sección 8. El orden transaccional, los fallos parciales de emisión/persistencia y la limpieza y recuperación de una sesión anterior inválida o expirada quedan pendientes.

### GET /api/v1/auth/me

La sesión se obtiene de la cookie. El backend comprueba caducidad absoluta, inactividad, revocación, usuario activo y rol vigente. No se aceptará como identidad una declaración del cliente.

**Decisión aprobada:** devolver el cuerpo de la sección 4 con AuthUser dentro de user y sus tres campos obligatorios id, email y role; rechazar con 401 cuando no exista una sesión válida. **Propuesta:** estado de respuesta exitosa 200.

Errores generales adicionales: 500 y 503. No se impone CSRF a esta lectura como si fuera una operación mutable; su relación con la actualización de actividad y las políticas de origen queda por precisar.

### POST /api/v1/auth/logout

Requiere protección CSRF y validación de origen. Para una sesión válida, el backend revoca la sesión actual y elimina su cookie. Las demás sesiones simultáneas permanecen independientes. Tras una respuesta de éxito no se podrá reutilizar el token revocado.

Respuesta prevista, sin JSON:

~~~http
HTTP/1.1 204 No Content
~~~

El ejemplo omite Set-Cookie: su nombre y ámbito exactos dependen de la propuesta pendiente de cookie. No se inventa un token ni una fecha de borrado.

**Pendiente:** cuerpo de solicitud, tratamiento de sesión ausente, vencida o ya revocada; decidir si esas situaciones producen 204 o 401 y cómo interactúan con CSRF. También quedan por especificar fallos parciales y concurrencia. Este documento no declara idempotencia ni un orden de precedencia de errores todavía no acordado.

Errores previstos cuando correspondan: 400, 401, 403, 422, 500 y 503. No se agrega limitación específica de logout por analogía con login.

## 8. Errores y respuestas HTTP

**Decisión aprobada:** reutilizar ApiErrorBody dentro de error, exactamente como en el contrato general y los tipos públicos existentes.

| Campo dentro de error | Tipo público existente | Regla |
| --- | --- | --- |
| code | string | Código técnico; catálogo de autenticación pendiente de cierre. |
| message | string | Mensaje público en español, sin revelar información sensible. |
| details | unknown o null | Información pública segura; nunca contraseñas, tokens ni trazas. |
| requestId | string | Identificador de correlación; seguir la convención del ejemplo general. |

Ejemplo propuesto para 401 de login; INVALID_CREDENTIALS es el código propuesto, no un catálogo completo aprobado:

~~~json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Correo o contraseña incorrectos.",
    "details": null,
    "requestId": "4762428a-c356-44d7-8f43-e48fc16e393a"
  }
}
~~~

La misma respuesta pública se aplicará a los tres casos de rechazo de credenciales indicados en login. No se incluirán pistas en details sobre existencia o activación de cuentas.

| Estado | Significado previsto |
| --- | --- |
| 400 | Solicitud incorrecta. |
| 401 | Credenciales inválidas o ausencia de autenticación válida. |
| 403 | Permisos insuficientes o CSRF inválido. |
| 422 | Validación de entrada. |
| 429 | Limitación de intentos de autenticación. |
| 500 | Error interno. |
| 503 | Servicio indisponible. |

**Pendiente:** códigos específicos, distinción exacta entre 400 y 422, respuesta al origen rechazado, prioridad entre errores concurrentes, detalle seguro de validación y posibles cabeceras de reintento. Los fallos internos o de PostgreSQL no deben publicarse como credenciales incorrectas. Las respuestas de error no expondrán contraseñas, hashes, tokens, SQL, rutas internas, variables de entorno ni trazas.

## 9. Autorización y roles

Los roles iniciales son admin y agent. FastAPI comprobará usuario activo y rol vigente en las operaciones protegidas. El proxy, el DTO y la ocultación de controles del frontend no sustituyen esta verificación.

El [modelo de dominio](../arquitectura/modelo-dominio.md) describe responsabilidades generales de cada rol; no constituye una matriz completa de permisos por recurso. Esa matriz y el tratamiento operativo de cambios de rol o desactivación quedan pendientes. No se conceden permisos adicionales ni se crean endpoints administrativos en este contrato.

## 10. Límites de intentos y auditoría

**Decisiones aprobadas:** la limitación de intentos será persistente y no desaparecerá al reiniciar el proceso. Se auditarán eventos de autenticación sin registrar contraseñas, tokens portadores ni pruebas CSRF.

**Pendiente de definición o calibración:** claves de agrupación, umbrales, ventanas, desbloqueo, concurrencia del contador, identificación del cliente detrás del proxy y tratamiento de fallos del limitador. No se fijan cantidades arbitrarias.

La auditoría deberá permitir revisar el flujo de autenticación. Su catálogo mínimo de eventos, campos, almacenamiento, acceso y retención quedan pendientes; el dominio ya prevé auditoría, pero no resuelve esos parámetros.

## 11. Criterios de aceptación

### Calidad documental

- Separar decisiones aprobadas, propuestas, pendientes y funcionalidades no implementadas.
- Mantener enlaces relativos válidos y ejemplos JSON coherentes con las convenciones comunes.
- Conservar los cuatro campos de ApiErrorBody dentro de error.
- Reutilizar en login y /me el AuthUser aprobado con id, email y role obligatorios dentro de user, sin modificar User.
- No presentar ejemplos incompletos de CSRF o cookies como solicitudes listas para ejecutar.
- Resolver los pendientes que afecten interoperabilidad antes de implementar esas partes; en particular, cerrar completamente el protocolo CSRF antes de implementar login funcional con cookies.

### Comportamiento verificable en la implementación posterior

- Una cuenta activa con credenciales válidas inicia sesión; /me devuelve su identidad y rol vigente.
- La recarga conserva la sesión mientras siga válida.
- Las tres causas de rechazo de credenciales producen una respuesta pública indistinguible.
- El backend rechaza sesiones ausentes, caducadas o revocadas; se comprueban ambos límites de tiempo.
- Logout válido devuelve 204 y el token revocado no vuelve a autenticar, aunque se conserve una copia.
- Las sesiones simultáneas están permitidas; logout individual no revoca las otras.
- Un login exitoso reemplaza y revoca la sesión anterior válida presentada por el navegador, emite una credencial opaca nueva e impide reutilizar la anterior; las sesiones independientes de otros dispositivos permanecen válidas según su propia vigencia.
- Login y logout rechazan solicitudes que incumplen CSRF u origen según el protocolo que se acuerde.
- El contexto CSRF anónimo previo al login no se acepta como contexto autenticado.
- El control de intentos sobrevive al reinicio y produce 429 al alcanzar los límites que se acuerden.
- Usuarios inactivos o roles sin permiso no obtienen acceso protegido.
- El navegador utiliza /api/v1/* del mismo origen y el backend sigue autorizando cada operación.
- No se exponen secretos en JSON, errores, persistencia en texto plano ni auditoría.

Estos criterios describen verificaciones futuras. No se han ejecutado pruebas funcionales como parte de la redacción documental.

## 12. Dependencias y decisiones pendientes

| Tema | Estado y definición necesaria |
| --- | --- |
| AuthUser | Definición aprobada: id, email y role obligatorios dentro de user; adaptar después los consumidores provisionales sin modificar User en esta tarea. |
| Éxitos HTTP | Confirmar 200 para csrf, login y me; logout tiene respuesta prevista 204. |
| CSRF y origen | Dependencia bloqueante para login funcional con cookies: cerrar vinculación criptográfica, contextos previo/posterior, transporte, cabeceras, rotación, caducidad, origen/proxy y errores. |
| Cookies | Confirmar propuesta de producción, persistencia y eliminación; acordar desarrollo local. |
| Sesiones | Definir actividad, concurrencia, representación del token, limpieza y fallos parciales. |
| Logout excepcional | Acordar respuesta ante sesión ausente, vencida o revocada y prioridad de controles. |
| Login | Precisar normalización, validación, orden transaccional y fallos parciales del reemplazo aprobado, limpieza y recuperación de sesión anterior inválida o expirada, y mitigación de diferencias observables. |
| Argon2id | Calibrar parámetros y política de actualización de hashes; no se fijan valores aquí. |
| Intentos | Definir y calibrar límites persistentes, concurrencia y operación detrás del proxy. |
| Auditoría | Acordar eventos mínimos, campos, acceso y retención. |
| Permisos | Acordar matriz por recurso y tratamiento operativo de cambios de usuario. |
| Errores | Cerrar catálogo, casos excepcionales y cabeceras conservando ApiErrorBody. |
| Proxy y despliegue | Especificar implementación y confianza, sin consumir Render directamente desde el navegador. |
| Alta administrativa | Definir procedimiento del comando y entrega segura de credenciales. |

Los detalles de persistencia y configuración se resolverán en etapas posteriores autorizadas. La arquitectura aprobada por el Product Owner todavía debe reflejarse, cuando se autorice, en documentos de arquitectura que siguen describiendo el mecanismo como pendiente. Esta tarea no modifica ADR ni configuración.

La revisión humana de este borrador no equivale a autorización para implementar, ejecutar migraciones o desplegar.
