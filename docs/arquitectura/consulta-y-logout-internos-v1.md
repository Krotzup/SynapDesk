# Consulta de sesión y logout internos — AUTH-07B.3

Estado: implementación interna para revisión. No modifica contratos aprobados,
no registra GET `/api/v1/auth/me` ni POST `/api/v1/auth/logout`, no crea cookies
ni habilita login o emisión CSRF. SEC-01B conserva su estado de borrador.

## Interfaces y límites de confianza

[operaciones_sesion.py](../../backend/app/seguridad/operaciones_sesion.py) incorpora:

- `ReferenciaSesion(SecretStr)`: posesión presentada, con representación canónica
  validada por `digest_secreto`. Oculta la credencial en repr y es inmutable.
  No prueba vigencia, identidad de usuario, Origin, IP ni autenticidad del servicio.
  No admite UUID, booleanos, cadenas HTTP ni identidad elegida por el cliente.
- `ServicioConsultaSesion(motor, reloj=...).consultar(referencia)`: devuelve el
  `AuthUser` existente, exclusivamente id, email normalizado y role vigente.
- `ServicioLogout(motor, configuracion, reloj=...).cerrar(referencia, token=...)`:
  devuelve `LogoutConfirmado(revocada=True)` solo tras confirmar su transacción;
  `False` identifica la rama idempotente sin afirmar revocación.

Ambos coordinadores son propietarios de su Session/transacción PostgreSQL y
usan aislamiento READ COMMITTED explícito, como ServicioLogin. No admiten una
Session del llamador ni un commit diferido. El reloj predeterminado es
`clock_timestamp()` de PostgreSQL; el reloj inyectado de los tests es controlado
en código confiable y no se recibe desde HTTP.

Un futuro adaptador autorizado deberá extraer exactamente una cookie permitida
mediante `leer_cookie`, validar representación y construir la referencia. Los
tipos Python evitan composiciones accidentales; no aíslan código malicioso
ejecutado en el proceso. Nunca serializar referencias, resultados de login o
SecretStr completos para construir respuestas públicas.

## Consulta, usuario y actividad

Se reutiliza `ServicioSesiones.consultar`, sin duplicar su verificador: digest y
posesión, existencia, revocación, caducidad absoluta, inactividad, cuenta activa y
rol admin/agent. El correo/rol se leen de Usuario bajo los locks existentes y se
proyectan explícitamente al DTO; no se serializa ORM ni se congela el rol del login.

La ausencia de referencia o una sesión inválida produce ErrorSeguridad existente.
No devuelve hash, nombre, estado interno, token ni secreto. La FK RESTRICT de
sesiones impide eliminar un usuario referenciado; una inconsistencia de datos
no autoriza identidad. No se agrega un evento de auditoría ficticio por cada lectura.

No se llama `registrar_actividad`. Consultar repetidamente no modifica
ultima_actividad ni expira_en. A los treinta minutos sin una actualización
explícita autorizada, consultar vuelve a rechazar; ocho horas sigue siendo el
máximo absoluto, incluso si otra operación actualizó actividad.

Pendiente de aprobación: si /me contará como actividad, qué otras rutas podrán
renovarla, cuándo actualizar, cómo coordinar consultas simultáneas y cómo evitar
que el sondeo automático prolongue sesiones. Esta tarea no elige esa política.

## Logout y precedencia contractual

Se conserva la sección 7 APPROVED del
[contrato de autenticación](../contratos/autenticacion-v1.md):

1. Sin referencia (`None` representa ausencia de cookie, no cookie malformada):
   no consulta BD, no exige CSRF y devuelve revocada=False.
2. Con referencia canónica: consulta PostgreSQL mediante ServicioSesiones.
   Sesión confirmada inexistente, vencida o revocada devuelve revocada=False;
   no exige un token antiguo ni registra otra revocación. Fallo de BD nunca
   equivale a esa confirmación. Las representaciones malformadas se rechazan
   al construir la referencia y no entran en la rama de ausencia.
3. Sesión válida: exige SecretStr y `ServicioCsrf.validar_token(..., sesion=...)`.
   Comprueba contexto autenticado, vinculación, revocación y vencimientos. Un
   token de otra sesión/contexto o un contexto anónimo no autoriza logout.
4. Reconsulta la sesión después de los locks CSRF y usa `ServicioSesiones.revocar`.
   Invalida persistentemente los contextos y todos sus tokens mediante la
   primitiva existente, sin afectar otros dispositivos ni modificar cuotas.
5. En la misma transacción registra session_revoked/success/logout con IDs
   obtenidos de la consulta y request_id nuevo del servidor. Confirma antes de
   devolver revocada=True. No construye cookies.

Los tokens siguen siendo reutilizables mientras su contexto sea válido, según
AUTH-06. Un segundo logout después de revocación confirmada es idempotente,
aunque no tenga token o el token antiguo ya sea inválido. Esto no permite omitir
CSRF sobre una sesión válida. Origin sigue siendo obligatorio incluso sin cookie,
pero pertenece al adaptador HTTP futuro y no se simula en estas operaciones.

Caso pendiente de especificación HTTP: cookie de sesión no vencida cuyo usuario
fue desactivado (o cuyo rol es inválido). Se conserva el rechazo seguro de
ServicioSesiones; no se lo convierte unilateralmente en revocación ni éxito
idempotente. No se introduce un código HTTP nuevo para resolverlo.

## Atomicidad, auditoría y concurrencia

Orden reutilizado: usuario SHARE → sesión UPDATE → contexto UPDATE. El reloj
se relee después de adquirir los locks; esperar no prolonga la autorización.
La consulta retiene los locks hasta terminar su transacción breve. No hace
cálculo Argon2 ni llama nuevamente al limitador de login.

Los cambios de usuario confirmados antes de adquirir el lock se observan en la
respuesta; un cambio que espera detrás de una consulta ya autorizada no invalida
retroactivamente esa respuesta. Una revocación confirmada impide consultas
nuevas. Dos logouts simultáneos producen una revocación y un evento de éxito;
el segundo observa sesión revocada y devuelve revocada=False. No se promete
cancelar una respuesta /me autorizada antes del logout.

Revocación, contextos, tokens y evento de éxito comparten commit. Fallo de
auditoría, SQL o rechazo del commit revierte todos esos cambios. Tras rollback,
los rechazos usan únicamente validation/failure y csrf_invalid, session_invalid
o security_unavailable del catálogo existente, en una nueva transacción. No se
incluyen entradas, secretos, correo ni detalles libres. Si también falla esa
auditoría, se propaga error saneado sin afirmar que el evento quedó persistido.
No se registra una revocación ficticia en las ramas idempotentes.

Pérdida de conexión durante commit puede dejar resultado desconocido. No se
afirma rollback en ese caso, no se devuelve éxito ni se reintenta automáticamente.
Una petición posterior deberá volver a comprobar el estado persistido.

## Integración HTTP pendiente y AUTH-07C

No se convierte bearer de intermediario en usuario ni se construye IpVerificada
desde cabeceras/socket/loopback. Estas operaciones no requieren IP ni cuotas
nuevas: logout no tiene un límite específico aprobado y la lectura no consume
una reserva de login. Su auditoría usa el digest IP opcional ausente; no inventa
una dirección. Esto no aprueba una excepción a controles de canal futuros.

Para conectar FastAPI faltan extracción inequívoca de cookies con perfil aprobado,
Origin según lectura/SSR y obligatorio para toda mutación, identidad de servicio
y TLS verificado, composición con el flujo CSRF y políticas HTTP/cookies pendientes,
errores saneados/no-store y pruebas proxy extremo a extremo. El adaptador debe
preservar la precedencia idempotente antes de exigir el encabezado CSRF, y
traducir rechazos CSRF solo cuando estén acreditados antes de efectos de negocio.
No borrar cookies ni devolver éxito persistente antes del commit requerido.

El cierre de bootstrap CSRF, la IP Render sin acreditar y las condiciones de
activación de login permanecen intactos. La prueba TLS local no acredita Render.
AUTH-07C puede reutilizar Usuario/admin-agent, normalizar_cuenta,
ServicioContrasenas Argon2id, transacciones y estas operaciones para comprobar
cuentas creadas administrativamente. Aún necesita política de alta/contraseñas,
permisos administrativos y entrega de credenciales; no se agrega registro público,
cuenta automática ni contraseña predeterminada.

## Validación reproducible

Desde backend ejecutar `herramientas/validar_sesiones.py` con el intérprete del
proyecto. Reutiliza el validador restringido a localhost:5433 y una base exclusiva
con prefijo SEC-01A. Verifica identidad antes de migrar y antes de eliminarla.
Incluye pip check, Alembic upgrade/current/heads/check, todas las unitarias y
las integraciones PostgreSQL y TLS. El informe nuevo es
`docs/auditorias/auth07b3-sesiones-validacion.json`; no sobrescribe los cuatro
auxiliares históricos. Los tests de carreras observan locks en pg_stat_activity;
el fallo de commit se comprueba con una restricción diferible real de PostgreSQL.
