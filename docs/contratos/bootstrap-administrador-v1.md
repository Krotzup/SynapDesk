# Bootstrap administrativo V1 — AUTH-07C.1B

**APPROVED para implementación:** P1–P10 y evento admin_bootstrap, autorizados
expresamente por el Product Owner en SYNAPDESK-AUTH07C1B-ADMIN-BOOTSTRAP-PERSISTENT-ACTIVATION.
La aprobación no acredita producción, identidad de personas ni controles del host.
Este documento sustituye el borrador AUTH-07C.1; no cambia permisos de altas
posteriores, sesiones, CSRF, cookies o recuperación de cuentas.

## A. Políticas autorizadas

| Política | Acuerdo |
| --- | --- |
| P1 | Solo CLI administrativa explícita, fuera de HTTP, arranque y migraciones. |
| P2 | Esquema vigente e instalación inicial con conjunto de usuarios vacío. |
| P3 | Cualquier usuario, sin distinguir rol/estado/fecha, impide bootstrap. |
| P4 | Sin contraseñas predeterminadas o incorporadas al código. |
| P5 | Contraseña y confirmación ocultas; sin argv, eco o archivo temporal deliberado. |
| P6 | Primer usuario activo y con rol admin. |
| P7 | Sin recuperación, cambio de administrador o restauración. Un evento previo admin_bootstrap impide reabrir el flujo aunque se hayan eliminado usuarios. |
| P8 | Sin contraseñas, hashes, tokens o credenciales de conexión en salida, errores o logs. |
| P9 | Exclusión PostgreSQL frente a bootstrap e inserciones concurrentes. |
| P10 | Usuario y auditoría admin_bootstrap se confirman juntos; éxito solo después del commit. |

Se mantienen normalización/sintaxis de email y validación de contraseña existentes:
strip/lower mediante la función compartida de login y texto UTF-8 no vacío, sin
recortar la contraseña. No se inventa otra longitud o política de fortaleza.
El nombre se solicita porque Usuario lo exige; no se agrega a AuthUser.

## Evento y compatibilidad de auditoría

- tipo_evento: admin_bootstrap.
- resultado: success.
- motivo: initial_admin_created.
- usuario_id: sujeto creado, no actor que autoriza la acción.
- actor_tipo: postgresql_role.
- actor_id: OID decimal del principal autenticado session_user de PostgreSQL.
- ocurrido_en: reloj PostgreSQL; request_id: UUID nuevo del servidor.
- sesion_id e IP: ausentes; no existe sesión previa ni se inventa IP acreditada.

El actor representa al principal administrativo de BD, que puede ser compartido;
no certifica quién fue la persona física ni usa getpass.getuser o variables de
usuario como prueba de autorización. El operador debe conservar trazabilidad
externa restringida del acceso a ese principal cuando se necesite identificar
personas. No se almacena nombre de rol, DSN, contraseña, hash, cookie o bearer.

La revisión nueva 0005_actor_bootstrap agrega actor_tipo y actor_id opcionales,
con una restricción para el nuevo evento. Los eventos históricos conservan NULL
sin reinterpretación. La FK de usuario conserva SET NULL: perder el sujeto por
borrado no elimina el actor ni el evento. No se modifican migraciones previas.
El downgrade rechaza retirar los campos si existe auditoría admin_bootstrap.
Los eventos anteriores conservan tipos, motivos y significado.

No se añade un evento falso de login/session_created ni un catálogo de rechazo
administrativo distinto. Un rechazo no afirma creación; fallo de auditoría de
éxito revierte el usuario. Retención, acceso y purga generales continúan sujetos
a las decisiones existentes; esta autorización no introduce políticas nuevas.

## Autorización y destino

La ejecución administrativa exige identidad PostgreSQL real: session_user igual
a current_user y al principal de configuración, OID igual al propietario de la
base y permisos efectivos SELECT/INSERT, además de UPDATE en usuarios para el
bloqueo. No se permite usar SET ROLE para sustituir esa identidad. Esto verifica
el principal y su capacidad administrativa, no permisos del sistema operativo.

El principal de mantenimiento debe estar restringido por controles del host,
contenedor, acceso a secretos y autenticación PostgreSQL. Separarlo del rol de
aplicación y evitar credenciales compartidas sin trazabilidad. No conceder
superusuario solo para usar la herramienta; revisar propiedad de BD/tablas y
permiso específico para pg_control_system cuando sea viable.

La CLI persistente exige POSTGRES_SSLMODE=verify-full, TLS real observado en
pg_stat_ssl y AUTH_BOOTSTRAP_CLUSTER_ID explícito, contrastado con system_identifier
del servidor. libpq verifica CA y hostname. El pin no sensible no sustituye TLS.
También contrasta current_database, OID de base, principal, OIDs de tablas,
revisión Alembic exacta y estructura/restricciones críticas. Se confirma a mano
la descripción completa del destino, sin URL ni credenciales.

DestinoAutorizado es evidencia interna ligada a la instancia, no JSON ni una
bandera. La CLI solo la obtiene de verificar_destino. Los fixtures pueden
construirla después de validar SQL en una base temporal controlada, sin afirmar
TLS de PostgreSQL; ese adaptador no existe en la CLI ni se activa por entorno.
Código Python malicioso con acceso al proceso o credenciales queda fuera del
límite de aislamiento de estos tipos internos.

## Transacciones, concurrencia y errores

Captura y Argon2 preceden a la conexión de alta. Dentro de una única transacción:
revalidar destino/autorización, adquirir SHARE ROW EXCLUSIVE en public.usuarios,
revalidar esquema/destino tras la espera, comprobar usuarios e historial de
bootstrap, insertar admin activo y registrar el evento. El lock también
conflicta con INSERT/UPDATE/DELETE de procesos no cooperantes.

lock_timeout de alta: 3 segundos. La conexión conserva statement_timeout de
5 segundos. No se espera con Argon2 bajo lock. El orden es usuarios → auditoría;
un escritor externo con orden inverso puede causar deadlock, que se sanea y
revierte, sin reintentos automáticos. Un segundo bootstrap tras el primer commit
rechaza por estado existente. Los ensayos heredados mantienen rollback obligatorio
sin auditoría ficticia, limitados a bases temporales localhost:5433.

Fallo de INSERT, auditoría, flush o commit rechazado: rollback, sin éxito. Si se
pierde la conexión durante commit, el resultado puede ser desconocido: no afirmar
rollback, no reintentar automáticamente. Verificar cuenta/evento persistidos con
un procedimiento administrativo autorizado; nunca borrar filas para reabrir
bootstrap ni convertirlo en recuperación.

## B. Verificación local

Ver [informe AUTH-07C.1B](../auditorias/auth07c1b-bootstrap.md) y evidencia. Las
pruebas PostgreSQL comprueban alta realmente confirmada, lectura en otra conexión,
auditoría y actor, login interno del admin con CSRF e IP de fixture, me/logout,
rollback de fallos, restricción diferida de commit, carreras de procesos, INSERT
externo, timeout y deadlock aislado. No se ejecuta la CLI contra instalaciones
reales ni se abren rutas HTTP. Las pruebas TLS anteriores son de intermediario
Node/FastAPI, no una certificación del canal PostgreSQL de producción.

## C. Requisitos operativos pendientes

Verificar posteriormente CA/hostname/TLS del servidor PostgreSQL, pin correcto
obtenido por un canal administrativo confiable, credenciales/ACL del principal
de mantenimiento, acceso al proceso y secretos, terminal protegido, migración y
revisión humana. No se declara Render o producción validados por pruebas locales.
La configuración por defecto mantiene el alta CLI cerrada si falta cualquiera
de esas condiciones. No hay --yes, --force o --skip-confirmation.

## D. Exclusiones

Sin registro público, HTTP de altas, alta posterior, recuperación/cambio de
contraseña, administración de roles/desactivaciones o protección del último
admin nuevo en este incremento. AUTH-07C.2 requiere autorización separada de
permisos y actor admin vigente dentro de su transacción de escritura. Una
respuesta antigua de me o identidad de servicio no concede ese permiso.
