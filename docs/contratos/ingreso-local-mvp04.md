# Procedencia y autenticación HTTP local — MVP04

El encargo MVP04 autoriza una frontera local verificable y la composición de
CSRF/login/me con los servicios existentes, exclusivamente en infraestructura
aislada. Este documento registra esa implementación de ensayo; no ratifica
C01–C09 productivos ni acredita Render. Complementa [SEC-01B](comunicacion-interna-segura-v1.md)
y [HTTP V1](autenticacion-http-adaptadores-v1.md), sin reemplazar sus controles.

## Productor, transporte y consumidor

El productor es el servidor custom Node que aloja Next y observa el socket
original antes de invocar el framework. Descarta la posibilidad de que el
navegador elija el dato: cabeceras IP o de evidencia presentadas por el cliente
son rechazadas. El código confiable del ingreso establece el valor; poseer la
credencial SEC-01B no permite construir esa evidencia por sí solo.

Una clave aleatoria independiente firma HMAC-SHA-256 del dominio
synapdesk:ingreso-local:v1, separador NUL y payload base64url. El payload contiene
v/aud/ip/ts/nonce/method/path/controls. Solo se acepta versión 1, audiencia exacta,
representación canónica, tiempo válido, nonce único y controles coincidentes.
La firma no incluye el cuerpo; TLS protege su tránsito. Cookie y demás valores
sensibles solo participan en una huella, no se duplican en el payload.

El salto hacia FastAPI es HTTPS con CA/hostname verificados y SEC-01B. El listener
termina TLS directamente con proxy_headers=False. El consumidor verifica firma,
vínculo, servicio, transporte, peer y antirreplay antes de construir IpVerificada
con las primitivas existentes. No se aceptan X-Forwarded-For/Forwarded/X-Real-IP
ni cabeceras de IP arbitrarias. Loopback solo delimita el ensayo; no autentica.

Un ingreso comprometido podría mentir sobre lo que observó: ese productor y sus
claves son parte explícita de la frontera. No se presenta la firma como prueba
contra el propio emisor. Los nonces son locales y acotados por ejecución, con
clave/audiencia nuevas en cada arranque del runner; no hay garantía distribuida
de replay ni acreditación de despliegue.

## Perfil operacional explícito y decisiones acotadas

| Tema | Ensayo MVP04 | Estado fuera del ensayo |
| --- | --- | --- |
| Entorno/destino | testing, política ensayo, base propia aleatoria 5433, identidad/head verificados | Rechaza otros entornos/bases. Fábrica productiva cerrada |
| C01 | DTO existentes: 200 csrf/login/me; csrfToken/expiresAt; envoltura user con AuthUser mínimo | No se ratifican por inferencia otros cuerpos/estados públicos |
| C02 | Cookies locales explícitas synapdesk_session_dev/synapdesk_csrf_context_dev | Mapeo productivo sigue pendiente; atributos existentes preservados |
| C03/C04 | Rechazos saneados vigentes, CookieAmbigua 500, credenciales incorrectas 401 y cuotas con espera real | Sin nuevos códigos públicos ni clasificación definitiva de cookies |
| C05 | Política persistente existente de ensayo, capacidad Argon2 1, cuerpo local acotado y máximo de tokens existente | Sin valores productivos nuevos ni aprobación de mediciones |
| C06 | Presupuesto del proxy observado y límites propios del ensayo | No constituye presupuesto de producción aprobado |
| C07 | SEC-01B privado y clave de evidencia/audiencia efímeras, no NEXT_PUBLIC ni persistencia | Nombre actual de variable de servicio continúa provisional |
| C08 | Fuente local observada, evidencia autenticada y pruebas de rechazo | Render sigue PENDIENTE_DE_EVIDENCIA |
| C09 | Origin antes de JSON en login; /me sin Origin permitido; sesión/contexto según rama presentada | Otros detalles interoperables pendientes conservan su estado |
| P4 | MVP04/MVP09 sin logout; MVP10 conecta el logout existente sólo en testing. Sin administración | Mantiene el cierre de la fábrica habitual y los contratos existentes |

Las cuentas de ensayo son filas reales con Argon2id y rol persistido, preparadas
solo en la base exclusiva. No constituyen identidades productivas ni sesiones
fingidas: las sesiones se obtienen exclusivamente con contraseña/CSRF por login
HTTP. /me reconsulta sesión/cuenta/rol y no renueva inactividad. Duraciones,
cuotas persistentes y auditoría conservan sus servicios existentes.

## Registro y recomposición MVP09

Solo la [aplicación local explícita](../../backend/herramientas/ingreso_local/aplicacion.py)
registra CSRF/login/me, crear/listar/detalle/cambio de estado y los conteos de tickets
requeridos por la UI actual. Reutiliza los adaptadores/DTO de main y su paginación
extrema corregida en #39; el parser HTTP no añade el límite antiguo de nueve dígitos.
[app.aplicacion](../../backend/app/aplicacion.py)
no importa el paquete ni habilita esas rutas. Su CSRF permanece cerrado y login/me
siguen ausentes. No hay flag de producción para activar el ensayo o aceptar
una IP declarada. La composición MVP09 no registraba logout. MVP10 conecta
`POST /api/v1/auth/logout` mediante SolicitudLogout y AdaptadorAuth existentes,
con cuerpo {}, respuesta 204, revocación persistente y rechazos Origin/CSRF
ya contratados. Conserva TLS, SEC-01B y evidencia local antes del adaptador;
no altera DTO ni el contrato público V1. No se registra administración.

La [guía ejecutable](../../backend/herramientas/ingreso_local/README.md) describe
recursos, pruebas y limpieza. MVP09 conserva la política OWS/NBSP ya fusionada de
#30 y la opción preservePairEvidence de búsqueda. El sello permite filtrar cookies
ajenas mediante esa función existente, pero comprueba independientemente que las
credenciales reservadas no se reparen, elijan ni descarten. Una diferencia cierra
el canal; no se reemplaza la política por la variante antigua de MVP07.

La única traducción BFF es POST /api/local/csrf → GET /api/v1/auth/csrf, con Origin
real y mismo origen. Las lecturas SSR necesitan una capacidad de código distinta:
navegación GET en inicio/métricas/tickets hacia GET de tickets o conteos permitidos.
Se validan Origin/Fetch-Site originales cuando existen, se rechaza un token CSRF
en esa delegación y se conservan socket/pares reservados. No permite escrituras,
bootstrap CSRF ni /me delegado. Nonces nuevos también para cada lectura SSR.

La fábrica habitual conserva su cierre, y ninguna variable pública instala la
capacidad privada. La comprobación Edge se ejecuta por separado con el driver
real; no acredita Render, múltiples workers, TLS público o cookies production.
