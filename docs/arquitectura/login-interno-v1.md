# Login interno — AUTH-07B.2

Estado: implementación interna para revisión. No aprueba parámetros operativos,
no modifica contratos y no habilita POST `/api/v1/auth/login`, me, logout o altas.
Se conserva el cierre HTTP CSRF de AUTH-07B.1/SEC-01B.

## Interfaz y fronteras

[ServicioLogin](../../backend/app/seguridad/login.py) recibe Engine PostgreSQL,
Configuracion, capacidad_argon2 positiva y explícita, y el Reloj AUTH-06 (por
defecto clock_timestamp de PostgreSQL). Es propietario de las sesiones y límites
transaccionales; no admite una Session externa ni un commit pendiente del llamador.
Su construcción requiere HMAC y las seis cuotas existentes; no necesita bearer
Next.js, acceso HTTP ni configuración de bootstrap para ejecutar el login interno.

1. CredencialesLogin normaliza mediante normalizar_cuenta, exige SecretStr para
   contraseña y oculta ambos campos en repr. No añade equivalencias de proveedores
   ni reemplaza la validación sintáctica de SolicitudLogin en la frontera HTTP.
2. PruebaAnonimaLogin contiene posesión del secreto anónimo y del token CSRF.
   PruebaSesionLogin contiene posesión de sesión y token de su contexto autenticado.
   Esas entradas no son por sí mismas comprobantes de validez.
3. validar_contexto comprueba posesión, vinculación y vigencia con ServicioCsrf y,
   cuando corresponde, ServicioSesiones; exige IpVerificada. Emite un
   ContextoLoginValidado ligado a esa instancia del coordinador.
4. autenticar acepta exclusivamente CredencialesLogin y ese contexto validado.
   Rechaza booleanos, UUID, cadenas HTTP y contextos de otro coordinador.
   Revalida las pruebas en BD antes de admitir y antes de crear sesión.

La marca de instancia evita composición accidental de objetos internos; no es
una firma ni un aislamiento frente a código Python malicioso. IpVerificada sigue
siendo una abstracción de código confiable, no una cabecera ni prueba criptográfica.
Los fixtures utilizan ServicioIpConfiable con evidencia sintética controlada.
No existe adaptador HTTP que fabrique estas pruebas, IP o tiempos.

LoginConfirmado devuelve Identidad (solo id/email/role) y SesionEmitida interna,
oculta en repr. Esta última permite al adaptador futuro construir su cookie
después del commit. No serializar el resultado completo a JSON ni registrar sus
campos secretos. LoginRechazado usa MotivoEvento del catálogo existente, con la
DecisionLimite cuando se agotó cuota. No se añade un código HTTP de login.

## Transacciones y trabajo criptográfico

La validación inicial de contexto es una transacción breve de solo control.
Cada intento usa UUID de correlación generado en servidor. Después:

1. Admisión: reservar por cuenta normalizada e IP mediante ServicioLimites;
   volver a validar CSRF; leer una instantánea mínima del usuario. Confirmar la
   reserva antes del trabajo costoso. Un rechazo CSRF revierte la reserva de
   esta transacción. Un rechazo de cuota confirma el evento rate_limit.
2. Argon2id: cerrar conexión y transacción de admisión, y verificar mediante
   ServicioContrasenas. Una cuenta inexistente usa un hash efímero aleatorio
   preparado por el mismo servicio, sin crear un usuario ficticio. Cuentas
   inactivas también atraviesan verificación. No se promete tiempo constante
   de la solicitud completa ni se ocultan todos los efectos de parámetros viejos.
3. Confirmación: consolidar reserva; bloquear usuarios por UUID ordenado mediante
   el mecanismo de ServicioSesiones; releer usuario/correo/estado/rol/hash; validar
   sesión/contexto/token y tiempo después de sus locks. Una reserva que venció
   durante el cálculo o la espera no autoriza sesión.
4. Dentro de esa misma transacción: crear sesión con ServicioSesiones, invalidar
   contexto y tokens previos, crear el contexto autenticado nuevo con ServicioCsrf
   y registrar login/session_created y, si corresponde, session_revoked/reemplazo.
5. Devolver LoginConfirmado únicamente después del commit. Un fallo de auditoría,
   flush o rechazo confirmado del commit revierte sesión, invalidación de contexto,
   revocación y eventos de éxito. La reserva previamente confirmada no desaparece
   por ese rollback.

El orden común es cuotas → usuarios ordenados → sesión → contextos, también en
admisión, para evitar inversión entre solicitudes que comparten contexto/cuotas.
El coordinador reutiliza el helper interno de bloqueo de ServicioSesiones; un
cambio futuro de esa API debe revisar esta composición y sus carreras.

Los rechazos se auditan en una nueva transacción después del rollback. Si existe
reserva vigente, se consolida allí; una reserva vencida continúa cerrada conforme
a ServicioLimites y no permite éxito. Si falla PostgreSQL o la auditoría de
rechazo, se propaga un error saneado, sin inventar persistencia del evento.
No se registran entradas, hashes de contraseña, bearer, cookies ni tokens.

Si se pierde la conexión durante el commit, su resultado puede ser desconocido:
no se devuelve el secreto ni se reintenta automáticamente. Podría existir una
sesión íntegramente confirmada con sus eventos pero sin cookie entregada; caducará
según las reglas existentes. No se afirma un rollback confirmado de ese caso.

## Cuotas, capacidad y errores

Se conserva la política implementada por AUTH-06: todo intento admitido consume
cuenta e IP, incluidos éxitos, credenciales inválidas e interrupciones posteriores
al commit de reserva. No se devuelve cuota ni se reinicia por éxito. Los fallos
CSRF anteriores a admisión no confirman una reserva. Esta conservación no aprueba
la política definitiva de consumo de éxitos, las cifras ni la purga de recibos.

capacidad_argon2 acota intentos concurrentes por instancia, sin cola implícita.
La saturación produce INFRAESTRUCTURA y un evento validation/security_unavailable;
no inventa Retry-After ni consume una reserva nueva. Mantener una instancia por
worker al integrar. Falta calibrar memoria/CPU/capacidad entre workers; este
semáforo local no es un limitador global distribuido ni certifica producción.

Cuenta inexistente, inactiva y contraseña incorrecta devuelven exactamente
LoginRechazado(credentials_rejected), con evento login/failure sin usuario_id.
Hash corrupto o fallo de Argon2 conserva ErrorContrasena saneado y auditoría
security_unavailable; no se trata una avería como contraseña incorrecta.
CSRF, sesión y persistencia utilizan ErrorSeguridad/CodigoSeguridad existentes.
Cuenta inactiva se representa por activo=False; roles admitidos siguen admin/agent.
No se agrega un catálogo de estados de usuario ni de eventos.

## Reemplazo y decisiones pendientes

El contrato de autenticación vigente, sección 7/login, indica que una sesión
previa válida presenta su cookie y token del contexto autenticado; no se elige
un contexto anónimo independiente para reemplazarla. Se implementa esa rama con
PruebaSesionLogin. El primer login utiliza PruebaAnonimaLogin. Una credencial de
sesión presentada no basta sin el token CSRF ligado a ella.

El reemplazo revoca exclusivamente la sesión presentada y sus contextos/tokens,
conservando dispositivos independientes. Puede cambiar de usuario conforme a la
primitiva de reemplazo existente, manteniendo locks ordenados de ambos usuarios.
La nueva sesión conserva ocho horas absolutas y treinta minutos de inactividad;
no se reactivan sesiones previas ni se amplía actividad por consultar CSRF.

Se mantienen cerradas las recuperaciones de sesión desconocida, vencida o
revocada y las representaciones ambiguas. Un adaptador HTTP futuro no debe
ignorar una cookie presentada para elegir artificialmente la rama anónima.
Siguen pendientes aprobación de recuperación, perfiles de cookies, catálogo
HTTP específico de login, consumo definitivo de cuotas, calibración, purga y
operación de auditoría. No se hace rehash automático ni se cambia la contraseña.

## HTTP y continuación

Origin estricto permanece obligatorio en la frontera HTTP futura. SEC-01B debe
acreditar el intermediario y el transporte de forma independiente, y debe existir
una procedencia IP aprobada. Un bearer válido no sustituye ninguno de esos
controles ni autentica al usuario. TLS local no acredita Next.js ni Render.
No hay ruta de desarrollo, emisor HTTP de CSRF ni login público nuevo.

Para exponer login faltan bootstrap CSRF seguro, IP acreditada, integración del
proxy con TLS verificado y cookies interoperables, decisiones pendientes y pruebas
de extremo a extremo. Me y logout pueden reutilizar sesiones/CSRF/cookies/auditoría,
sin reutilizar una prueba de contraseña o un resultado antiguo como autorización.
AUTH-07C requiere un procedimiento administrativo de altas con hashing real,
política de acceso/entrega de credenciales y datos de ensayo controlados; no una
contraseña predeterminada, registro público ni usuario sembrado automáticamente.

## Verificación reproducible

Desde backend, ejecutar `herramientas/validar_login.py` con el intérprete del
proyecto. Reutiliza el validador de bases temporales verificadas en localhost:5433
y conserva su prefijo SEC-01A, requerido por fixtures anteriores. Genera un
informe distinto; no sobrescribe los dos informes auxiliares SEC-01B.
Incluye pip check, Alembic upgrade/current/heads/check, suite unitaria e integración
PostgreSQL/TLS completas. La herramienta confirma eliminación de su propia base.
No realiza escrituras contra localhost:5432 ni modifica configuración privada.
