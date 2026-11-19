# Contrato HTTP V1 de autenticación — AUTH-07D.3

**Formalizado en el alcance aprobado P1–P10, arquitectura B y SEC-01B.**
Actualizado el 13-11-2026. Sustituye el candidato D.1 como especificación actual;
los detalles marcados PROPUESTA conservan su aprobación pendiente. Código
adaptador existente no equivale a ruta habilitada o infraestructura acreditada.

Referencias: [autenticación V1](autenticacion-v1.md),
[frontend/backend y errores](frontend-backend.md),
[SEC-01B](comunicacion-interna-segura-v1.md),
[responsabilidades PR30/PR32](integracion-http-pr30-pr32-v1.md) y
[compatibilidad, decisiones C01–C09, aceptación y plan](auth07d3-compatibilidad-y-plan-integracion.md).
Las P1–P10 del último documento están aprobadas y no requieren nueva aprobación.

## Estado real y alcance

Navegador → Next.js público → FastAPI privado → PostgreSQL: arquitectura
aprobada, Render todavía no desplegado/acreditado. La identidad de servicio,
la IP y la sesión del usuario son distintas; Origin y CSRF tampoco las sustituyen.

[AdaptadorAuth](../../backend/app/api/adaptadores_auth.py) existe, sin router,
registro, importación o instancia desde la [fábrica](../../backend/app/aplicacion.py).
GET csrf está registrado con cierre seguro: bootstrap inválido produce 403;
con Origin/bootstrap y canal válidos sigue 503 sin token/contexto/cookie, incluso
si un test sustituye la dependencia IP. Login, me y logout no están registrados
(404). No hay alta administrativa HTTP ni registro público.

## Reglas comunes formalizadas

- AuthUser mantiene exactamente id (UUID texto), email normalizado y role
  admin/agent dentro de user. No name, contraseña, hash, cookie o token de sesión.
- Toda respuesta de autenticación, incluidos errores y 204, lleva
  Cache-Control: no-store. JSON usa Content-Type: application/json; 204 no lleva
  cuerpo. No streaming de éxito ni commit en teardown o tareas de fondo.
- ApiErrorBody conserva error.code, error.message, error.details y
  error.requestId. Reutilizar DTO/manejadores; validación general 422
  VALIDATION_ERROR, distinta del rechazo de credenciales. No reflejar inputs,
  SQL, trazas, secretos o detalles de estado de cuenta.
- requestId de backend es UUID generado/reutilizado en Request por id_peticion,
  propagado a los coordinadores/auditoría que lo admiten. No adoptar UUID del
  navegador ni X-Request-ID. Next preserva el identificador de error backend;
  sus errores propios tienen UUID de Next, sin afirmar que hubo auditoría backend.
  No existe cabecera de correlación común implementada/aprobada; no agregar una
  ni añadir requestId a AuthUser o al DTO exitoso sin acuerdo adicional.
- Origin exacto obligatorio en POST, antes de efectos, también logout sin cookie.
  Ausente/null/múltiple/ambiguo/no permitido: 403 ORIGIN_INVALID. No sustituirlo
  por Referer, Host, Sec-Fetch-Site o un Origin inventado en SSR.
- SEC-01B obligatorio también en SSR: una Authorization propia del servidor,
  política del entorno vigente y TLS verificable. Error de canal: 503
  SERVICE_UNAVAILABLE. No utilizar bearer como identidad de usuario o IP.
- Cookies estrictas P1 y sin recuperación automática P2. Una sesión presentada
  selecciona su rama; no usar contexto anónimo coexistente para saltar el rechazo.
- Ocho horas absolutas y treinta minutos de inactividad. GET me y GET csrf no
  renuevan actividad, sesión ni credenciales. Ninguna lectura borra sesión para
  convertir una solicitud inválida en anónima.
- P8: no reintentos automáticos de escrituras. Renovar CSRF preventivamente no
  reenvía la mutación. Timeout/corte/error tras commit no demuestra rollback.

Los DTO existentes son [SolicitudLogin, SolicitudLogout, RespuestaCsrf,
RespuestaUsuario y AuthUser](../../backend/app/api/esquemas_auth.py).
Las representaciones y estados que siguen etiquetados PROPUESTA no se aprueban
por existir un DTO o por haber sido ensayados.

## GET /api/v1/auth/csrf

| Elemento | Contrato y estado |
| --- | --- |
| Propósito / actor | Obtener prueba Synchronizer Token para anónimo o sesión activa válida. No concede autenticación ni crea sesión de usuario. |
| Intermediario / IP | SEC-01B y procedencia IP acreditada obligatorios. Ausencia de cualquiera mantiene cierre, sin token/cookie. |
| Origin | Regla implementada/candidata C09: validar si existe; si falta exigir una única Sec-Fetch-Site: same-origin. Otros casos 403 ORIGIN_INVALID. No usar esta condición de lectura en POST. |
| Cookies / contexto | Sin sesión ni contexto: crear anónimo después de admisión. Con contexto anónimo: verificarlo, no reemplazar uno inválido silenciosamente. Con sesión presentada: verificarla y resolver exclusivamente su contexto autenticado. |
| CSRF de entrada / request DTO | No requiere X-CSRF-Token para obtener la prueba. Sin cuerpo ni query de credenciales (representación candidata). No aceptar usuario/rol/IP desde JSON. |
| Response DTO | PROPUESTA C01: 200 RespuestaCsrf {csrfToken, expiresAt}; expiresAt UTC efectivo del token, no de la sesión. Es el único secreto destinado al JSON de esta operación. |
| Set-Cookie | Contexto anónimo nuevo: cookie técnica HttpOnly solo tras commit, Max-Age restante. Existente: no prolongar. Autenticado: sin cookie técnica nueva ni renovación de sesión. Cada Set-Cookie separado. |
| Transacciones | ServicioBootstrapCsrf para anónimo: reservas IP/global/contexto y emisión confirmadas conforme a SEC-01A. Autenticado: ServicioCsrf.emitir_token dentro de transaccion_seguridad, con máximo existente sin expulsar tokens vigentes. |
| Estado ausente/inválido | Sesión ausente es admisible como anónimo; sesión presentada inexistente/vencida/revocada/inactiva se rechaza, sin fallback. Contexto inválido/vencido se rechaza sin reemplazo. Clasificación pública de esos contextos se cierra en C03/C04; candidato conserva fallo saneado. |
| Errores | 403 Origin/bootstrap; 503 canal/IP/BD; cuota real 429 RATE_LIMITED y Retry-After verificable (código adicional C04); 500 INTERNAL_ERROR saneado para no clasificados. Sesión presentada inválida: candidato 401 AUTHENTICATION_REQUIRED, sin distinguir causas. No inventar 429 para LIMITE_TOKENS. |
| Aceptación | A01–A02, A05–A11, A14/A17. Nada se emite antes de commit; P1/P2/P7/P9/P10 y saturación/admisión autenticada resueltas antes de habilitar. |

La política productiva de bootstrap y la admisión/emisión autenticada deben estar
aprobadas y configuradas. Perfil de ensayo no se activa en producción. La ruta
actual conserva su rechazo final, incluso si se resolviera solo la fuente IP.

## POST /api/v1/auth/login

| Elemento | Contrato y estado |
| --- | --- |
| Propósito / actor | Autenticar credenciales de cuenta activa. Anónimo puede solicitar login con contexto anónimo válido; usuario con sesión válida puede reemplazar esa sesión. |
| Intermediario / Origin / IP | SEC-01B, Origin exacto obligatorio e IP acreditada para cuotas persistentes; controles independientes. |
| Cookie / contexto | Contexto anónimo previo o sesión presentada con contexto autenticado vigente. Una cookie de sesión inválida no se convierte en ausencia aunque coexista contexto anónimo. |
| Token CSRF | Una X-CSRF-Token canónica, vigente y ligada a la rama elegida. Ausente/duplicada/malformada/ajena/vencida: 403 CSRF_INVALID cuando el control es aplicable, antes de negocio. |
| Request DTO | SolicitudLogin: email y password texto requerido, extra=forbid. Normalizar correo mediante normalizar_cuenta, sintaxis mínima compartida. Contraseña UTF-8 no vacía intacta, SecretStr, sin recorte/truncado. Content-Type JSON y límites de admisión exactos pendientes C01/C05. |
| Response DTO | Envoltura aprobada {user:{id,email,role}}. Estado 200 PROPUESTA C01. Sin credencial de sesión, contraseña, hash ni name en JSON. |
| Set-Cookie | Sesión opaca nueva después del commit; borrar contexto anónimo presentado después del éxito. Max-Age limitado a expiración confirmada. No emitir/borrar por rechazo de credenciales, Origin o CSRF. |
| Persistencia | ServicioLogin.validar_contexto y autenticar. Reservas persistentes antes de Argon2 fuera de locks prolongados; revalidar cuenta, hash, sesión/contexto y cuotas en confirmación. Sesión/contexto/auditoría de éxito en una transacción. Reemplazar/revocar solo sesión válida presentada; otras sesiones no cambian. |
| Sesión previa / cuenta | Ausente requiere contexto anónimo; vencida/revocada/inválida se rechaza sin recuperación. Cuenta destino inactiva, ausente o contraseña errónea: mismo rechazo público, sin enumeración. La excepción P4 no aplica a login. |
| Errores | 422 VALIDATION_ERROR general; 403 ORIGIN_INVALID/CSRF_INVALID; 401 INVALID_CREDENTIALS uniforme PROPUESTA C04; sesión previa inválida candidato 401 AUTHENTICATION_REQUIRED; 429 RATE_LIMITED con decisión real; 500/503 saneados. Argon2 o BD fallidos no son credenciales erróneas. |
| Aceptación | A01–A06/A08–A14/A17/A19; commit visible antes de cookie, rollback por auditoría/constraint, reemplazo y errores uniformes, sin retry ante resultado incierto. |

No registrar login antes de bootstrap/IP/cuotas/contrato/canal completos. No crear
usuarios al autenticar ni sesión automática desde alta administrativa.

## GET /api/v1/auth/me

| Elemento | Contrato y estado |
| --- | --- |
| Propósito / actor | Consultar identidad de sesión activa válida, admin o agent. Anónimo no obtiene identidad. |
| Intermediario / Origin | SEC-01B también para SSR. Regla candidata C09: Origin puede faltar en lectura/SSR; si existe se valida. Nunca fabricar uno. |
| IP / CSRF / request DTO | Sin IP ni cuota de login por analogía; sin X-CSRF-Token o cuerpo para lectura, conforme al diseño candidato por endpoint. |
| Cookie / identidad | Una cookie de sesión estricta; ServicioConsultaSesion revalida persistencia, expiraciones, revocación, cuenta activa y rol vigente. AuthUser antiguo no autoriza. |
| Response DTO | {user:{id,email,role}} aprobado; 200 PROPUESTA C01. Sin Set-Cookie, rotación ni borrado. |
| Transacción / actividad | Transacción propia de lectura. P3: no registrar_actividad, no modificar los treinta minutos ni las ocho horas. Polling/SSR no mantienen viva la sesión. |
| Sesión / cuenta inválida | Ausente/inexistente/vencida/revocada/inactiva: 401 aprobado, candidato AUTHENTICATION_REQUIRED; mismo error sin causa particular. No recuperar como anónimo ni emitir contexto. |
| Otros errores | 403 ORIGIN_INVALID si se presenta uno inválido; 500/503 saneados. Validación general adicional, si existe, usa 422 común. |
| Aceptación | A01–A08/A11/A15/A19; dos usuarios SSR aislados; fechas iguales antes/después de consulta, rechazo al límite, sin cookies ni caché compartida. |

## POST /api/v1/auth/logout

| Elemento | Contrato y estado |
| --- | --- |
| Propósito / actor | Revocar únicamente sesión propia verificable. Idempotencia 204 si no hay sesión válida que revocar; no afirmar revocación ficticia. P4 permite solo cierre de cuenta inactiva con controles restantes. |
| Intermediario / Origin | SEC-01B y Origin exacto obligatorios incluso sin cookie; ningún bypass SSR. |
| IP / request DTO | No añadir IP o cuota de login por analogía. SolicitudLogout {} con extra=forbid es PROPUESTA C01; no acepta identidad/rol. |
| Cookies / CSRF | Cookie estricta antes de identificar sesión. Si está vigente y revocable, token único/canónico ligado a contexto obligatorio. No elegir 204 solo porque la cuenta está inactiva o falta CSRF. |
| Response DTO | 204 aprobado, sin JSON; no-store también aquí. |
| Transacción / Set-Cookie | Revocación, invalidación de contexto/tokens y evento real atómicos. Borrar solo cookie de sesión presentada tras retorno confirmado; mismo perfil/ámbito. Sin cookie no hace falta borrado. No borrar contexto anónimo como recuperación silenciosa. |
| Sin sesión | Sin cookie: 204 después de Origin/servicio/representación, sin consulta para acreditar ausencia de cookie. Cookie canónica con inexistencia/vencimiento/revocación confirmados: 204, aun sin CSRF; sin nueva auditoría de revocación. Cookie malformada/ambigua no entra en esa rama. |
| Sesión válida / cuenta activa | CSRF válido → revocación/commit/204/borrado. CSRF inválido → 403 sin revocar/borrar. |
| Cuenta inactiva | P4: sesión identificada, vigente y verificable puede revocarse con Origin/servicio/CSRF y locks/revalidación; no usuario activo ni token nuevo. Falta token válido → 403, sin revocación. Implementada internamente y verificada por regresiones PostgreSQL/HTTP en testing aislado; consulta general y emisión siguen rechazadas. No habilita staging. |
| Errores | 422 de validación conforme representación que se apruebe; 403 Origin/CSRF; 500/503 saneados. BD necesaria fallida nunca 204. Cookie ambigua C03 pendiente; no implementar excepción con un simple cambio de error a 204. |
| Aceptación | A06/A08–A09/A11/A14/A16–A19; verificar caso inactivo, carreras, auditoría, fallo de commit y sesión de otro dispositivo intacta. |

P4 no modifica ServicioConsultaSesion: cuenta inactiva no obtiene recursos,
permisos administrativos, login, contexto privilegiado nuevo o renovación. Debe
conservarse verificación criptográfica/persistente y expiraciones de la sesión.
La [matriz de compatibilidad](auth07d3-compatibilidad-y-plan-integracion.md#3-matriz-de-compatibilidad-con-el-backend)
describe el ajuste estrecho y las pruebas que todavía no existen.

## Precedencia por endpoint

La matriz expresa la composición que deberá respetar el backend, conservando
controles independientes y sin atribuir al DTO de FastAPI una prioridad que aún
no se probó en rutas. Detalles de errores simultáneos/lecturas C09 se ratifican
antes de registro; Origin previo a efectos y precedencia idempotente de logout
ya estaban aprobados. UUID/no-store acompañan todos los rechazos.

| Endpoint | Orden de frontera y admisión | Persistencia / cierre |
| --- | --- | --- |
| csrf | id → Origin o condición bootstrap → SEC-01B → cookies estrictas/representación → IP acreditada | Seleccionar rama presentada. Anónimo: reserva durable de admisión → validación/reserva del contexto existente, si hay → transacción de emisión/commit → token/cookie. Autenticado: sesión/contexto y máximo de tokens existentes; admisión HTTP pendiente. Sin consumir cuota o emitir si falla frontera. |
| login | id → Origin → SEC-01B → cookies estrictas → DTO JSON normalizado → IP acreditada → prueba de contexto/token | Validación persistente preliminar → reserva de cuota con nueva validación CSRF en su transacción → Argon2 fuera de locks → confirmación con revalidación → commit → DTO/cookie. No revelar si existe cuenta. |
| me | id → validar Origin si existe → SEC-01B → cookies estrictas | Sesión/cuenta activa/rol/tiempos en PostgreSQL → fin de transacción → DTO, sin actividad/CSRF/IP/cookies de respuesta. |
| logout | id → Origin → SEC-01B → cookies estrictas y representación acordada | Sin cookie: 204. Con cookie canónica: identificar estado persistente; inexistente/vencida/revocada confirmado → 204. Si revocable (incluido P4): CSRF → revalidar tras locks → revocación/contexto/auditoría → commit → 204/borrado. Token inválido no desplaza la comprobación idempotente. |

No crear efectos de negocio antes de los controles. Reservas y auditorías de
rechazo de coordinadores conservan sus reglas actuales: P7 no cambia qué
intentos consumen cuota. Probar Origin+JSON inválidos, servicio+cookie inválidos,
sesión inválida+CSRF ausente y BD caída+aparente ausencia; no convertir la
precedencia en oráculo de cuentas o estado de sesión. Cuerpo lento/excesivo se
limita antes de criptografía; sus cifras y clasificación no se inventan aquí.

En SEC-01A, la admisión anónima consume primero intentos globales y por IP;
sin cookie de contexto reserva además creación global/IP. Esas reservas se
confirman antes de validar un contexto anónimo existente y sobreviven a fallos
posteriores. La cuota por contexto se confirma aparte antes de emitir. Un
contexto inválido nunca permite reemplazo, pero no deshace las reservas ya
consumidas. No trasladar su validación antes de la admisión durable sin una
decisión de cambio; P7 conserva esa semántica. El candidato autenticado no
hereda esas reservas por el solo hecho de llamar ServicioCsrf.emitir_token.

## Cookies y tratamiento de credenciales obsoletas

Perfil explícito validado contra APP_ENV y origen permitido mediante
[preparar_perfil](../../backend/app/api/cookies_auth.py); configuración inválida
rechaza. Nombres candidatos C02, no defaults aprobados:

| Perfil | Sesión propuesta | Contexto anónimo propuesto |
| --- | --- | --- |
| Local development/testing | synapdesk_session_dev | synapdesk_csrf_context_dev |
| Production HTTPS | __Host-synapdesk_session | __Host-synapdesk_csrf_context |

Atributos formalizados: HttpOnly, SameSite=Lax, Path=/, sin Domain; Secure en
producción y todo HTTPS. __Host- exige esos atributos y no se usa en HTTP local.
HTTP de cookie local explícita no permite transportar bearer SEC-01B sin TLS.
Max-Age usa tiempo restante confirmado, sin ampliar ocho horas ni inactividad.
Eliminación: mismo nombre/Path/seguridad, Max-Age=0, Domain ausente; Expires si
se usa debe ser coherente. Set-Cookie múltiples siempre separados.

P1 se aplica sobre evidencia original antes de filtrar: duplicados idénticos o
distintos, cookie permitida sin '=', vacía, comillas, espacios/codificación
inválida, perfiles mezclados y cabeceras ambiguas no se reparan ni desaparecen.
No elegir primer/último valor. Nombres desconocidos no se convierten en
credenciales; filtrar cookies ajenas solo después de descartar ambigüedad de
las reservadas. No decodificar porcentajes para reparar secretos.

P2: ante 401, descartar identidad local no equivale a autorización para tratar
esa cookie como anónima. GET me/csrf no eliminan ni recuperan sesión. El usuario
puede solicitar logout explícito con Origin/servicio: si BD confirma que no hay
sesión válida, 204 y borrado de la cookie presentada; después una acción nueva
puede iniciar bootstrap sin ella. No es reintento automático de login/negocio.
Si la cookie es malformada, no transformarla en ausencia ni borrarla desde una
lectura; un procedimiento explícito de eliminación local de datos del sitio no
revoca sesiones ni constituye recuperación backend. No añadir un endpoint de
limpieza. Coordinar pestañas para evitar borrado tardío de login posterior.

## Errores y límites de clasificación

| Situación | HTTP / code | Estado y manejo |
| --- | --- | --- |
| JSON, campos/tipos/extra inválidos | 422 VALIDATION_ERROR | Contrato general vigente; details solo field/message declarados, sin input. No nuevo 400/415 automático. |
| Origin rechazado | 403 ORIGIN_INVALID | Aprobado, mensaje seguro; antes de efectos. |
| CSRF exigible rechazado | 403 CSRF_INVALID | Aprobado, sin causa particular; no autoriza replay automático de escritura. |
| Me sin sesión válida | 401; candidato AUTHENTICATION_REQUIRED | 401 aprobado, código reutilizado existente; sin enumerar causa. |
| Credenciales login rechazadas | 401 INVALID_CREDENTIALS | Candidato C04; mismo mensaje para ausente/inactiva/clave. |
| CookieAmbigua | Actual 500 INTERNAL_ERROR | Rechazo seguro, clasificación definitiva C03 pendiente. Propuesta: 422 VALIDATION_ERROR existente; no aprobada. |
| Cuota observada | 429 RATE_LIMITED, Retry-After | Código/casos adicionales C04; espera positiva derivada de reloj/fin reales, no inventar intervalo de saturación. |
| Canal SEC-01B, IP o BD necesarios no disponibles | 503 SERVICE_UNAVAILABLE | Catálogo general aprobado, sin distinguir secreto/SQL/TLS/IP interna. |
| Proxy/TLS/timeout/redirección | 503 SERVICE_UNAVAILABLE | Error saneado de Next; requestId propio cuando no hay respuesta backend utilizable. Sin retry. |
| Fallo interno/serialización | 500 INTERNAL_ERROR | Existente saneado; no cuerpo parcial ni cookies de éxito. Mensajes exactos no expresamente aprobados siguen candidatos. |

GET ready conserva 503 DATABASE_UNAVAILABLE y su contrato separado. 403 FORBIDDEN
solo donde exista una política de autorización de recurso; no inventar permiso
por bearer. ApiErrorBody permite details público; adaptadores auth actuales lo
limitan a lista field/message o null. No-store siempre; Retry-After se conserva
desde backend cuando es válido. No repetir automáticamente una escritura al
terminar la espera. Success DTO no recibe un campo nuevo de correlación.

Los [presupuestos/cuotas](auth07d3-compatibilidad-y-plan-integracion.md#5-cuotas-y-presupuestos-inventario-sin-cifras-productivas-nuevas)
separan valores observados, medición y decisiones. Si falla la lectura de reloj
para cookie después del commit, no enviar éxito/cookie aunque la sesión ya pueda
existir. Conciliar resultado incierto; no recuperar secreto de digest, reintentar
login o revocar automáticamente.

## Condiciones para habilitar

Contrato formalizado no es autorización de registro. Resolver C01–C09 aplicables,
corregir PR30 y canal específico PR32, probar TLS/SEC/DTO/cookies/errores, configurar
cuotas y composición por worker. Csrf/login requieren además IP acreditada y
políticas productivas; me/logout no heredan IP, pero necesitan su canal/contrato
completos y logout la implementación P4. Navegador y Render conservan pruebas
pendientes. La [secuencia por incremento](auth07d3-compatibilidad-y-plan-integracion.md#8-secuencia-exacta-de-incrementos)
no se inicia automáticamente. Sin frontend, ML, rutas, migraciones, despliegue,
commits, push o PR en D.3.
