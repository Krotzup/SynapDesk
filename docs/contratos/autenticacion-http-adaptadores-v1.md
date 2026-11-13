# Contrato HTTP interoperable candidato — AUTH-07D.1

**Estado: DRAFT / REVIEW_REQUIRED para activación.** Este documento prepara la
especificación y los adaptadores autorizados en SYNAPDESK-AUTH07D1-HTTP-CONTRACT-AND-ADAPTERS.
No cambia unilateralmente [autenticación V1](autenticacion-v1.md),
[frontend–backend](frontend-backend.md) ni [SEC-01B](comunicacion-interna-segura-v1.md).
Las propuestas no se vuelven APPROVED por disponer de código o pruebas locales.

## Estados y frontera

| Categoría | Estado |
| --- | --- |
| A. Decisiones aprobadas | Sesión opaca PostgreSQL, AuthUser id/email/role dentro de user; Synchronizer Token, Origin estricto, CSRF en mutaciones, logout idempotente; mismo origen, no-store y secretos solo servidor. |
| B. Existente | Servicios internos, cuotas, auditoría y adaptadores AUTH-07A; GET csrf registrado pero cerrado. D.1 añade candidatos sin router ni registro. |
| C. Propuestas pendientes | 200 de éxito, INVALID_CREDENTIALS/401 y otros detalles del catálogo, nombres/perfiles de cookies, cuerpo {} de logout, recuperación de cookies, saturación y presupuestos de recursos. |
| D. Solo infraestructura | Procedencia IP verificable, caminos de ingreso, TLS privado/CA/hostname, aislamiento Render y operación de credenciales. No acreditados por pruebas locales. |

Objetivo autorizado del encargo: navegador → Next.js público → FastAPI privado
→ PostgreSQL, arquitectura B prevista en Render. No se presenta como despliegue.
El bearer SEC-01B acredita servicio, la sesión acredita usuario y una fuente
verificada debe acreditar IP; son pruebas distintas.

[AdaptadorAuth](../../backend/app/api/adaptadores_auth.py) no se importa ni se
instancia en la fábrica de FastAPI, no tiene APIRouter ni flags de activación.
Sus métodos se prueban directamente con objetos Request; no son endpoints
operativos. El GET csrf real conserva su cierre final incluso si se sustituye
su dependencia de IP en una prueba.

## Reglas comunes y orden

1. Generar/reutilizar id_peticion del servidor; ignorar X-Request-ID del cliente.
2. Origin: obligatorio y exacto en POST; en GET me se valida si existe; GET csrf
   utiliza la condición específica de bootstrap descrita abajo.
3. Verificar intermediario SEC-01B: una Authorization de servicio, TLS directo,
   configuración/entorno/vencimiento y ausencia de cabeceras de proxy prohibidas.
4. Extraer cookies originales por perfil explícito; rechazar duplicadas,
   malformadas o credenciales de los perfiles propuestos incompatibles.
5. En csrf/login exigir obtener_ip_verificada. Permanece cerrado en aplicación;
   no se puede pasar una IP arbitraria por argumento del adaptador.
6. Construir la prueba CSRF con cookie anónima o con sesión presentada; una
   sesión presentada selecciona siempre su rama, sin recuperación silenciosa.
7. Usar los coordinadores existentes para controles persistentes y efectos.
8. Construir respuesta y cookies únicamente después de resultados confirmados.

La validación de cuerpo FastAPI usa DTO extra=forbid y errores comunes. En el
futuro registro, Origin debe componerse como dependencia previa a efectos y
debe conciliarse la precedencia ante cuerpo inválido/origen inválido simultáneos.
D.1 no publica una nueva prioridad global de todos los errores de FastAPI.

No se adoptan rol, UUID, AuthUser, IP, bearer de usuario o booleanos del JSON
como autorización. No hay campo name en AuthUser. No se aceptará UsuarioPreparado
desde HTTP ni se incorpora alta administrativa en este incremento.

## Especificación por endpoint

Los estados de éxito 200 y detalles nuevos mantienen PROPOSED salvo lo indicado.
Las cabeceras comunes son Content-Type application/json en JSON y
Cache-Control: no-store en toda respuesta, incluidos errores y 204.
Set-Cookie permanece separado por cookie. No se añade requestId a AuthUser
ni al éxito de login/me: el cuerpo mantiene el contrato aprobado.

### GET /api/v1/auth/csrf

| Aspecto | Contrato candidato y límite actual |
| --- | --- |
| Método/ruta | GET /api/v1/auth/csrf, ya registrado con rechazo seguro; no se sustituye su handler. |
| Origin | Si existe, coincidencia exacta; si falta, Sec-Fetch-Site debe tener una única ocurrencia same-origin. No acredita servicio/IP y no se usa esta excepción en POST. |
| Intermediario/IP | SEC-01B obligatorio y fuente IP acreditada. Sin ella: 503 SERVICE_UNAVAILABLE, sin token/contexto/cookie. |
| Cookies | Perfil de sesión/contexto. Sesión presentada → contexto autenticado; sin sesión → reconocer/crear anónimo. No recuperar automáticamente sesiones inválidas. |
| CSRF/cuerpo | No exige X-CSRF-Token para obtener prueba; sin JSON ni query de credenciales. |
| Identidad | Anónimo no autentica; sesión válida se revalida en PostgreSQL. |
| Éxito propuesto | 200, RespuestaCsrf {csrfToken, expiresAt}, fecha UTC efectiva del token. Solo ese token puede aparecer en JSON. |
| Cookies posteriores | Nuevo anónimo: emitir cookie técnica HttpOnly tras commit. Anónimo existente: conservar vencimiento. Autenticado: no emitir cookie de contexto ni renovar sesión. |
| Transacciones/cuotas | Anónimo utiliza ServicioBootstrapCsrf y sus reservas persistentes IP/global/contexto. Autenticado reutiliza ServicioCsrf.emitir_token en transaccion_seguridad y su máximo existente de tokens. No expulsar tokens vigentes ni extender actividad. |
| Rechazos | Origin 403 ORIGIN_INVALID; canal/IP/BD 503 SERVICE_UNAVAILABLE; cuota observada 429 RATE_LIMITED/Retry-After verificable; fallos no clasificados 500 INTERNAL_ERROR. Saturación por LIMITE_TOKENS no se convierte en 429 sin espera/política aprobada. |
| Pendiente específico | Recuperación de sesión/contexto inválidos y traducción de esos casos; admisión de emisión autenticada y saturación antes de activarla. El candidato conserva el rechazo del servicio (incluido 401 para sesión presentada inválida), sin convertirlo en contexto anónimo; no se publica ese comportamiento mientras no se concilie. |

La ruta real no emite aunque la procedencia fuese sustituida por un fixture.
La rama autenticada del candidato utiliza exclusivamente la primitiva existente;
la política HTTP de admisión/saturación debe cerrarse antes de habilitarla.
No se crea otro protocolo CSRF.

### POST /api/v1/auth/login

| Aspecto | Contrato candidato |
| --- | --- |
| Método/ruta | POST /api/v1/auth/login, NO REGISTRADO. |
| Origin | Obligatorio; ausente/null/múltiple/ambiguo/no permitido → 403 ORIGIN_INVALID antes de efectos. Sin sustituto Referer o Sec-Fetch-Site. |
| Intermediario/IP | Bearer de servidor y TLS SEC-01B; IP acreditada obligatoria para las cuotas. |
| Cookies | Contexto anónimo previo, o sesión presentada cuyo contexto autenticado se debe validar. Nunca convertir cookie inválida en ausencia. |
| CSRF | Una X-CSRF-Token canónica; ligada a la rama elegida, no vencida/ajena/invalidada. |
| JSON | SolicitudLogin: email y password requeridos; normalización compartida del correo, contraseña UTF-8 intacta/SecretStr; extra=forbid. Content-Type JSON según propuesta vigente. |
| Identidad | No requiere usuario previo; identidad resultante solo del ServicioLogin y estado/rol vigentes. |
| Éxito propuesto | 200 {user:{id,email,role}}; sin name, contraseña, hash o credencial de sesión. |
| Set-Cookie | Credencial nueva confirmada; borrar cookie anónima presentada tras éxito. La sesión anterior válida se reemplaza/revoca en el servicio, no en el adaptador. |
| Transacciones | validar_contexto y autenticar de ServicioLogin; reserva de cuota antes de Argon2id fuera de locks; confirmación atómica de sesión/contexto/auditoría. |
| Rechazos | 422 VALIDATION_ERROR general; 403 ORIGIN_INVALID/CSRF_INVALID; 401 INVALID_CREDENTIALS candidato ya documentado, uniforme para cuenta ausente/inactiva/clave incorrecta; 429 RATE_LIMITED; 500 INTERNAL_ERROR; 503 SERVICE_UNAVAILABLE. Sesión presentada inválida conserva rechazo del servicio, sin recuperación implícita. |

El código INVALID_CREDENTIALS se añade al catálogo como candidato previamente
propuesto en autenticación V1, sin aprobación nueva ni ruta que lo publique.
Un fallo de Argon2 o infraestructura no se interpreta como credenciales erróneas.
No hay rehash ni recuperación nuevos.

### GET /api/v1/auth/me

| Aspecto | Contrato candidato |
| --- | --- |
| Método/ruta | GET /api/v1/auth/me, NO REGISTRADO. |
| Origin | Puede faltar en SSR/navegación; si existe se valida. No se fabrica. |
| Intermediario/IP | SEC-01B también en SSR. No requiere inventar IP o consumir cuota de login para consulta. |
| Cookie/identidad | Sesión canónica de perfil; ServicioConsultaSesion revalida sesión, cuenta activa y rol vigente. |
| CSRF/JSON | Sin token CSRF o cuerpo para lectura. |
| Éxito propuesto | 200 {user:{id,email,role}}. |
| Cookies/transacción | Ningún Set-Cookie ni borrado desde lectura; transacción propia del servicio, sin renovar actividad. |
| Rechazos | 401 AUTHENTICATION_REQUIRED para ausencia/vencimiento/revocación/usuario inactivo; 403 ORIGIN_INVALID si se presenta origen inválido; 500/503 saneados. |

### POST /api/v1/auth/logout

| Aspecto | Contrato candidato |
| --- | --- |
| Método/ruta | POST /api/v1/auth/logout, NO REGISTRADO. |
| Origin | Obligatorio aun sin cookie; rechazo 403 antes de cerrar o borrar. |
| Intermediario/IP | SEC-01B obligatorio; no se añade cuota o IP por analogía con login. |
| JSON | SolicitudLogout candidato {} con extra=forbid; representación exacta pendiente, sin identidad/rol. |
| Cookie/identidad | Sesión presentada se verifica mediante ServicioLogout. Sin cookie → 204 sin consulta de ausencia a BD. |
| CSRF | Para sesión válida, token único/canónico/persistente obligatorio. Ausente/duplicado/malformado se representa como token rechazado, nunca como permiso. |
| Precedencia aprobada | Sesión inexistente/vencida/revocada confirmada → 204 aun sin CSRF; sesión válida con CSRF inválido → 403 sin revocación/borrado; falla BD necesaria → 503. |
| Éxito | 204 aprobado, sin cuerpo; revocación y auditoría confirmadas antes del borrado. |
| Set-Cookie | Borrar cookie de sesión presentada tras retorno confirmado, mismo perfil/ámbito. Sin cookie no hace falta borrado. No borrar contexto anónimo como recuperación implícita. |
| Rechazos | 422 de cuerpo según propuesta; 403 Origin/CSRF; 500/503. Cookie ambigua y estado de cuenta inactiva requieren clasificación final; el candidato conserva rechazo existente y no lo convierte en cierre ficticio. |

No se crea otra sesión, no se revocan dispositivos independientes y no se
relaja la precedencia idempotente por un token ausente.

## Cookies y resultados confirmados

El perfil es explícito, se valida contra APP_ENV y un origen permitido mediante
preparar_perfil; sin nombres por defecto. Se mantienen nombres propuestos:

| Perfil candidato | Sesión | Contexto anónimo |
| --- | --- | --- |
| Local development/testing | synapdesk_session_dev | synapdesk_csrf_context_dev |
| Production HTTPS | __Host-synapdesk_session | __Host-synapdesk_csrf_context |

HttpOnly, SameSite=Lax, Path=/ y ausencia de Domain; Secure en todo HTTPS.
HTTP solo es perfil de cookie local propuesto, no excepción TLS para bearer.
Max-Age es tiempo restante del resultado confirmado, sin extender límite
absoluto o inactividad. Borrado usa mismo nombre, Path y seguridad, Max-Age=0.

extraer_cookies reutiliza leer_cookie de AUTH-07A, conserva cabeceras originales
y rechaza los otros nombres reservados de perfiles propuestos. CookieAmbigua
sigue fallando cerrada mediante 500 saneado; su estado HTTP definitivo es una
decisión pendiente, no una recuperación automática.

Los constructores privados de respuesta se ejecutan después de los coordinadores.
La lectura corta del reloj para Max-Age también es posterior al commit; si falla,
no se entrega cookie/éxito aunque la sesión ya pueda estar confirmada. Esto es un
resultado incierto que requiere conciliación; no se reintenta ni revoca
automáticamente. Los fallos de serialización/emisión no publican respuestas
parciales. Las primitivas AUTH-07A no son por sí solas comprobantes de commit.

## Error, requestId y correlación

Todos los errores usan {error:{code,message,details,requestId}}. Reutilizar
ApiErrorBody y los manejadores existentes; no exponer input/contexto Pydantic,
SQL, trazas, contraseñas, hashes o cabeceras. La validación general es
422 VALIDATION_ERROR por acuerdo general de 03-11-2026; credenciales rechazadas
son otro resultado y usan la propuesta específica 401, no 422.

id_peticion genera UUID del servidor, se mantiene durante la petición y se
propaga al parámetro interno opcional request_id de validar_contexto/autenticar
y ServicioLogout.cerrar. Llamadores anteriores conservan generación interna;
no cambia autorización/transacciones/semántica de sesiones. No se acepta un
requestId del cuerpo o X-Request-ID. Los éxitos conservan sus DTO sin campos nuevos.

No-store siempre. Retry-After solo a partir de una decisión negativa con reloj
y vencimiento verificables; no inventar espera de saturación. Ready conserva
503 DATABASE_UNAVAILABLE; las operaciones de aplicación usan SERVICE_UNAVAILABLE.
El cliente trata 503 por estado sin retry de mutación. RechazoAntesDeEfectos
solo envuelve controles CSRF de coordinadores conocidos que revierten efectos de
negocio al fallar; no se usa sobre errores de commit/infraestructura incierta.

## Contradicciones y decisiones para conciliación

| Tema | Evidencia | Tratamiento D.1 |
| --- | --- | --- |
| Arquitectura | V1 describe Vercel → Render; SEC-01B y encargo prevén B en Render | Documentar objetivo B, no reescribir aprobación histórica ni afirmar despliegue. |
| Canal local | PR30/PR32 admiten HTTP local; SEC-01B exige TLS incluso local con bearer | Preparar integración TLS; no bypass por localhost. |
| Estado funcional antiguo | Contratos dicen no implementado; ahora hay servicios y candidatos | Separar operación interna de rutas públicas aún no registradas. |
| Validación 400/422 | Tabla antigua de auth frente a acuerdo general posterior | Reutilizar 422 VALIDATION_ERROR general; sin nuevo 400/415 inventado. |
| Recuperación de cookie inválida | Documento propone anónimo tras 401; servicio actual rechaza sesión presentada inválida | No implementar recuperación; conciliar antes de abrir csrf/login. |
| Cookie ambigua | Rechazo obligatorio, clasificación HTTP aún pendiente | Rechazo saneado existente, no elegir credencial. |
| Logout/cuenta inactiva | Servicio distingue usuario inactivo de sesión revocada/vencida | No reinterpretar unilateralmente como 204; resolver clasificación antes de registro. |
| Éxitos/catálogo | 200 y INVALID_CREDENTIALS siguen propuestos | Código candidato no expuesto; aprobar antes de registrar. |
| CSRF autenticado | Primitiva tiene máximo de tokens; cuota HTTP/saturación requieren acuerdo | Preservar controles, no inventar 429/espera ni habilitar emisión. |
| SEC-01B/IP | Bearer implementado; IP no acreditada | Mantener dependencia cerrada; no cabecera IP aceptada. |

## Condiciones de registro y aceptación

Aprobar/conciliar las filas anteriores, perfiles y contratos operativos; validar
Node/FastAPI TLS e IP; fijar presupuestos/admisión y configuración por worker.
Después, en otra tarea, registrar únicamente handlers completos con sus
dependencias y pruebas; no basta importar el candidato.

Pruebas locales: extracción/cabeceras/errores/DTO, servicio TLS real existente,
cuotas y commits PostgreSQL; cookies solo tras visibilidad en otra conexión,
restricciones diferidas sin Set-Cookie y recorrido interno de prueba.
Pruebas pendientes: Node real con transportes de PR30/PR32, navegador y Render.
Ver [acuerdo de integración para Valentina y América](integracion-http-pr30-pr32-v1.md).

Sin endpoints administrativos, frontend/ML, cambios de migración, commits,
push, PR, infraestructura o inicio de AUTH-07D.2.
