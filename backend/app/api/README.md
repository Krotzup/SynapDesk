# Fundamentos HTTP de autenticación — AUTH-07A

## Candidatos AUTH-07D.1

[adaptadores_auth.py](adaptadores_auth.py) compone cookies, Origin, SEC-01B,
pruebas tipadas y servicios internos. No tiene router ni se instancia desde la
fábrica. Login/me/logout conservan 404 y CSRF real conserva rechazo seguro.
La dependencia IP no tiene implementación HTTP ni opción de sustitución productiva.

El [contrato candidato D.1](../../../docs/contratos/autenticacion-http-adaptadores-v1.md)
conserva aprobaciones anteriores y enumera contradicciones/decisiones antes de
activar tráfico. INVALID_CREDENTIALS y SolicitudLogout son candidatos ya descritos
en autenticación V1; no se presentan como aprobados. El requestId generado por
servidor se propaga a auditoría de login/logout mediante parámetros internos
opcionales, sin cambiar la semántica de sesiones o aceptar el identificador cliente.

Las respuestas se construyen tras resultados confirmados, con no-store y sin
credenciales en JSON. Las pruebas PostgreSQL de D.1 verifican visibilidad antes
de Set-Cookie y fallos diferidos de commit. No acreditan Node o Render.
Las secciones siguientes documentan la preparación AUTH-07A original.

AUTH-07A prepara utilidades sin emitir cookies desde endpoints ni crear seeds. Reutiliza [AUTH-06](../seguridad/README.md), sus modelos y sus transacciones. Salud y disponibilidad conservan su comportamiento. La adaptación parcial AUTH-07B1 se describe al final.

## Esquemas y errores

[esquemas_auth.py](esquemas_auth.py) define AuthUser exclusivamente con `id`, `email` y `role`, su envoltura `user`, solicitud de login, respuesta CSRF propuesta y la envoltura de errores. `ApiErrorBody` corresponde al objeto dentro de `error`, igual que el tipo frontend. Solo se admiten detalles de validación saneados o null en los errores construidos aquí. Los DTO no serializan modelos ORM.

El correo de login comparte la normalización de Usuario y una comprobación sintáctica mínima (un separador @, partes no vacías y ausencia de espacios internos); no introduce reglas de proveedores ni certifica validación internacional completa. La política definitiva de direcciones especiales y límites de entrada requiere coordinación antes de AUTH-07B. La contraseña debe ser texto no vacío UTF-8 y se conserva intacta como SecretStr, sin restricciones nuevas de longitud. El token CSRF permanece oculto en repr; su serialización JSON expone exclusivamente la prueba prevista para el cliente. No registrar ese JSON.

[errores_auth.py](errores_auth.py) registra manejadores en la fábrica existente. Traduce sesión ausente/vencida/revocada a `401 AUTHENTICATION_REQUIRED` en consultas de identidad, Origin a `403 ORIGIN_INVALID`, y persistencia/conflictos o IP no verificable a `503 SERVICE_UNAVAILABLE`. No proporciona aún la política de credenciales de login. Argon2 y configuración inválida son errores internos `500 INTERNAL_ERROR`, nunca `INVALID_CREDENTIALS`. `LIMITE_TOKENS` tampoco se convierte automáticamente en 429 sin una política/espera verificable.

CSRF inválido/vencido/contexto inválido solo produce `403 CSRF_INVALID` mediante `RechazoAntesDeEfectos`: el adaptador debe acreditar que no comenzó la mutación. Un error CSRF sin esa garantía produce error interno, sin habilitar el reintento contractual. No envolver fallos posteriores a efectos ni resultados desconocidos. La futura orquestación debe preservar esta distinción.

La validación FastAPI devuelve `422 VALIDATION_ERROR`, los cuatro campos contractuales y una lista de `{field, message}`. Solo se seleccionan nombres declarados en el esquema/ruta, con mensajes fijos en español; nunca input, contexto, mensajes de validadores, índices arbitrarios ni nombres extra del cliente. JSON inválido usa la misma envoltura con lista vacía. **Discrepancia documental:** el contrato general acordó este código el 03-11-2026, mientras la tabla de autenticación aún marca su catálogo de validación pendiente. Se aplica el acuerdo general más reciente; no se modifican contratos.

[respuestas_auth.py](respuestas_auth.py) genera UUID por petición en servidor, sin adoptar X-Request-ID. Las respuestas preparadas aquí llevan `Cache-Control: no-store`; no se agrega caché ni cookies a salud/disponibilidad. `respuesta_limite` exige una decisión negativa con tiempos conscientes de zona y espera positiva calculada por AUTH-06; nunca fabrica Retry-After.

## Cookies: perfiles propuestos, explícitos

[cookies_auth.py](cookies_auth.py) exige entorno, origen público y nombres distintos de sesión/contexto. No hay nombres ni duraciones por defecto. Usar `preparar_perfil` con la configuración para exigir pertenencia al Origin permitido. Ejemplos **PROPOSED** del contrato: `__Host-synapdesk_session` y `__Host-synapdesk_csrf_context` para HTTPS; `synapdesk_session_dev` y `synapdesk_csrf_context_dev` para HTTP local. No quedan aprobados definitivamente por estas utilidades.

Los perfiles usan HttpOnly, SameSite=Lax, Path=/ y ausencia de Domain. Todo origen HTTPS implica Secure, también en desarrollo. HTTP solo se admite en development/testing para hosts locales explícitos; staging/production exigen HTTPS. El nombre __Host-/__Secure- no puede usarse con HTTP. La emisión recibe credencial canónica de AUTH-06 y vencimiento confirmado, calcula Max-Age como el tiempo restante redondeado hacia abajo, sin fijar nuevas duraciones. El borrado conserva ámbito y atributos con Max-Age=0.

La lectura inspecciona todas las cabeceras Cookie originales, rechaza duplicados incluso idénticos y representaciones ambiguas. Nunca elige silenciosamente el primer/último valor de Request.cookies. La respuesta tampoco puede emitir/borrar dos veces el mismo nombre; diferentes Set-Cookie permanecen separados. `CookieAmbigua` no tiene todavía un código público específico aprobado: falla cerrada como error saneado y su clasificación queda para AUTH-07B.

## Transacciones e infraestructura

[dependencias_auth.py](dependencias_auth.py) obtiene una Session SQLAlchemy por petición desde el motor del ciclo de vida existente. `SesionHttp` usa `scope="function"` para cerrar y revertir trabajo pendiente antes de enviar la respuesta. Nunca hace commit automático. No compartir sesiones entre peticiones, tareas o streaming.

La futura operación debe abrir explícitamente [transaccion_seguridad](../seguridad/transacciones.py), componer efectos y auditoría dentro de ella, y construir credenciales/cookies de éxito **después** de salir correctamente del bloque. El commit puede fallar; no capturar el fallo para reutilizar resultados provisionales. Las pruebas PostgreSQL demuestran commit visible desde otra conexión antes de emitir cookie, rollback, fallo real de una restricción diferida al commit y sesiones/conexiones concurrentes distintas.

## Origin y frontera de confianza

El adaptador `exigir_origin` pasa todas las ocurrencias originales al servicio AUTH-06. No combina Origin ni lo infiere de Host, Referer o forwarded headers. El ejemplo local sigue siendo `AUTH_ORIGENES_PERMITIDOS=["http://localhost:3000"]`. No modifica CORS ni las reglas de lecturas/bootstrap, que se conectarán en AUTH-07B.

`obtener_token_csrf` solo exige una cabecera X-CSRF-Token canónica y única, sin acreditar contexto o vigencia: el futuro endpoint debe llamar al servicio CSRF con la vinculación correcta. No sustituye su validación persistente.

**IP HTTP pendiente:** `obtener_ip_verificada` rechaza siempre mientras no exista un adaptador autenticado o aislado aprobado. No acepta X-Forwarded-For, X-Real-IP, Forwarded ni X-SynapDesk-Client-IP; tampoco confía en loopback o Request.client. AUTH-06 conserva su primitiva independiente, sin activar un bypass. La ausencia de procedencia verificable no autoriza omitir la cuota IP.

El comando local documentado utiliza `uvicorn ... --no-proxy-headers`: Uvicorn no debe reescribir el peer desde cabeceras del cliente. Esa opción no autentica Next.js ni resuelve despliegues de varios saltos; la app nunca considera confiable automáticamente el peer aunque el servidor se inicie con otras opciones. Se deben aprobar redes, aislamiento/autenticidad y metadatos reconstruidos antes de habilitar IP en AUTH-07B.

Siguen pendientes recuperación ante cookie vencida, actividad exacta de sesión, perfil operativo definitivo de cookies, integración HTTP de cuotas/bootstrap, saturación CSRF, calibración y políticas administrativas. Los flujos completos AUTH-07B/C, proxy Next.js y SSR no están implementados en esta rama; no hay cambios de roles por SEC-01B.

## AUTH-07B1: ruta registrada, emisión bloqueada

[csrf_auth.py](csrf_auth.py) registra únicamente `GET /api/v1/auth/csrf`. Valida todas las ocurrencias de Origin con AUTH-06. Si Origin falta, exige una única cabecera `Sec-Fetch-Site: same-origin`, según la condición de bootstrap del contrato; esa cabecera no acredita al proxy ni la IP. Un rechazo devuelve `403 ORIGIN_INVALID`. Sin orígenes configurados conserva el error interno de configuración de AUTH-07A.

Con bootstrap válido devuelve `503 SERVICE_UNAVAILABLE`, con ApiErrorBody, requestId de servidor y no-store. No emite tokens, contextos ni cookies, no lee sesiones y no inicia transacciones. La ausencia de IP verificable mantiene el cierre existente. Incluso si se reemplazase ese adaptador, la ruta conserva el rechazo mientras falte el control persistente de emisión aprobado.

`ServicioLimites.reservar` exige cuenta e IP verificada; no limita bootstrap sin cuenta por sí solo. SEC-01A incorpora el coordinador interno [ServicioBootstrapCsrf](../seguridad/bootstrap_csrf.py), con cuotas separadas por IP, globales y por contexto, todavía sin conectar a HTTP. No se inventa una cuenta compartida ni se omite cuota IP. Su política explícita no certifica umbrales productivos; siguen pendientes su integración HTTP, las esperas/saturación y la procedencia del intermediario.

La emisión exitosa con `ServicioCsrf`, su respuesta `csrfToken`/`expiresAt`, cookies y recuperación de contextos no está conectada. AUTH-06 conserva sus valores configurables provisionales: token 600 segundos, contexto anónimo 900 segundos y máximo de ocho tokens vigentes, sin expulsión. No son duraciones certificadas ni aprobación nueva. Los nombres/perfil operativo de cookies y la recuperación de una cookie de sesión vencida siguen pendientes. En esta fase toda cookie presentada, incluida una antigua o malformada, permanece sin modificar y nunca habilita emisión ni renueva actividad.

Las pruebas de AUTH-07B.1 acreditan controles HTTP y ausencia de efectos, también con PostgreSQL real; no acreditan una emisión HTTP exitosa. SEC-01A añadió posteriormente el coordinador persistente interno, todavía sin conectar al handler. El inventario de rutas de AUTH-07A se amplía solo con esta ruta, conservando las comprobaciones de salud/disponibilidad. No se implementan login, me o logout.

## SEC-01B: identidad de intermediario, IP HTTP todavía cerrada

[ServicioIntermediario](../seguridad/intermediario.py) verifica un bearer de servicio
exclusivo del entorno, independiente de cookies, usuarios y AUTH_HMAC_CLAVE.
[obtener_intermediario](dependencias_auth.py) y `IntermediarioHttp` permiten exigirlo
en rutas futuras. No son identidad de usuario ni autorización de recursos.

La configuración explícita `AUTH_INTERMEDIARIO` contiene habilitación, entorno,
transporte `tls_directo`, política IP `no_acreditada` y una o dos credenciales con
identificador, digest oculto y vencimiento consciente de zona. Sin configuración,
deshabilitada o de otro entorno, el control rechaza con el 503 existente; salud
no depende de ella. Los digests usan dominio y entorno separados de sesiones/HMAC.
Cada credencial requiere vencimiento; retirarla de la lista la revoca en los
procesos que reciban la configuración actualizada. No hay recarga distribuida.

Next.js debe descartar Authorization del navegador y construir un único
`Authorization: Bearer <secreto>` en servidor. El secreto representa exactamente
32 bytes CSPRNG en base64url canónico sin padding. El formato no acredita entropía.
FastAPI compara todos los digests mediante `hmac.compare_digest`, sin revelar
cuál coincidió. No registrar cabeceras, configuración serializada con entradas
crudas ni excepciones de validación mediante `errors(include_input=True)`.

El listener debe terminar TLS directamente y arrancar con `--no-proxy-headers`,
sin middleware que reescriba `scope['scheme']`. La dependencia exige `https` y
rechaza Forwarded, X-Real-IP y cualquier X-Forwarded-*. Esto impide usar esas
cabeceras para aparentar TLS, incluso con la reescritura habitual de Uvicorn.
El dato ASGI depende del servidor: no demuestra por sí solo el canal ni que el
cliente haya verificado el certificado. Next.js debe verificar CA y hostname.
No se habilita HTTP interno local ni un modo permisivo de desarrollo.

`obtener_ip_verificada` verifica primero servicio y después rechaza siempre por
IP no acreditada. No consume ninguna cabecera IP, Request.client ni UUID cliente.
El único adaptador controlado está en fixtures; no hay adaptador HTTP local ni
Render habilitable por configuración. La ruta CSRF conserva Origin antes del
control del canal y su rechazo final incondicional; no inicia transacciones ni
emite cookies. SEC-01A ya implementó cuotas internas, pero su integración HTTP
de emisión no forma parte de SEC-01B.

El [borrador de comunicación interna](../../../docs/contratos/comunicacion-interna-segura-v1.md)
describe el comportamiento implementado y los gates pendientes. Las pruebas de
[TLS real](../../pruebas/integracion/test_intermediario_tls.py) requieren OpenSSL
(incluido con Git for Windows): generan y eliminan certificado/clave efímeros,
usan conexiones HTTPS verificadas y rechazan CA/hostname incorrectos. Las pruebas
[PostgreSQL](../../pruebas/integracion/test_intermediario_postgresql.py) registran
rutas exclusivamente de ensayo con IP del fixture; no agregan rutas a la app.
