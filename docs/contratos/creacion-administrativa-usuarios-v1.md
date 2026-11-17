# Creación administrativa de usuarios — AUTH-07C.2B

**APPROVED para implementación interna:** P1–P15, matriz, política de credenciales
y evento user_created aprobados expresamente por el Product Owner en
SYNAPDESK-AUTH07C2B-ADMIN-USER-CREATION-PERSISTENT-ACTIVATION. Sustituye el borrador
AUTH-07C.2. La aprobación no acredita un despliegue ni un canal administrativo.
No se registran rutas HTTP y no existe registro público.

Complementa el [contrato de autenticación](autenticacion-v1.md) y conserva el
[bootstrap inicial](bootstrap-administrador-v1.md). Sus aprobaciones tienen
alcances distintos: bootstrap crea al primer admin; esta operación exige un
administrador SynapDesk ya autenticado.

## Políticas aprobadas

| Política | Acuerdo |
| --- | --- |
| P1 | Solo admin autenticado, activo y con sesión persistente vigente puede crear cuentas. |
| P2 | Admin puede crear admin y agent. |
| P3 | Agent no puede crear cuentas. |
| P4 | Anónimo no puede crear cuentas. |
| P5 | Las cuentas nuevas nacen activas. |
| P6 | Correo normalizado y único en PostgreSQL. |
| P7 | Política vigente y Argon2id; nunca contraseña en texto plano en persistencia. |
| P8 | Captura mediante canal administrativo protegido, sin valores predeterminados, logs o exposición en respuestas. |
| P9 | Entrega privada externa acordada; sin correo automático ni contraseña devuelta por el coordinador. |
| P10 | Auditoría user_created obligatoria, atómica con la cuenta. |
| P11 | Autorización revalidada dentro de la transacción que persiste la cuenta. |
| P12 | Sin registro público. |
| P13 | Cambios posteriores de rol, desactivación, eliminación y recuperación quedan excluidos. |
| P14 | Sin sesión automática para la cuenta nueva. |
| P15 | Errores saneados sin hashes, tokens, credenciales o datos sensibles innecesarios. |

## Matriz de autorización

| Actor vigente en PostgreSQL | Crear admin | Crear agent |
| --- | --- | --- |
| Admin activo con sesión vigente | Permitido | Permitido |
| Agent | Denegado | Denegado |
| Anónimo, sesión ausente, revocada o vencida | Denegado | Denegado |
| Cuenta administrativa inactiva o rol cambiado a agent | Denegado | Denegado |

El rol solicitado pertenece a la cuenta nueva y no autoriza al actor.
AuthUser, una respuesta anterior de me, UUID, booleanos, cookie sin comprobación
o bearer del intermediario no conceden permiso.

## Interfaz y credenciales

[ServicioCreacionUsuarios](../../backend/app/seguridad/creacion_usuarios.py)
recibe DatosNuevoUsuario en preparar: nombre requerido por Usuario, correo, rol
admin/agent y contraseña SecretStr. Comparte la sintaxis mínima de
SolicitudLogin.validar_email y normalizar_cuenta: strip/lower, un único @,
partes no vacías y sin espacios. No introduce equivalencias de proveedores.

La política vigente de ServicioContrasenas acepta texto UTF-8 no vacío, sin
recortar la contraseña. Esta es la política aprobada para este incremento;
no se atribuye una fortaleza, longitud mínima adicional o calibración de recursos
que el componente no garantice. Argon2id usa sal aleatoria y configuración
existente; preparar calcula el hash antes de abrir conexión o mantener locks.
UsuarioPreparado oculta el hash en repr, no conserva la contraseña y está ligado
a la instancia. Es un objeto interno de confianza: no deserializarlo desde HTTP
ni serializar sus atributos. SecretStr no cifra la memoria del proceso.

crear exige ReferenciaSesion y UsuarioPreparado de esa instancia. Devuelve
únicamente AuthUser con id/email/role después del commit. No devuelve contraseña,
hash, cookie o sesión, ni envía correo. ensayar usa la misma inserción y auditoría,
pero solo en base temporal local verificada de 5433 y con rollback obligatorio;
su resultado no acredita persistencia.

El operador debe acordar y comprobar la identidad del destinatario, capturar la
contraseña sin argv, URL, eco, archivos temporales o logs, y entregarla por un
canal privado externo acordado con acceso restringido. Descartar referencias a
la entrada cuando termine la operación. El coordinador no implementa captura
interactiva ni puede garantizar la privacidad del canal externo. La futura
integración debe proteger ambos tramos y el proceso que maneja los secretos.

## Auditoría user_created

| Dato | Representación persistente |
| --- | --- |
| Tipo | tipo_evento = user_created |
| Administrador responsable | actor_tipo = synapdesk_user, actor_id = UUID del admin vigente |
| Cuenta creada | usuario_id = UUID de la cuenta nueva |
| Rol asignado | rol_asignado = admin o agent |
| Fecha | ocurrido_en, reloj PostgreSQL UTC |
| Resultado | resultado = success |
| Motivo | motivo = user_created_by_admin |
| Correlación | request_id UUID del servidor; sesion_id referencia a la sesión del admin |

No reutiliza admin_bootstrap ni atribuye el acto a un principal externo.
No admite metadatos libres, contraseña, hash, credencial de sesión, cookie,
CSRF, bearer o secretos. Los rechazos no generan user_created ficticio.

La [revisión 0006](../../backend/migraciones/versiones/0006_user_created.py)
ensancha actor_id de 32 a 36 para UUID y amplía la restricción existente para
el actor interno. Añade únicamente rol_asignado, que el esquema previo no podía
representar sin sobrecargar motivos u otros campos. Reutiliza actor, sujeto,
resultado, fecha y correlación existentes. Mantiene eventos/actores anteriores
y sus significados. El identificador del actor es una instantánea histórica;
no introduce una FK que pierda al actor por borrado. Las FK previas conservan
SET NULL. Retención, purga y acceso a auditoría no cambian.

Downgrade a 0005 se permite si no hay user_created; con altas auditadas rechaza
la reversión sin truncar UUID ni eliminar eventos. No modificar revisiones previas.

## Transacción y concurrencia

El coordinador usa transaccion_seguridad, READ COMMITTED y una Session propia.
ServicioSesiones.consultar recupera la sesión por digest de la credencial,
bloquea cuenta del actor FOR SHARE y después sesión FOR UPDATE, recarga estado
persistente y consulta el reloj después de adquirir locks. Comprueba existencia,
revocación, expiración absoluta (ocho horas), inactividad (30 minutos), cuenta
activa y rol actual admin. La igualdad con un límite significa vencimiento.

Después comprueba el correo e inserta el usuario activo con hash. La restricción
uq_usuarios_correo decide también frente a inserciones concurrentes. Tras flush
revalida autorización; registra user_created en esa misma transacción y revalida
otra vez después de la escritura de auditoría. No renueva actividad o expiración
administrativa. Ningún lock se mantiene durante Argon2id.

Los locks duran hasta commit/rollback. Revocación, desactivación o cambio de rol
confirmados antes de adquirirlos se observan y rechazan. Si el alta obtuvo los
locks primero, el cambio espera y puede confirmarse después del alta autorizada;
no hay revocación retroactiva. Se revalida el tiempo después de las esperas por
cuenta, sesión, correo y auditoría. La vigencia se observa en la última
revalidación anterior al commit; no se promete congelar el reloj físico durante
el acuse del commit ni ante extensiones externas con trabajo diferido.

Sesiones diferentes pueden crear correos diferentes simultáneamente; una misma
sesión se serializa. No hay lock global de usuarios. Escritores deben respetar
el orden cuenta del actor → sesión → usuario nuevo → auditoría. Un escritor
externo con orden inverso puede producir deadlock. lock_timeout = 3 s y
statement_timeout = 5 s; estos fallos se sanean y revierten sin reintento automático.

## Atomicidad, errores y conciliación

Cuenta y evento comparten un único commit. Fallos de inserción, auditoría o
restricción diferida revierten ambas escrituras. Un commit fallido no devuelve
éxito. No se usan mocks como evidencia de atomicidad: las pruebas de persistencia
y restricciones se ejecutan en PostgreSQL real.

Entrada/hash/autorización/correo existente usan ErrorCreacionUsuario con códigos
ENTRADA, HASH, NO_AUTORIZADO y CORREO_EXISTENTE. Sesión, transacción e
infraestructura conservan ErrorSeguridad. Los mensajes son fijos y no interpolan
valores privados ni excepciones SQL. No se fijan códigos o respuestas HTTP aquí.
No registrar tracebacks con entradas o contexto del driver en una integración.

La pérdida del acuse de commit deja un resultado incierto: el servidor puede
haber confirmado cuenta y evento. El cliente no debe repetir ciegamente la
operación ni interpretar indisponibilidad como rollback seguro. Conciliar por
id si fue obtenido de forma confiable o por correo normalizado mediante lectura
administrativa autorizada, verificando cuenta, rol y su user_created. Un duplicado
por sí solo no acredita quién creó la cuenta ni entrega credenciales. Resolver
la incertidumbre antes de decidir otro intento. No hay clave de idempotencia,
recuperación, reintento automático ni borrado para reparar incertidumbre.

## Condiciones futuras para HTTP y exclusiones

Antes de exponer administración: acordar ruta, DTO/respuestas y traducción de
errores; extraer solo la cookie permitida; validar sesión vigente, Origin estricto,
CSRF autenticado, intermediario e IP de procedencia cuando corresponda; aplicar
cuotas/admisión y límites de entrada adecuados antes de Argon2id; configurar TLS,
cookies y no-store, acceso al proceso y operación de secretos. El bearer de
servicio no sustituye la sesión del administrador. Definir conciliación operativa
de respuestas perdidas. El transporte futuro no puede pasar un rol como prueba.

No existen rutas HTTP de altas/login/me/logout registradas, registro público,
CLI nueva de altas posteriores, usuarios al arrancar, correo automático, sesión
automática, cambios de roles/contraseñas, desactivación, eliminación, recuperación
o protección del último admin en este incremento. Frontend, ML, proxy #30 y
búsqueda #32 quedan fuera. No se inicia integración HTTP ni AUTH-07C.3.

Las decisiones P1–P15 ya no están pendientes; la revisión humana del código y
la integración/operación futuras conservan sus propios requisitos.
