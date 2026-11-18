# Contrato API de autenticación V1

## 1. Estado, responsables y alcance

- Estado del documento: decisiones de seguridad aprobadas, parámetros provisionales y propuestas pendientes diferenciados.
- Responsables de revisión: Product Owner y equipo SynapDesk.
- Estado funcional: servicios internos y adaptadores AUTH-07D.1 implementados; CSRF HTTP registrado y cerrado; login, /me y logout HTTP sin registrar.
- Propósito: formalizar interfaces compatibles dentro del alcance aprobado y distinguir detalles adicionales pendientes de la implementación/operación futura.
- Actualización AUTH-07D.3 (13-11-2026): P1–P10, arquitectura B y mecanismo SEC-01B aprobados expresamente; no habilita rutas ni modifica código.

Los estados de aprobación, implementación y validación son independientes:

| Dimensión | Etiqueta canónica | Significado |
| --- | --- | --- |
| Aprobación | APPROVED | Decisión autorizada por el Product Owner; no acredita implementación ni pruebas. |
| Aprobación | PROPOSED | Propuesta técnica pendiente de revisión; no es un requisito definitivamente aprobado. |
| Aprobación | PROPOSAL_PENDING_TEAM_REVIEW | Propuesta de permisos pendiente de decisión del equipo; no concede acceso. |
| Configuración | PROVISIONAL_CONFIGURATION | Valor operativo inicial, sujeto a calibración y revisión; no es un valor certificado. |
| Validación | PENDING_MEASUREMENT | Faltan mediciones o benchmarks; no describe resultados obtenidos. |
| Diseño | PENDING_DESIGN | Falta una definición técnica suficiente; no autoriza elegirla durante la implementación. |
| Implementación | IMPLEMENTATION_PENDING | Requisito de implementación u operación aún no cumplido. |
| Implementación | NOT_IMPLEMENTED | Funcionalidad cuyo código todavía no existe. |
| Implementación | IMPLEMENTED | Funcionalidad presente y contrastada en archivos; no implica aprobación o validación funcional automática. |

«Decisión aprobada», «propuesta», «pendiente de diseño» y «no implementado» corresponden respectivamente a APPROVED, PROPOSED, PENDING_DESIGN y NOT_IMPLEMENTED. CSRF_IMPLEMENTATION_GATE es un indicador de preparación, no una etiqueta de aprobación: usa IMPLEMENTATION_PENDING mientras falten configuración interoperable y requisitos operativos. No se utilizan BLOCKED_UNTIL_DEFINED ni etiquetas compuestas como sustitutos de estos estados. Las mediciones y verificaciones realizadas se describen separadamente con su evidencia.

Synchronizer Token, los contextos servidor anónimo y autenticado ligado a sesión, X-CSRF-Token, origen estricto, protección de mutaciones e invalidación/rotación de contextos están aprobados. También lo están el transporte Next.js de mismo origen y el logout idempotente de sección 7. Los valores numéricos, nombres concretos de cookies y permisos detallados conservan sus estados provisionales o de propuesta.

Existen fábrica FastAPI, persistencia con cabeza única `0006_user_created`, servicios internos de seguridad/login/consulta/logout/altas y adaptadores HTTP sin registrar. GET `/api/v1/auth/csrf` está registrado con cierre seguro, sin emisión; login, /me y logout siguen 404. Frontend no incorpora todavía esos flujos: el login visual y la redirección de logout no autentican/revocan. Los fundamentos se describen en el [backend](../../backend/README.md#fundamentos-de-seguridad).

La [especificación HTTP V1](autenticacion-http-adaptadores-v1.md) concreta cada endpoint, cookies, precedencia y errores. La [matriz D.3](auth07d3-compatibilidad-y-plan-integracion.md) es la referencia actual de aprobación/compatibilidad/aceptación; D.1/D.2 quedan como antecedentes. P1–P10 no aprueban automáticamente los nombres de cookies, campos CSRF, códigos adicionales o cifras pendientes. P2 sustituye la antigua recuperación anónima propuesta; P3 descarta actividad por /me; P4 añade la excepción limitada de revocación de cuenta inactiva; P8 sustituye el reenvío automático de escrituras tras renovación CSRF. Estos cambios tienen autorización expresa del nuevo encargo, sin alterar políticas administrativas AUTH-07C.

V1 incluye obtención de contexto CSRF, login, consulta de identidad y logout individual. No incluye registro público, MFA, OAuth ni recuperación de contraseña por correo. El alta inicial dispone del [bootstrap administrativo](bootstrap-administrador-v1.md) y las altas posteriores del [coordinador administrativo interno](creacion-administrativa-usuarios-v1.md), con políticas ya aprobadas. No se incorporan rutas administrativas HTTP.

## 2. Referencias y convenciones

- [Contrato general frontend–backend](frontend-backend.md): convenciones compartidas y formato de errores.
- [Modelo de dominio](../arquitectura/modelo-dominio.md): usuarios, roles y auditoría.
- [Estrategia de entornos](../arquitectura/entornos.md).
- [Estrategia de staging](../arquitectura/staging.md).
- [ADR del monolito modular](../adr/0001-monolito-modular.md).
- [ADR de staging](../adr/0004-estrategia-staging.md).
- [Tipos públicos provisionales del frontend](../../frontend/src/types/index.ts).
- [Persistencia relacional inicial](../arquitectura/persistencia-inicial.md).
- [Fábrica FastAPI](../../backend/app/aplicacion.py) y [servicio provisional de autenticación](../../frontend/src/services/auth.ts).

Referencias técnicas consultadas el 30 de octubre de 2026:

- [OWASP: prevención de CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): patrón sincronizado y controles de origen.
- [OWASP: sesiones](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): credenciales opacas y ciclo de vida.
- [OWASP: contraseñas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): Argon2id y calibración.
- [MDN: Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie): ámbito y atributos de cookies.
- [Next.js: cookies](https://nextjs.org/docs/app/api-reference/functions/cookies): lectura en Server Components y escritura en Route Handlers o Server Functions. La consulta corresponde a la documentación vigente; el repositorio declara Next.js 16.3.4 y requerirá verificar el adaptador con esa versión antes de implementar.

Las fuentes respaldan mecanismos generales; no aprueban parámetros, permisos ni decisiones de producto de SynapDesk. El estado de cada decisión se identifica en su sección.

Se conservan JSON, prefijo /api/v1, campos camelCase, UUID representados como texto y fechas ISO 8601 en UTC. Los valores técnicos de roles permanecen en inglés; documentación y mensajes públicos se redactan en español. Los ejemplos utilizan datos ficticios.

El contrato general conserva las reglas comunes. Este documento concentra los detalles de autenticación. Una decisión pendiente no constituye una autorización para elegir su comportamiento durante la implementación.

## 3. Arquitectura y despliegue

**Decisiones aprobadas:** FastAPI es la autoridad de autenticación y autorización. Las sesiones son opacas y persistidas en PostgreSQL. JWT no será el mecanismo principal.

El flujo público previsto es:

1. Navegador → Next.js público, mediante proxy de mismo origen /api/v1/*.
2. Next.js → FastAPI privado mediante SEC-01B y TLS con CA/hostname verificados.
3. FastAPI → PostgreSQL para usuarios, sesiones y controles persistentes.

**APPROVED en AUTH-07D.3:** arquitectura B con despliegue objetivo en Render para Next.js público y FastAPI privado. Sustituye la referencia anterior a Next.js en Vercel como objetivo de autenticación. No acredita recursos desplegados, terminación TLS, red o IP original de Render. El [contrato SEC-01B](comunicacion-interna-segura-v1.md) formaliza credencial opaca por entorno, solo servidor, rotación y fallo seguro. Bearer reutilizable, identidad de usuario y procedencia IP siguen separados.

Render será el destino del proxy, no la URL que consumirá directamente el navegador. La URL directa al backend descrita en documentación previa corresponde a la configuración provisional; no define el acceso público de autenticación V1.

HTTPS será obligatorio en producción. El proxy no sustituye la autorización del backend. El diseño operativo deberá garantizar el transporte de cookies y respuestas Set-Cookie, así como la validación del origen público sin confiar en cabeceras reenviadas arbitrariamente por clientes.

### Contrato de transporte — APPROVED; detalles operativos PROPOSED

**APPROVED:** proxy Next.js de mismo origen, navegador mediante `/api/v1/*`, transporte de cookies necesarias, FastAPI como autoridad de sesiones/permisos, adaptador seguro por petición para Server Components, respuestas privadas sin caché compartida y secretos de infraestructura exclusivamente en servidor. La selección de Route Handlers y los detalles operativos de cabeceras, configuración y confianza siguientes siguen siendo propuestas cuando no se declaran aprobados.

- Navegador: usar rutas relativas `/api/v1/*` y `credentials: same-origin`. No utilizar la URL de Render como base pública de autenticación ni almacenar la credencial de sesión en localStorage o sessionStorage.
- Next.js: utilizar un proxy controlado mediante Route Handlers, con destino FastAPI fijo y privado de servidor. Validar rutas y métodos permitidos, sin aceptar destinos arbitrarios ni redirecciones que puedan reenviar cookies a otro host. No se implementa aquí ese proxy.
- Petición al backend: reenviar exclusivamente las cookies de sesión o contexto CSRF del entorno, `Content-Type`, `X-CSRF-Token`, `Sec-Fetch-Site` y el `Origin` original cuando existan. No reenviar íntegramente todas las cookies del navegador, cabeceras de autorización ajenas ni cabeceras de proxy aportadas por el cliente.
- Respuesta al navegador: conservar estado, cuerpo y cada `Set-Cookie` autorizado como cabecera separada; no unirlos con comas ni convertir secretos en JSON. Los errores y el `204` también deben conservar las cabeceras pertinentes.
- Backend: comparar el origen contra una lista explícita de orígenes públicos, con esquema, host y puerto. No deducir el origen permitido del `Host` de Render ni de `X-Forwarded-Host` sin verificar el intermediario. La topología de confianza y la restricción de acceso directo a Render requieren validación del despliegue antes de implementar.
- Las cabeceras que pretendan identificar IP del cliente se descartan mientras no exista una cadena acreditada; autenticar al intermediario no basta para reconstruir una IP. No hay actualmente cabecera interna IP aprobada. Si la cadena no puede verificarse, no atribuir al usuario una IP tomada de ella ni desactivar el limitador silenciosamente.
- HTTPS en ambos tramos de producción. No introducir secretos en variables `NEXT_PUBLIC_*`. Para el flujo público de mismo origen no se propone habilitar CORS con credenciales ni comodines; mantener cerrado el acceso de otros orígenes. CORS no constituye autorización ni autentica al proxy.
- Respuestas de autenticación, incluidas las de error: `Cache-Control: no-store`; sin caché compartida, prerenderizado estático ni reutilización de respuestas entre usuarios. Las peticiones servidor a servidor usarán también `cache: no-store`.

### Configuración del destino del proxy

**APPROVED:** el navegador utiliza rutas relativas `/api/v1/*`. El destino FastAPI se configura exclusivamente en el servidor Next.js mediante el nombre contractual previsto `BACKEND_INTERNAL_URL`. Esta variable existe en los árboles de PR #30/#32, todavía no integrados en esta rama; su uso seguro con SEC-01B/TLS sigue IMPLEMENTATION_PENDING. No se expone mediante NEXT_PUBLIC_* ni se acepta su valor desde parámetros, cabeceras o cuerpos controlados por el cliente.

Un ingreso local de ensayo puede usar navegador/cliente en `http://localhost:3000`, pero el salto Next.js→FastAPI con SEC-01B exige HTTPS y validación de CA/hostname, incluso localmente. La antigua ilustración de destino HTTP no autoriza transportar bearer en claro. Se conserva `/api/v1/*`, sin omitir ni duplicar el prefijo. Se debe usar un host consistente; no mezclar localhost y 127.0.0.1 dentro del flujo de cookies. Configurar el origen público permitido de forma explícita; el destino interno no lo sustituye.

NEXT_PUBLIC_API_URL no se utilizará para autenticación del navegador mediante proxy. Sus usos actuales para otras funcionalidades no se eliminan ni se consideran migrados por este contrato. El proxy conservará solo cookies/cabeceras autorizadas y cada Set-Cookie separado, sin confiar en cabeceras de proxy arbitrarias. La validación de origen no se deduce de un destino elegido por el cliente.

### SSR aprobado y adaptaciones pendientes

Un Server Component utilizará un adaptador exclusivo de servidor para leer las cookies de la petición actual y construir un encabezado `Cookie` con la lista permitida. No se debe suponer que un `fetch` de Node.js reenvía automáticamente las cookies del navegador ni conserva su almacén. El adaptador llamará solo al destino backend configurado; nunca guardará identidad o cookies en variables globales compartidas entre peticiones.

La lectura de identidad por SSR no exige inventar un `Origin` si la petición de navegación carece de él. Un `Set-Cookie` recibido por un fetch durante el render de un Server Component no se propaga automáticamente al navegador. Login, logout y bootstrap CSRF se canalizan por una respuesta del proxy al navegador; el proxy debe transmitir sus cabeceras correctamente.

**APPROVED para V1:** las mutaciones autenticadas de negocio se realizan con fetch desde componentes o servicios cliente a `/api/v1/*` a través del proxy. Esto incluye crear/modificar tickets, acciones mutables del asistente, login y logout con sus requisitos respectivos, y cualquier operación autenticada que altere datos. No se utilizarán Server Actions ni Server Functions para esas mutaciones en V1. No se agregan excepciones para scripts o clientes externos: el proxy conserva el Origin real y FastAPI aplica el mismo control. Las lecturas SSR siguen permitidas mediante el adaptador por petición, con identidad, cookies autorizadas y ausencia de caché compartida; no son un transporte alternativo para mutaciones durante el render.

| Adaptación futura | Evidencia actual | Cambio requerido, sin implementarlo aquí |
| --- | --- | --- |
| `AuthUser` y respuestas | [User](../../frontend/src/types/index.ts) incluye otros campos. | Añadir después un DTO independiente y la envoltura aprobada, sin sustituir User. |
| `authService.me` y login | [auth.ts](../../frontend/src/services/auth.ts) espera User directo en me y unknown en login. | Ambos deben consumir `{user: AuthUser}`; incorporar obtención de CSRF. |
| Cliente HTTP | [api.ts](../../frontend/src/lib/api.ts) usa una URL directa por defecto y no permite cabeceras por llamada en post. | Rutas relativas en navegador, cabecera CSRF en mutaciones, transporte de cookies, no-store y errores uniformes. |
| Login y logout | [Login](../../frontend/src/app/(auth)/login/page.tsx) no envía solicitudes; [Header](../../frontend/src/components/layout/Header.tsx) solo redirige al salir. | Ejecutar el flujo de la sección 6, borrar estado local solo cuando corresponda y no simular revocación. |
| Identidad y navegación | [Layout](../../frontend/src/app/(dashboard)/layout.tsx) no verifica sesión; el perfil es de demostración. | Consultar me, proteger rutas y mostrar identidad real disponible en AuthUser; no inventar name como campo obligatorio. |
| Proxy y SSR | [next.config.ts](../../frontend/next.config.ts) no configura proxy. | Implementar posteriormente proxy y adaptador servidor; las comprobaciones del backend siguen siendo obligatorias. |

Backend se encargará de DTO, cookies, persistencia, CSRF, origen, límites, auditoría y permisos. Frontend se encargará del proxy/adaptador Next.js, cliente HTTP, formulario, logout, identidad y protección de navegación, coordinando los contratos con backend. La documentación de estructura frontend describe intención de rutas protegidas; el código inspeccionado aún no aplica esa protección.

**PENDING_DESIGN / PENDIENTE_DE_EVIDENCIA:** orígenes concretos por entorno/previews, operación de SEC-01B/rotación, configuración real de Render, CORS operativo y procedencia IP. El mecanismo de intermediario y arquitectura B ya están aprobados. No se aprueban despliegues ni excepciones por este documento.

## 4. Identidad y DTO AuthUser

**Decisión aprobada:** AuthUser será un DTO específico de autenticación, reutilizado por login y /me. No reemplaza ni modifica el tipo público User. Su definición contractual no implica que exista un tipo o endpoint implementado.

**Decisión aprobada:** AuthUser tiene exactamente los siguientes tres campos obligatorios, basados en los nombres públicos existentes:

| Campo obligatorio | Representación | Significado |
| --- | --- | --- |
| id | UUID como texto | Identificador público del usuario. |
| email | Texto | Correo electrónico normalizado del usuario. |
| role | admin o agent | Rol vigente verificado por el backend. |

No se incorporan otros campos obligatorios: name, isActive, createdAt y updatedAt pertenecen al tipo público User y no se requieren en AuthUser. En la persistencia actualmente incorporada, id, correo y rol son los atributos correspondientes a id, email y role; la conversión deberá ser explícita y no serializar el modelo ORM completo. Las reglas de normalización propuestas se describen en login.

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

Nunca se incluirán contraseñas, hashes, tokens de sesión ni datos internos. El servicio provisional que espera User directo para /me requerirá adaptación posterior a esta definición aprobada.

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

El reemplazo aprobado se mantiene. P2 prohíbe recuperar automáticamente sesiones inválidas; P3 establece /me sin renovación. Los detalles operativos que siguen como PROPOSED no revierten esas decisiones.

La sesión deja de ser válida cuando alcanza cualquiera de los dos límites. Las comprobaciones del backend son obligatorias aunque el navegador conserve la cookie. El rol no debe quedar congelado como autoridad en el cliente ni en una copia desactualizada de la sesión.

El secreto opaco se entrega mediante cookie; no se devuelve en JSON. PostgreSQL conservará una representación no recuperable del secreto, nunca el token portador en texto plano. Las contraseñas se protegerán con Argon2id. Las credenciales de sesión/contexto solo se transportan en sus cookies HttpOnly, sin copias en localStorage, sessionStorage ni registros de auditoría; el token CSRF tiene el transporte separado propuesto en la sección 6.

### Representación y vigencia — PROPOSED

Generar una credencial de sesión de 32 bytes mediante CSPRNG y codificarla como base64url sin relleno. Será independiente de UUID internos, identidad, rol y credenciales CSRF. Persistir únicamente SHA-256 del secreto, con unicidad del digest; rechazar representaciones malformadas. SHA-256 se propone para secretos aleatorios de alta entropía, nunca como sustituto de Argon2id para contraseñas.

Usar tiempo de PostgreSQL en UTC después de adquirir los bloqueos necesarios. Para acceso a recursos una sesión solo será válida si no está revocada, el usuario está activo, el rol es admitido y el instante actual es estrictamente anterior tanto a la expiración absoluta como a la última actividad más 30 minutos. La igualdad con un límite significa caducidad. Mantener el rol vigente en usuarios como autoridad, sin congelarlo en la cookie o en un snapshot de sesión. P4 exceptúa únicamente el estado activo para revocación verificada en logout, sin convertir esa sesión en permiso para recursos.

**APPROVED P3:** /me no registra actividad ni modifica los treinta minutos de inactividad o las ocho horas absolutas. Polling y SSR no mantienen viva la sesión. GET csrf y los rechazos tampoco renuevan actividad. Sustituye la propuesta anterior de contabilizar me. La política de actividad de otras operaciones no se amplía por analogía y continúa sujeta a su contrato; no agregar rotación ni duraciones nuevas.

### Transacciones y concurrencia — PROPOSED

- Coordinar bloqueos de usuario, sesiones y contextos en un orden común, con identificadores ordenados cuando haya varias filas. La validación y actualización de actividad no deben reactivar una fila revocada ni una sesión vencida mientras esperaba un bloqueo.
- Las futuras operaciones protegidas que escriban datos deberán verificar sesión, usuario y permisos dentro de la transacción que autoriza esos efectos. Los cambios de rol/desactivación deberán respetar esa coordinación; no basta con consultar al inicio de la petición y usar una identidad desactualizada.
- Verificar Argon2id fuera de bloqueos prolongados. Antes de crear sesión, volver a comprobar usuario activo, rol y que el hash verificado no fue sustituido; si cambió, no emitir sesión con la comprobación anterior.
- Login exitoso: en una única transacción, volver a comprobar vigencia de contexto, token y sesión presentada después de los bloqueos y del trabajo de hash; invalidar el contexto presentado, revocar la sesión anterior válida presentada si existe, crear la nueva sesión y su contexto autenticado, y registrar el evento. Solo después del commit emitir la nueva cookie. No tocar sesiones de otros dispositivos.
- Dos logins con el mismo contexto se serializan: tras el primer éxito, el segundo debe rechazar el contexto invalidado sin crear otra sesión. Un fallo de credenciales no reemplaza ni revoca una sesión anterior válida.
- Logout válido: coordinarse con las operaciones protegidas, persistir revocación de la sesión y del contexto CSRF, y confirmar antes de devolver éxito y borrar cookies. No se promete cancelar operaciones ya autorizadas y confirmadas antes de la revocación; ninguna autorización posterior puede reutilizarla.
- Fallo de transacción: rollback y error público; sin cookie nueva ni éxito de revocación ficticio. Si el commit ocurrió pero la respuesta se perdió, no recuperar el secreto desde su digest ni revertir una revocación: el usuario podrá iniciar sesión de nuevo. Pueden quedar sesiones sin cookie entregada, que vencerán y serán limpiadas.
- La exclusión mutua de login/logout en el cliente y entre pestañas deberá evitar que un borrado de cookie tardío suprima una cookie de un login posterior. No se enviarán secretos por los mecanismos de coordinación entre pestañas; el orden efectivo se verificará con pruebas de navegador. El servidor seguirá impidiendo reutilizar credenciales revocadas incluso ante una carrera del cliente.

**APPROVED P1/P2:** una cookie presentada inválida/vencida/revocada no autentica y no se convierte automáticamente en ausencia: me responde 401; csrf/login conservan la rama de sesión presentada y rechazan sin fallback al contexto anónimo coexistente. Las lecturas no borran cookies. Logout explícito con Origin/servicio, tras confirmar inexistencia/vencimiento/revocación, conserva 204 y puede eliminar la cookie presentada: es limpieza, no recuperación o login automático. Una nueva acción sin esa cookie puede iniciar el flujo anónimo; nunca se repite automáticamente la escritura anterior. Cookie malformada/ambigua se rechaza antes de esa rama idempotente.

### Persistencia: esquema implementado y operación PROPOSED

La revisión `0002_autenticacion_persistencia`, posterior a `0001_usuarios_tickets` sin modificarla, ya implementa las cinco tablas siguientes, con UUID internos, fechas UTC y claves foráneas. El esquema vigente se describe en [persistencia relacional](../arquitectura/persistencia-inicial.md#persistencia-de-autenticación). Esta tabla conserva el diseño conceptual y las propuestas de operación; no añade campos a la API ni acredita servicios funcionales de sesión, CSRF, límites o auditoría.

| Tabla existente | Responsabilidad y datos conceptuales mínimos | Relaciones, restricciones e índices del diseño |
| --- | --- | --- |
| sesiones | Identificador interno, usuario, digest del secreto, creación, última actividad, expiración absoluta, revocación y motivo. | FK a usuarios; digest único y no vacío; fechas coherentes; índices por usuario y para vencimiento/limpieza. La actividad no puede superar el máximo absoluto. |
| contextos_csrf | Identificador, clase anónima/autenticada, digest del secreto anónimo cuando corresponda, sesión cuando corresponda, creación, expiración y revocación. | Exactamente una vinculación: secreto anónimo o sesión; FK y unicidad del contexto autenticado por sesión; digest anónimo único; índices por expiración y sesión. |
| tokens_csrf | Identificador, contexto, digest SHA-256 del token, creación y expiración. | FK al contexto; digest único; vencimiento no posterior al contexto; índice contexto/fecha para depuración y límite de tokens, protegido mediante bloqueo del contexto. |
| limites_autenticacion | Tipo de clave, clave seudonimizada, ventana, intentos o reservas y bloqueo temporal. | Clave/ventana única; contadores no negativos; índices de expiración; actualización atómica con creación concurrente controlada. |
| eventos_autenticacion | Identificador, instante, evento, resultado, requestId y referencias opcionales a usuario/sesión, más metadatos mínimos autorizados. | Índices por tiempo y correlación; sin borrado en cascada que destruya auditoría por limpiar una sesión; acceso restringido. |

La limpieza de sesiones, contextos, tokens y límites vencidos será un proceso administrativo acotado, independiente de la validación de vigencia. Su frecuencia y retención quedan pendientes; no se exige que un registro desaparezca para rechazarlo. No borrar eventos por analogía con datos temporales. Las acciones de FK y el esquema implementado están descritos en la arquitectura de persistencia; la estrategia operativa sigue pendiente. Las restricciones entre filas y los límites de emisión no se consideran implementados por existir las tablas.

Si PostgreSQL falla, las operaciones que necesitan sesión, CSRF o límites persistentes no concederán acceso; responderán 503, sin degradarse a sesiones en memoria ni presentar una caída como credenciales incorrectas. Health conservará su responsabilidad básica. Véanse las políticas de auditoría y errores para los fallos de infraestructura.

## 6. Cookies y CSRF

### Cookies de sesión — atributos formalizados; nombres PROPOSED

P1 y los requisitos de AUTH-07D.3 formalizan perfiles separados, rechazo de configuración inválida, HttpOnly, Secure en producción, SameSite=Lax, Path=/ y ausencia de Domain en __Host-. Los nombres concretos de la tabla conservan PROPOSED C02; el constructor ya permite perfiles explícitos, sin defaults aprobados:

| Atributo | Producción HTTPS | Desarrollo HTTP exclusivamente local |
| --- | --- | --- |
| Nombre | __Host-synapdesk_session | synapdesk_session_dev |
| HttpOnly | true | true |
| Secure | true | false, únicamente en el entorno HTTP local explícito |
| SameSite | Lax | Lax |
| Path | / | / |
| Domain | Ausente; cookie de solo host | Ausente; cookie de solo host |

Los atributos y aislamiento de perfiles quedan formalizados en D.3; los nombres concretos y selección operativa local conservan propuesta C02. HTTP local de cookies no permite omitir TLS de SEC-01B. El prefijo `__Host-` exige Secure, Path=/ y ausencia de Domain según [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie); no se debe reutilizar ese nombre como cookie insegura local.

**Propuesta de persistencia:** fijar Max-Age al tiempo restante hasta el máximo absoluto de ocho horas al emitir la cookie; Expires, si se incluye, debe expresar el mismo límite. No renovar ese máximo con actividad. El servidor siempre comprueba además los 30 minutos de inactividad. Cerrar/reabrir el navegador no garantiza borrar una cookie persistente, y conservarla no prueba vigencia. No se añade una opción de recordar sesión.

Para borrarla después de una revocación confirmada: mismo nombre, Path y ausencia de Domain, con Max-Age=0 y Expires pasado si se usa, conservando atributos de seguridad del entorno. Borrar la cookie no sustituye revocar en PostgreSQL. No transportar una cookie de desarrollo a producción ni aceptar simultáneamente credenciales de ambos perfiles. Elegir un único host local coherente para Next.js; localhost y 127.0.0.1 no comparten cookie de solo host.

La nueva credencial de cada login sustituye la presentada y no adopta identificadores elegidos por el cliente. Las lecturas no rotan ni eliminan automáticamente la cookie de sesión. El proxy deja que el navegador la asocie al host público del frontend, sin Domain de Render.

### Contexto CSRF y origen

**Decisiones aprobadas:** CSRF para operaciones mutables, incluidos login y logout; validación estricta del origen. SameSite y CORS no reemplazan estos controles.

**APPROVED:** Synchronizer Token con contextos del servidor, contexto anónimo anterior al login, contexto autenticado vinculado a sesión, X-CSRF-Token e invalidación/rotación del contexto anterior al autenticar o cerrar sesión. La excepción de CSRF cuando no existe sesión válida que revocar en logout se precisa en sección 7 y no permite revocar una sesión válida sin CSRF.

GET /api/v1/auth/csrf permitirá obtener contexto/token para solicitudes anónimas y autenticadas. El contexto anterior al login no se reutilizará como contexto de la sesión autenticada. Después del login, el cliente deberá obtener el contexto correspondiente y vinculado a esa sesión antes de realizar operaciones mutables.

**Dependencia de habilitación HTTP:** el mecanismo central está aprobado y sus servicios internos existen; antes de registrar/empezar emisión deberán cerrarse configuración interoperable, detalles operativos y autorización de la siguiente implementación.

- CSRF_PROTOCOL_STATUS: APPROVED.
- CSRF_CONFIGURATION_STATUS: PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT.
- CSRF_IMPLEMENTATION_GATE: IMPLEMENTATION_PENDING para habilitación HTTP; primitivas/coordinadores internos ya implementados y ensayados.

Estos estados separan aprobación del mecanismo, calibración de parámetros y requisitos de implementación. La aprobación del contrato no acredita código implementado ni certifica la configuración propuesta.

### Synchronizer Token aprobado y configuración provisional

Se aprueba el patrón sincronizado porque PostgreSQL será la autoridad de contexto y revocación. Un double-submit firmado no es el mecanismo elegido; requeriría vinculación y claves de firma sin eliminar la persistencia aprobada. OWASP describe el patrón sincronizado para aplicaciones con estado; los valores locales siguientes no son prescripciones de OWASP ni parámetros certificados.

| Elemento | Diseño y estado según las reglas anteriores |
| --- | --- |
| Token CSRF | 32 bytes CSPRNG, base64url sin relleno; independiente del secreto de sesión/contexto. |
| Persistencia | Digest SHA-256 del token; nunca el valor portador. Verificación ligada al contexto correcto, con comparación resistente a diferencias temporales. |
| Transporte | X-CSRF-Token está APPROVED para mutaciones. Se proponen los campos JSON `csrfToken` y `expiresAt` UTC; no entregar la prueba por URL ni registrarla en logs. |
| Vigencia del token | Hasta 10 minutos desde emisión, recortados al vencimiento del contexto y, si aplica, de la sesión. |
| Contexto anónimo | 15 minutos desde creación, sin prolongarlo por emitir tokens. Credencial CSPRNG de 32 bytes, digest en contextos_csrf y cookie técnica HttpOnly de solo host. |
| Cookies de contexto anónimo | Nombres propuestos `__Host-synapdesk_csrf_context` en HTTPS y `synapdesk_csrf_context_dev` en HTTP local; mismos atributos del perfil de sesión, Max-Age limitado a los 15 minutos restantes. No autentican usuarios. |
| Contexto autenticado | Vinculado mediante FK a la sesión; no requiere otra cookie técnica. Vigencia limitada por revocación, inactividad y máximo absoluto de esa sesión. |
| Concurrencia | Máximo provisional de ocho tokens no vencidos por contexto. Bloquear el contexto al emitir y retirar vencidos. No expulsar tokens vigentes para renovar, pues pueden estar en uso. Se propone aplazar o rechazar una nueva emisión al llegar al máximo, con 429 y espera derivada del vencimiento; no repetir por ello una mutación. |

Los valores 32 bytes, 10 minutos, 15 minutos y ocho tokens tienen estado `PROVISIONAL_CONFIGURATION` y `PENDING_MEASUREMENT`; no son resultados medidos ni parámetros definitivamente aprobados. Los nombres de cookies de contexto, digest/representación, campos JSON y respuesta de saturación siguen siendo propuestas. X-CSRF-Token, la separación/vinculación de contextos y la conservación de tokens vigentes durante la renovación ya están aprobados.

El token se conserva únicamente en memoria del cliente y puede reutilizarse mientras sea válido y permanezca en el contexto: no es de un solo uso. Esto permite solicitudes simultáneas, pero no garantiza impedir una repetición si un atacante obtiene token y cookie vigentes. Expiración, cambio de contexto y revocación cortan su reutilización; la idempotencia de futuras operaciones de negocio debe diseñarse aparte. CSRF no soluciona XSS.

### Origin estricto y ausencia de recuperación; detalles de lectura propuestos

- **APPROVED:** en POST y demás operaciones HTTP mutables del navegador exigir Origin presente y coincidencia exacta con un origen público permitido y configurado, sin sufijos ni comodines. Rechazar Origin ausente, null, ambiguo, múltiple, inválido o externo no permitido mediante HTTP 403 ORIGIN_INVALID, con ApiErrorBody, antes de cualquier efecto de la mutación. No utilizar Referer como sustituto ni fabricar Origin en el proxy para ocultar una solicitud inválida. Aplica también a logout sin sesión válida; no hay excepciones implícitas para Server Actions, scripts ni clientes externos.
- Rechazar cookies de autenticación duplicadas del mismo nombre o cabeceras CSRF ambiguas, sin elegir silenciosamente el primer o último valor. La representación exacta del rechazo se revisará con el catálogo de errores, sin aceptar una identidad ambigua.
- En GET csrf, validar Origin si existe. Si falta, exigir `Sec-Fetch-Site: same-origin` para el bootstrap del navegador. Rechazar los otros casos; el adaptador SSR no obtiene CSRF ni muta durante render. No utilizar esa cabecera como identidad del proxy. En GET me puede faltar Origin por navegación/SSR; si existe se valida, y ninguna lectura recibe permisos por presentar esa cabecera.
- **APPROVED:** cuando la operación exige CSRF, un token faltante, malformado, vencido, de otro contexto o invalidado devuelve HTTP 403 CSRF_INVALID con ApiErrorBody. Este rechazo ocurre antes de ejecutar efectos de negocio, incluida creación o revocación de sesión; no confirma ni deja en curso la mutación solicitada. Puede registrar un evento saneado de rechazo o control de seguridad, sin ejecutar el efecto de negocio. No revelar la causa particular ni revocar sesiones independientes. La comparación incluye contexto, vigencia y estado de sesión; no basta encontrar el digest en cualquier fila. Se conserva la excepción de logout sin sesión válida, que no requiere CSRF para una revocación inexistente.
- En operaciones que requieren sesión, proponer comprobar origen, sesión válida, CSRF y permisos en ese orden antes de los efectos; sin sesión válida se obtiene 401, no un 403 CSRF que oculte la necesidad de volver a entrar. Login permite contexto anónimo o autenticado, según la cookie validada. Logout es la excepción aprobada: ausencia confirmada de sesión válida devuelve 204, según sección 7.
- **APPROVED P2:** tras 401, descartar identidad local; no consultar csrf como anónimo mientras se presenta una cookie de sesión inválida. La limpieza explícita mediante logout confirmado se describe en sección 7 y no recupera sesión ni reintenta negocio. Cookie malformada no se oculta ni se repara automáticamente.
- Coordinar bootstrap y renovación por contexto. Si dos peticiones anónimas iniciales compiten sin cookie, puede quedar un token ligado a un contexto distinto del instalado en el navegador: no asumir continuidad del contexto para repetir una mutación. Obtener contexto de nuevo antes de una nueva acción y aplicar las comprobaciones de recuperación que siguen.
- No ampliar actividad por pedir csrf. Tras login invalidar todos los tokens del contexto previo y borrar su cookie anónima si existía; la sesión nueva requiere otro GET csrf. Logout válido revoca el contexto autenticado y sus tokens junto con la sesión.

### Renovación preventiva y ausencia de reintentos de escritura — APPROVED P8

Se conserva renovación preventiva coordinada mediante GET csrf cerca de expiresAt, token solo en memoria y sin ampliar actividad ni expulsar tokens vigentes. Duración, capacidad y margen numérico siguen provisionales. P8 y la formalización D.3 sustituyen el reenvío automático de la mutación que anteriormente se permitía tras un 403 CSRF_INVALID: obtener otra prueba no vuelve a ejecutar automáticamente una escritura.

No reintentar escrituras automáticamente ante CSRF, 429, errores 500/503, TLS/red, timeout, serialización o resultado incierto. Entregar el error al llamador; una nueva acción debe volver a cumplir controles, sin asumir continuidad de sesión/contexto. Coordinar cambios de contexto/pestañas sin exponer secretos. El rechazo CSRF previo a efectos sigue siendo una garantía de negocio, no un permiso de replay. Los reintentos internos acotados de control de versión de cuotas no equivalen a repetir una operación HTTP de negocio.

### Flujo con mecanismo aprobado y configuración provisional

1. GET `/api/v1/auth/csrf`: crear o reconocer contexto anónimo por su cookie HttpOnly, devolver token y expiración con no-store. Si hay sesión válida, emitir para su contexto autenticado.
2. POST `/api/v1/auth/login`: enviar cookie del contexto vigente, Origin, X-CSRF-Token y JSON de credenciales. Comprobar controles y límites; emitir sesión nueva solo después del commit. Invalidar el contexto usado y no convertir su token en autenticado.
3. GET `/api/v1/auth/csrf` autenticado: la cookie de sesión permite resolver el contexto nuevo; recibir otro token, sin exponer el secreto de sesión.
4. Solicitudes protegidas: enviar cookie y, para mutaciones, Origin y X-CSRF-Token; comprobar sesión, usuario, rol y alcance del recurso en backend.
5. POST `/api/v1/auth/logout`: validar origen; si hay sesión válida, exigir CSRF y confirmar revocación antes de borrar cookie y devolver 204. Si se confirma que no existe sesión válida que revocar, devolver 204 sin afirmar una revocación inexistente. Si PostgreSQL impide comprobar una cookie presentada o confirmar la revocación requerida, devolver 503.

## 7. Endpoints de autenticación

GET csrf está registrado con cierre seguro, sin emisión. Login, me y logout HTTP siguen sin registrar (404). Los servicios internos y adaptadores existen; sus métodos no son rutas operativas. La [especificación HTTP actual](autenticacion-http-adaptadores-v1.md) precisa frontera, DTO, estados, sesión/cuenta y aceptación por endpoint.

Las entradas y salidas adicionales de esta sección se etiquetan `PROPOSED` salvo decisiones explícitas APPROVED, incluidos X-CSRF-Token y la semántica de logout. AuthUser y su envoltura permanecen intactos. Las respuestas privadas no tendrán caché compartida; se concreta mediante Cache-Control: no-store. No se aceptan IDs de usuario, roles ni secretos de sesión en el cuerpo como sustitución de la identidad backend.

| Método | Ruta pública relativa | Finalidad |
| --- | --- | --- |
| GET | /api/v1/auth/csrf | Obtener contexto/token CSRF. |
| POST | /api/v1/auth/login | Iniciar sesión. |
| GET | /api/v1/auth/me | Consultar identidad. |
| POST | /api/v1/auth/logout | Revocar la sesión actual. |

### GET /api/v1/auth/csrf

Disponible para contextos anónimos y autenticados. La respuesta permitirá preparar las operaciones mutables posteriores sin exponer el secreto de sesión. Un token anónimo anterior al login no será válido como token de la sesión autenticada.

**PROPOSED:** sin cuerpo ni query de credenciales; éxito 200 con JSON de token CSRF y expiración. No requiere identidad de usuario previa, pero sí intermediario SEC-01B, IP acreditada y controles de origen/bootstrap de sección 6 más límites persistentes de emisión. Una cookie de sesión presentada selecciona la rama autenticada y debe validarse; si es inválida se rechaza sin fallback P2. Solo sin sesión presentada se crea o reconoce contexto anónimo válido, emitiendo cookie técnica nueva tras commit cuando proceda. La existencia de ese contexto no acredita autenticación ni renueva la inactividad.

Representación documental propuesta; el valor entre ángulos es un marcador ficticio, no un token utilizable:

~~~json
{
  "csrfToken": "<token-csrf-base64url-generado-por-el-servidor>",
  "expiresAt": "2026-10-30T21:10:00Z"
}
~~~

`expiresAt` es el vencimiento efectivo de ese token, no de la sesión. No se devuelve el secreto de la cookie anónima ni el de sesión. Errores según el [catálogo HTTP conciliado](autenticacion-http-adaptadores-v1.md#errores-y-límites-de-clasificación): validación general 422, 403 origen/bootstrap, 429 de cuota real, 500 interno y 503 por canal/IP/persistencia. La ausencia de cookie permite rama anónima; sesión presentada inválida no tiene esa excepción y el candidato rechaza con 401. Quedan pendientes aprobación de los campos nuevos y parámetros de emisión, sin modificar AuthUser.

### POST /api/v1/auth/login

No requiere una sesión autenticada previa; sí exige contexto CSRF y validación estricta de origen. Entrada prevista: objeto JSON con email y password, ambos campos de texto requeridos. **PROPOSED:** `Content-Type: application/json`, `Origin` público permitido, `X-CSRF-Token` y cookie del contexto anónimo o de la sesión válida presentada.

~~~http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json
Origin: https://frontend.example.invalid
X-CSRF-Token: <token-csrf-del-contexto-vigente>
Cookie: __Host-synapdesk_csrf_context=<secreto-contexto-anonimo>

{"email":"agente@example.invalid","password":"ejemplo-ficticio-no-utilizar"}
~~~

El ejemplo es ilustrativo de las propuestas de producción; dominio, secretos y cabecera son marcadores sin valor operativo. Con sesión anterior válida se presenta su cookie y un token de su contexto autenticado, en lugar de elegir arbitrariamente un contexto anónimo.

El backend deberá validar el formato del correo y normalizarlo coherentemente con el alta administrativa y su unicidad. **PROPOSED:** quitar espacios exteriores y pasar a minúsculas, coherente con el modelo Usuario ya incorporado; no eliminar puntos ni sufijos ni aplicar equivalencias de proveedores. La validación de direcciones internacionales y su equivalencia con la normalización PostgreSQL deberá verificarse antes de elegir biblioteca. Los límites HTTP de admisión siguen pendientes. La política de alta interna ya está aprobada en AUTH-07C.2B; no se redefine aquí. No normalizar, recortar ni truncar silenciosamente la contraseña.

Antes de conceder acceso deberán cumplirse origen, CSRF y límites persistentes. Se verificarán credenciales mediante Argon2id y el estado activo del usuario. Las cuentas inexistentes, contraseñas incorrectas y cuentas inactivas recibirán un error público indistinguible. **PROPOSED:** validar origen y formato del contexto, reservar cuota persistente antes de ejecutar Argon2id y usar un hash ficticio de coste equivalente cuando la cuenta no exista. También verificar con coste equivalente cuentas inactivas; igualar código, cuerpo y detalles sin prometer igualdad exacta de tiempos de red. Registrar internamente el motivo permitido sin filtrarlo en respuestas ni cabeceras.

Al tener éxito se crea una nueva sesión con una credencial opaca nueva y se emite su cookie. Si el navegador presenta una sesión anterior válida, el backend la reemplaza y revoca según la sección 5, sin revocar sesiones independientes de otros dispositivos ni confiar en la identidad indicada por el cliente. La respuesta utilizará el cuerpo aprobado de la sección 4, con AuthUser dentro de user; el estado 200 continúa como propuesta. No se expone el token portador en JSON. Se conservan CSRF y origen; el contexto CSRF previo al login no se convierte en contexto autenticado.

Errores previstos según causa: 401, 403, 422, 429, 500 y 503; véase sección 8. El reemplazo de sesión válida está aprobado y es transaccional en el servicio; P2 prohíbe recuperación automática de cookie inválida. Clasificaciones adicionales conservan propuesta. Si falla el login, no renovar actividad ni cambiar cookie de una sesión anterior válida. Un éxito invalida su contexto anterior y requiere un GET csrf autenticado antes de otra mutación.

### GET /api/v1/auth/me

La sesión se obtiene de la cookie. El backend comprueba caducidad absoluta, inactividad, revocación, usuario activo y rol vigente. No se aceptará como identidad una declaración del cliente.

**Decisión aprobada:** devolver el cuerpo de la sección 4 con AuthUser dentro de user y sus tres campos obligatorios id, email y role; rechazar con 401 cuando no exista una sesión válida. **Propuesta:** estado de respuesta exitosa 200.

**PROPOSED:** GET sin cuerpo, cookie de sesión obligatoria para obtener identidad; no exige X-CSRF-Token. Aplica la política de origen de lecturas y actividad de las secciones 5 y 6. Errores adicionales: 403 si se rechaza un Origin presente, 500 y 503. El 401 no expone si la causa es ausencia, caducidad, revocación o usuario inactivo. No emitir una sesión nueva ni borrar la cookie desde esta lectura; el cliente descarta identidad local; no inicia flujo anónimo automáticamente mientras siga presentando cookie de sesión inválida (P2).

### POST /api/v1/auth/logout

**APPROVED:** operación idempotente respecto al cierre de sesión. Siempre valida origen. Una sesión válida exige CSRF válido antes de revocar únicamente esa sesión y eliminar su cookie; las demás permanecen independientes. Si se confirma sesión inexistente/vencida/revocada, responde 204 sin declarar una revocación inexistente. P4 permite revocar una sesión vigente verificable de cuenta inactiva con los demás controles; inactividad de cuenta no autoriza un 204 ficticio ni acceso. Un fallo de PostgreSQL no se confunde con ausencia de sesión.

Respuesta prevista, sin JSON:

~~~http
HTTP/1.1 204 No Content
~~~

**PROPOSED:** enviar `{}` con Content-Type JSON y, cuando hay sesión válida, X-CSRF-Token autenticado y su cookie. Siempre aplica validación de origen. Tras commit de revocación, emitir Set-Cookie de borrado con el perfil de la sección 6, sin JSON. HTTP 204 para cierre confirmado o ausencia de sesión válida está aprobado; no ampliar logout a otras sesiones ni agregar rutas administrativas.

#### Precedencia HTTP de logout — APPROVED

1. Aplicar la validación aprobada de Origin estricto antes de cualquier cierre o borrado: Origin ausente, null, ambiguo/múltiple o no permitido devuelve HTTP 403 ORIGIN_INVALID, incluso sin sesión válida. El proxy no fabrica Origin. No revocar ni borrar cookies por ese rechazo.
2. Verificar SEC-01B y representación/cookies estrictas antes de negocio. Validación general usa 422 VALIDATION_ERROR; el cuerpo `{}` y la clasificación de cookie ambigua siguen propuestas C01/C03. No ocultar malformadas ni perfiles mezclados.
3. Si no se presenta cookie de sesión, no hay credencial que consultar o revocar: devolver 204 sin exigir CSRF ni afirmar revocación. Este caso no necesita una consulta PostgreSQL para acreditar ausencia de cookie.
4. Si se presenta cookie, comprobar su validez. Si una consulta necesaria falla, devolver 503 y no borrar la cookie ni simular éxito. Si se confirma sesión inexistente, vencida o ya revocada, devolver 204; no exigir un token CSRF de una sesión ya inválida ni registrar una nueva revocación como realizada.
5. Si existe sesión vigente revocable, incluida la excepción P4 de cuenta inactiva, comprobar CSRF: si falta o es inválido, devolver 403 sin revocar ni borrar. No utilizar la rama idempotente para eludirlo ni emitir token privilegiado nuevo para el cierre.
6. Confirmar la revocación requerida en PostgreSQL antes de responder 204 y borrar cookie. Ante fallo que impida confirmar la revocación, devolver 503, sin éxito ficticio. Un segundo logout con origen permitido y sesión ya revocada devuelve 204 aunque su antiguo contexto CSRF ya no sea válido.

El borrado de una cookie presentada y confirmada inválida se recomienda con el mismo ámbito de emisión; no equivale a una revocación. Si no se presenta cookie, no es necesario emitir un borrado. La coordinación entre pestañas y los detalles transaccionales de sección 5 siguen siendo propuestas operativas. La idempotencia no hace indistinguibles los fallos de infraestructura ni obliga a devolver 204 ante origen o CSRF rechazados sobre una sesión válida.

Errores de logout cuando correspondan: 403, 422, 500 y 503; cookie ambigua conserva clasificación pendiente. Ausencia confirmada de sesión válida devuelve 204, no 401. P4 no añade acceso: solo revocación con sesión identificada/verificada, Origin, SEC-01B y CSRF cuando corresponde; no renueva/reactiva/emite contexto privilegiado ni login ficticio. **Brecha actual:** ServicioLogout y ServicioCsrf rechazan usuario inactivo. Requieren ajuste estrecho y pruebas antes de registrar logout; ServicioConsultaSesion debe seguir rechazando cuenta inactiva. No se implementa el cambio en D.3 ni se agrega IP/cuota por analogía.

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

### Catálogo conciliado y propuestas complementarias

El [catálogo HTTP V1](autenticacion-http-adaptadores-v1.md#errores-y-límites-de-clasificación) es la referencia específica por situación y endpoint. Se preservan ApiErrorBody y 422 VALIDATION_ERROR general (incluida representación JSON rechazada por FastAPI), 403 ORIGIN_INVALID/CSRF_INVALID y 503 SERVICE_UNAVAILABLE de aplicación. Ready conserva 503 DATABASE_UNAVAILABLE. No agregar silenciosamente 400/415 o un código de cookie nuevo.

401 de me sin sesión válida y 204 de logout idempotente están aprobados. INVALID_CREDENTIALS/401, RATE_LIMITED/429, estados 200 y campos/casos adicionales siguen candidatos C01/C04; CookieAmbigua actualmente falla con 500 saneado y requiere clasificación C03. Mensajes adicionales y esperas no observadas no se aprueban por existir en CATALOGO.

Rechazo de credenciales es distinto de validación estructural. Cuenta ausente/inactiva/clave errónea recibe el mismo resultado; Argon2/BD fallidos no se convierten en 401. Error.details solo muestra información pública saneada, sin inputs, SQL, trazas, rutas, secretos o estado interno de cuenta. UUID servidor, no-store y Retry-After solo con decisión verificable. Sin retry automático de escritura, tampoco por CSRF previo a efectos.

La [precedencia por endpoint](autenticacion-http-adaptadores-v1.md#precedencia-por-endpoint) conserva Origin antes de efectos y sesión antes del CSRF exigible de logout; no impone una única prioridad artificial a lecturas, bootstrap y login. Los detalles de errores simultáneos C09 deben probarse al componer rutas futuras, sin cambiar consumo actual de cuotas. Error de PostgreSQL nunca concede acceso ni simula 204. Estos requisitos no registran handlers.

## 9. Autorización y roles

Los roles iniciales son admin y agent. FastAPI comprobará usuario activo y rol vigente en las operaciones protegidas. El proxy, el DTO y la ocultación de controles del frontend no sustituyen esta verificación.

El [modelo de dominio](../arquitectura/modelo-dominio.md) describe responsabilidades generales de cada rol; no constituye una matriz completa de permisos por recurso. Esa matriz y el tratamiento operativo de cambios de rol o desactivación quedan pendientes. No se conceden permisos adicionales ni se crean endpoints administrativos en este contrato.

**Actualización acotada AUTH-07C.2B:** el [contrato de creación administrativa](creacion-administrativa-usuarios-v1.md) formaliza P1–P15 ya aprobadas: admin activo con sesión vigente puede crear admin/agent activos y exige user_created atómico con actor SynapDesk. Sustituye el estado pendiente solo para esas altas internas y su política de credenciales/entrega externa. No aprueba el resto de la matriz, cambios posteriores de rol/estado, retención o rutas HTTP administrativas.

### Matriz para decisión del equipo — PROPOSAL_PENDING_TEAM_REVIEW

Toda celda expresa una propuesta, no un permiso ya concedido ni una obligación de implementación. La política general es denegar por defecto operaciones sin autorización definida. El alcance deberá comprobarse también en listados, recomendaciones y conteos, sin confiar en el filtro que envíe el cliente; esta regla no aprueba ninguna celda de la matriz.

| Recurso/operación | admin propuesto | agent propuesto | Decisión que debe confirmar el Product Owner |
| --- | --- | --- | --- |
| Usuarios | Consultar y administrar altas, roles y desactivaciones mediante flujos administrativos. | Identidad propia por me; sin administración ni listado general por defecto. | Acceso al directorio mínimo para asignaciones, administración de la propia cuenta y protección del último admin activo. No habilitar registro público. |
| Tickets | Consultar y gestionar todos, incluida asignación. | Crear; consultar los creados por él o asignados a él; modificar los asignados dentro de transiciones autorizadas. | Alcance de lectura del equipo, reasignación, cierre y edición de tickets creados pero no asignados. No aprobar borrado físico. |
| Recomendaciones | Consultar, generar y revisar dentro del ámbito de tickets administrables. | Consultar, generar y revisar en tickets sobre los que tenga el permiso correspondiente. | Separar lectura, generación y revisión; decidir quién puede modificar una revisión previa. |
| Sesiones | me y logout individual de la sesión propia. | me y logout individual de la sesión propia. | Mantener fuera de este incremento administración o revocación de sesiones ajenas; no se añaden endpoints. |
| Métricas | Resumen global del ámbito autorizado. | Resumen limitado a sus tickets accesibles, si se aprueba habilitarlo. | Aprobar acceso de agent y coherencia de conteos/paginación con los tickets visibles; el mock actual no concede acceso global. |

La comprobación de usuario activo y rol vigente es aprobada; la invalidación masiva de sesiones por cambios administrativos no está aprobada. Usuario desactivado no obtiene acceso; P4 exceptúa exclusivamente revocación verificada de su sesión mediante logout, sin identidad activa. Reevaluar rol por petición; retención o revocación administrativa adicional requiere decisión. Este documento no modifica los contratos de recursos ni sus endpoints existentes/propuestos.

## 10. Límites de intentos y auditoría

**Decisiones aprobadas:** la limitación de intentos será persistente y no desaparecerá al reiniciar el proceso. Se auditarán eventos de autenticación sin registrar contraseñas, tokens portadores ni pruebas CSRF.

### Contraseñas — PROPOSED

Argon2id es una decisión aprobada. Se propone iniciar la calibración con **64 MiB de memoria, tres iteraciones y paralelismo uno** (`m=65536 KiB`, `t=3`, `p=1`), sin afirmar resultados de benchmark ni aprobarlos para producción. Medir latencia, memoria y concurrencia en el entorno objetivo, incluidas credenciales inválidas y hash ficticio. Elegir una biblioteca mantenida, sin fijar aquí una dependencia ni modificar requirements.

Estado de estos valores y del presupuesto de concurrencia: `PROVISIONAL_CONFIGURATION` / `PENDING_MEASUREMENT`. No hay resultados de rendimiento medidos o certificados.

Proponer sal aleatoria individual administrada por la biblioteca y almacenamiento del hash codificado con sus parámetros. Tras un login válido, rehash si la política aprobada cambió, evitando sobrescribir un cambio concurrente de contraseña. Para cuentas inexistentes usar el hash ficticio citado en login; no generar una contraseña predeterminada de usuario.

Limitar trabajo criptográfico concurrente y validar tamaños antes de Argon2id; las cuotas persistentes por sí solas no acotan la memoria de todos los workers. El presupuesto de concurrencia, límites de entrada y tiempos admisibles requieren medición y aprobación. No suprimir validaciones ni reducir el coste automáticamente ante sobrecarga. La guía [OWASP de contraseñas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) distingue este hash lento del digest de secretos aleatorios; los valores locales anteriores son una propuesta no medida.

### Limitación persistente — PROPOSED

Las categorías por cuenta, IP verificada y bootstrap, sus ventanas y umbrales se mantienen como `PROVISIONAL_CONFIGURATION` / `PENDING_MEASUREMENT`. No se fijan cantidades adicionales.

| Clave de control | Qué se propone contar | Precaución |
| --- | --- | --- |
| Cuenta normalizada | Intentos fallidos y reservas en curso del mismo identificador, exista o no la cuenta. | Generar la misma clase de clave para cualquier correo válido; no limitar solo cuentas encontradas ni bloquearlas permanentemente. |
| IP verificada | Intentos de login aceptados para evaluación y rechazos que consuman capacidad, con independencia de la cuenta. | No confiar en X-Forwarded-For enviado por el navegador; contemplar usuarios detrás de NAT. |
| Bootstrap CSRF | Emisión de contextos y tokens, combinando origen de cliente verificado y contexto cuando exista. | No permitir eludir la cuota quitando la cookie; reservar antes de insertar para evitar crecimiento ilimitado por concurrencia. |

Proponer claves HMAC de datos normalizados con secreto exclusivo de servidor para no persistir correos/IP directamente en el limitador. La administración/rotación de esa clave y la minimización de IP en auditoría quedan pendientes; un digest simple de un correo no se considera anonimización. No se añade un proveedor externo: PostgreSQL mantiene el estado entre procesos y reinicios.

Reservar y actualizar capacidad atómicamente con claves/ventanas únicas; liberar o consolidar la reserva según resultado, con recuperación de reservas abandonadas tras caída. Un éxito no debe borrar globalmente límites de origen ni permitir que dos workers superen un máximo por leer simultáneamente. Proponer bloqueos temporales y 429 con Retry-After derivado del estado, sin mensajes distintos por existencia de cuenta. Si el almacenamiento del limitador falla, 503; no aceptar intentos sin control persistente.

**PENDING_DESIGN:** umbrales y ventanas por cada clave, duración y recuperación de bloqueos/reservas, mitigación del bloqueo malicioso de cuentas, capacidad máxima, política de purga y configuración de IP/proxy. No hay cantidades adicionales aprobadas ni estimaciones presentadas como resultados. Probar carreras, reinicios, NAT y saturación antes de aceptar valores.

### Auditoría — componentes implementados; operación general PROPOSED

El [catálogo existente](../../backend/app/seguridad/auditoria.py) y esquema 0006 incluyen los eventos internos; admin_bootstrap y user_created tienen aprobación específica en AUTH-07C. El catálogo general recomendado cubre login exitoso/fallido, logout, reemplazo/revocación, caducidad, CSRF/origen, límites y fallos de controles, sin aprobar eventos nuevos por esta enumeración. No se inventan códigos HTTP a partir del catálogo de eventos. Evitar eventos repetidos sin límite por cada intento de reutilizar la misma sesión; la deduplicación y su retención necesitan aprobación.

Campos conceptuales: fecha UTC del servidor, tipo y resultado, requestId, usuario conocido y referencia interna de sesión cuando corresponda, motivo técnico acotado y metadatos de origen minimizados. No registrar contraseña, cuerpo íntegro de login, cookies, tokens CSRF, digest completo de credenciales ni cabeceras sin filtrar. Los motivos privados de rechazo no se envían al cliente.

Proponer escritura de los eventos de éxito y revocación en la misma transacción de sesión, sin conceder éxito si falla su registro. Los rechazos se auditan en una transacción independiente para que un rollback de credenciales no los borre. Si PostgreSQL completo está caído, las operaciones que necesitan comprobar o revocar sesión responden 503 y solo registran un aviso operativo saneado con requestId, sin afirmar persistencia del evento ausente. Se conserva la excepción aprobada de logout sin cookie, que puede responder 204 sin consulta ni revocación; no registrar una revocación ficticia para ese caso.

**PENDING_DESIGN:** acceso a eventos, retención, purga, tratamiento de referencias a usuarios/sesiones eliminados y política de datos personales. No se fija una duración arbitraria ni se habilita un endpoint de auditoría. La evidencia de las pruebas posteriores deberá demostrar que contraseñas y secretos no aparecen tampoco en errores o logs de fallos.

Eventos, trazabilidad y minimización de información sensible se conservan como requisitos; catálogo detallado y operación siguen propuestos. La retención es configuración provisional pendiente de aprobación, sin duración asignada ni medición que la certifique.

## 11. Criterios de aceptación

### Calidad documental

- Separar decisiones aprobadas, propuestas, pendientes y funcionalidades no implementadas.
- Mantener enlaces relativos válidos y ejemplos JSON coherentes con las convenciones comunes.
- Conservar los cuatro campos de ApiErrorBody dentro de error.
- Reutilizar en login y /me el AuthUser aprobado con id, email y role obligatorios dentro de user, sin modificar User.
- No presentar ejemplos incompletos de CSRF o cookies como solicitudes listas para ejecutar.
- Resolver los detalles operativos y de configuración pendientes antes de implementar; no confundir aprobación del mecanismo CSRF con parámetros certificados o autorización para programarlo.

### Comportamiento verificable en la implementación posterior

- Una cuenta activa con credenciales válidas inicia sesión; /me devuelve su identidad y rol vigente.
- La recarga conserva la sesión mientras siga válida.
- Las tres causas de rechazo de credenciales producen una respuesta pública indistinguible.
- El backend rechaza sesiones ausentes, caducadas o revocadas; se comprueban ambos límites de tiempo.
- Logout válido devuelve 204 y el token revocado no vuelve a autenticar, aunque se conserve una copia.
- Las sesiones simultáneas están permitidas; logout individual no revoca las otras.
- Un login exitoso reemplaza y revoca la sesión anterior válida presentada por el navegador, emite una credencial opaca nueva e impide reutilizar la anterior; las sesiones independientes de otros dispositivos permanecen válidas según su propia vigencia.
- Login y logout sobre sesión válida rechazan CSRF inválido; logout siempre valida origen y, sin sesión válida que revocar, responde 204 conforme a la precedencia aprobada. Un fallo PostgreSQL que impide determinar/revocar una sesión presentada produce 503.
- El contexto CSRF anónimo previo al login no se acepta como contexto autenticado.
- El control de intentos sobrevive al reinicio y produce 429 al alcanzar los límites que se acuerden.
- Usuarios inactivos o roles sin permiso no obtienen acceso protegido.
- El navegador utiliza /api/v1/* del mismo origen y el backend sigue autorizando cada operación.
- No se exponen contraseñas, hashes ni secretos de sesión/contexto en JSON, errores o auditoría; PostgreSQL no almacena sus credenciales portadoras en texto plano. El token CSRF solo se entrega por el campo propuesto para ese fin y se mantiene fuera de errores y logs.

### Verificaciones del diseño propuesto, tras su aprobación

- Contextos anónimos duran como máximo 15 minutos; los tokens propuestos duran como máximo 10, recortados por su contexto/sesión. Probar igualdad en el límite, nueva emisión y contexto ya revocado.
- Hasta el máximo provisional de ocho tokens vigentes por contexto, sin excederlo bajo emisión concurrente ni expulsar tokens aún vigentes para renovar. Verificar saturación, vencimientos y dos bootstraps en competencia.
- Renovación preventiva coordinada antes de expiresAt, sin extender inactividad ni invalidar tokens vigentes en uso. Probar ausencia de reintento automático de escritura también tras 403 CSRF_INVALID, cambio de sesión, 429 o resultados desconocidos (P8).
- Un token de otra sesión o anónimo anterior al login no autoriza mutaciones sobre una sesión válida; logout sin sesión válida aplica su excepción aprobada sin revocación. Origin estricto rechaza ausencia/null/ambigüedad/origen no permitido también en ese logout. GET csrf sin Origin conserva solo la regla específica de lectura, sin habilitar bypass de mutaciones.
- Login concurrente con el mismo contexto no deja dos sesiones autorizadas; un fallo no revoca la sesión anterior válida. Rollback o caída de PostgreSQL no emiten éxito ni cookie nueva.
- Logout compite con peticiones protegidas sin resucitar sesión ni actividad; distinguir efectos confirmados antes de revocar de autorizaciones posteriores. Probar también pérdida de respuesta y coordinación entre pestañas.
- Cookies de ambos perfiles respetan ámbito/atributos, borrado y máximo absoluto; una cookie conservada no supera la vigencia del servidor. No mezclar perfiles local/producción.
- SSR reenvía solo cookies autorizadas, conserva identidad por petición y no cachea datos entre usuarios. Los Set-Cookie de login/logout/bootstrap llegan al navegador como cabeceras separadas, también al producir errores.
- Las mutaciones de V1 usan fetch cliente y proxy de mismo origen, sin Server Actions/Server Functions de negocio. El destino se obtiene del futuro BACKEND_INTERNAL_URL exclusivo de servidor y nunca de entrada del cliente. HTTP 503 se maneja sin asumir un único error.code y sin repetir automáticamente una mutación.
- El limitador persiste tras reinicios, maneja reservas concurrentes y no permite eludir bootstrap borrando cookies. La auditoría de éxitos se confirma con la sesión; una caída no concede acceso ni registra secretos.
- La futura matriz aprobada se aplica en detalle, listados y métricas; los mocks no constituyen evidencia de permisos backend.

Estos criterios describen verificaciones funcionales futuras; su definición no constituye evidencia de pruebas superadas.

## 12. Dependencias y decisiones pendientes

P1–P10, arquitectura B, servicio SEC-01B, AuthUser y políticas administrativas ya aprobadas no se vuelven a someter a aprobación. La [matriz C01–C09](auth07d3-compatibilidad-y-plan-integracion.md#4-decisiones-adicionales-que-siguen-pendientes) sustituye las listas antiguas de pendientes en lo que corresponde a HTTP:

- C01: 200 csrf/login/me, campos csrfToken/expiresAt y representación {} de logout.
- C02/C03: nombres/mapeo explícito de cookies y clasificación pública de CookieAmbigua; P1/P2 y atributos estrictos ya formalizados.
- C04: códigos/mensajes adicionales de credenciales/cuotas y casos no aprobados expresamente.
- C05/C06: valores productivos, admisión/saturación, Argon2/capacidad y presupuestos por operación/tramo medidos; no cuotas de ensayo ni cifras inventadas.
- C07: operación de credenciales/CA, variable privada Next, orígenes concretos y rotación; el mecanismo ya aprobado no acredita su despliegue.
- C08: evidencia técnica de IP/TLS/red en Render, no sustituible por aprobación documental.
- C09: detalles interoperables de lecturas/errores simultáneos/correlación; sin nueva cabecera o DTO implícito.

Permisos por recurso no aprobados, retención/acceso/purga de auditoría y limpieza operativa siguen sus decisiones previas, sin nuevas cantidades. El alta inicial/posterior interna ya tiene contratos AUTH-07C; HTTP administrativo requiere contrato separado. El [plan de doce incrementos](auth07d3-compatibilidad-y-plan-integracion.md#8-secuencia-exacta-de-incrementos) mantiene cierres y evidencia independiente. La excepción P4 está aprobada pero pendiente de implementación/pruebas; no se resuelve cambiando únicamente un error a 204.

La aprobación documental no equivale a implementación, migración aplicada o despliegue validado.
