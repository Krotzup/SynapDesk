# Creación persistente de usuarios interna — AUTH-07C.2B

Implementación interna de las [políticas aprobadas P1–P15](../contratos/creacion-administrativa-usuarios-v1.md).
Un administrador vigente crea cuentas admin o agent activas con auditoría
user_created obligatoria. No hay rutas HTTP nuevas, CLI de altas posteriores,
alta al arrancar o registro público.

## Componentes

| Componente | Responsabilidad |
| --- | --- |
| [ServicioCreacionUsuarios](../../backend/app/seguridad/creacion_usuarios.py) | Preparación fuera de BD, autorización transaccional y commit propio |
| [Usuario](../../backend/app/persistencia/modelos/usuario.py) | Normalización compartida, UNIQUE, CHECK de rol y cuenta activa |
| [ServicioContrasenas](../../backend/app/seguridad/contrasenas.py) | Política vigente y Argon2id con sal aleatoria |
| [ReferenciaSesion](../../backend/app/seguridad/operaciones_sesion.py) | Credencial opaca tipada; no autorización anticipada |
| [ServicioSesiones](../../backend/app/seguridad/sesiones.py) | Relectura, bloqueos y vigencia persistente |
| [ServicioAuditoria](../../backend/app/seguridad/auditoria.py) | Catálogo cerrado, ActorUsuario y evento sin secretos |
| [transaccion_seguridad](../../backend/app/seguridad/transacciones.py) | Commit, rollback y saneamiento de errores incluido el commit |

## Flujo interno

1. Construir DatosNuevoUsuario con nombre/correo/rol y SecretStr recibido por
   un canal administrativo protegido.
2. preparar valida y calcula Argon2id sin conexión ni locks; devuelve
   UsuarioPreparado ligado a la instancia, sin conservar contraseña.
3. crear valida la referencia tipada y abre READ COMMITTED.
4. La función compartida _insertar consulta sesión real, bloquea cuenta FOR SHARE
   y sesión FOR UPDATE, comprueba estado/vigencia y exige admin actual.
5. Comprueba correo e inserta usuario activo; UNIQUE decide las carreras.
6. Revalida después de flush; registra user_created con actor admin, sujeto
   nuevo y rol asignado en la misma transacción.
7. Revalida después de la auditoría para observar expiración tras esperas.
8. Confirma y devuelve AuthUser id/email/role sin credenciales.

ensayar llama al mismo _insertar y revierte siempre usuario y evento. Está
limitado a testing, host local, 5433 y nombre temporal; verifica identidad
current_database/session_user/current_user y revisión 0006. El resultado de
ensayo contiene identificadores provisionales ya revertidos, persistido=False
y auditoria_registrada=False. No es una vía alternativa de persistencia.

## Garantías y límites

Los bloqueos y reloj se reutilizan de ServicioSesiones, sin duplicar lógica.
Cuenta/rol/expiración se releen después de esperas. Cambios previos confirmados
impiden el alta; cambios posteriores esperan a que termine la transacción.
Sesiones distintas permiten altas distintas simultáneas; una sesión se serializa.
No se modifica su actividad, expiración, revocación o CSRF ni se emite sesión
para el nuevo usuario. El [contrato](../contratos/creacion-administrativa-usuarios-v1.md)
detalla el límite temporal de la última revalidación y el orden de locks.

Los fallos de inserción, auditoría, commit y restricciones diferidas no producen
un resultado exitoso. Ante acuse de commit perdido puede existir una cuenta
confirmada: conciliar por id/correo normalizado y evento antes de decidir un nuevo
intento. Sin reintentos automáticos ni garantía de idempotencia de peticiones.

La [migración 0006](../../backend/migraciones/versiones/0006_user_created.py)
reutiliza actor_tipo/actor_id y sujeto usuario_id, amplía actor_id para UUID y
añade rol_asignado. Conserva auditoría anterior y bloquea downgrade con
user_created existente. El bootstrap exige ahora el head 0006 y mantiene sus
controles anteriores, sin modificar las migraciones 0001–0005.

## Credenciales e integración

La política vigente es texto UTF-8 no vacío sin recorte; no se inventa una
contraseña predeterminada ni fortaleza adicional. Solo persiste Argon2id.
SecretStr y repr reducen exposiciones accidentales; no cifran memoria.
El operador/integrador debe proteger captura, proceso, logs y entrega externa
por canal privado acordado. El coordinador no envía correo, devuelve contraseñas
ni garantiza la privacidad del canal externo.

HTTP requiere contrato y adaptador, cookies permitidas, Origin, CSRF, canal de
intermediario/IP, cuotas/admisión y límites antes del hashing, TLS y no-store.
El [contrato](../contratos/creacion-administrativa-usuarios-v1.md) conserva estos
requisitos futuros; no existe una ruta a la que conectar el proxy todavía.

## Validación reproducible

[validar_creacion_usuarios.py](../../backend/herramientas/validar_creacion_usuarios.py)
crea una base temporal propia en localhost:5433, verifica identidad, aplica
Alembic, ejecuta pip check y suites unitarias/PostgreSQL/TLS, elimina solo su base
y comprueba ausencia. Escribe evidencia C.2B sin sobrescribir los diez auxiliares
históricos ni los informes de preparación C.2. No modifica configuración privada.

Las [pruebas PostgreSQL](../../backend/pruebas/integracion/test_creacion_usuarios.py)
demuestran lectura desde otra conexión, login real con CSRF para admin/agent,
atomicidad con fallos SQL/commit, restricciones, carreras, revocación, estado/rol,
expiración bajo locks, timeout y deadlock. La pérdida del acuse se inyecta después
de un commit real; las desconexiones terminan solo conexiones propias de prueba.
No se detiene el servidor PostgreSQL compartido ni se certifica el despliegue.
