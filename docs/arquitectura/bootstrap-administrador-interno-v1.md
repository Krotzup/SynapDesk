# Operación del bootstrap administrativo — AUTH-07C.1B

Las políticas P1–P10 y admin_bootstrap están aprobadas para implementación.
Usuario y auditoría se persisten atómicamente. La habilitación en una instalación
real requiere verificar los controles operativos; no se ha ejecutado aquí.
Consultar el [contrato](../contratos/bootstrap-administrador-v1.md).

## Preparación administrativa

1. Restringir acceso al host/contenedor y al proceso; preparar un principal de
   mantenimiento PostgreSQL propietario de la base, separado del rol de aplicación.
   La CLI comprueba session_user, propietario y permisos reales, no el nombre del SO.
2. Revisar autenticación PostgreSQL y custodia de sus credenciales. No utilizar
   trust o acceso indiscriminado como autorización. Si se comparte principal,
   conservar trazabilidad externa de personas; el evento registra el OID del rol.
3. Configurar POSTGRES_* en el backend sin secretos en argumentos ni repositorio.
   Exigir POSTGRES_SSLMODE=verify-full, CA y hostname verificables por libpq.
   Configurar AUTH_BOOTSTRAP_CLUSTER_ID con system_identifier obtenido por un
   canal administrativo ya confiable. No copiar el pin de un servidor desconocido
   para hacer pasar el control; no es un secreto ni sustituye TLS.
4. Revisar/aplicar Alembic explícitamente hasta 0007_recomendaciones_rag. Las
   migraciones y el arranque no crean usuarios. La CLI requiere versión exacta,
   tablas/columnas y restricciones críticas; no ejecuta upgrade automáticamente.
   AUTH-07C.2B actualiza solo ese head requerido para compatibilidad de auditoría;
   conserva las políticas P1–P10 y el evento de bootstrap aprobados.
5. Confirmar ausencia de usuarios y de un bootstrap anterior, terminal protegido
   y acceso del principal a pg_control_system/ACL necesarios. Revisar lock_timeout
   de 3 s y statement_timeout de conexión de 5 s para el entorno; no son un SLA.

## Ejecución explícita

Desde backend, con el intérprete del proyecto y solo después de la revisión
operativa autorizada:

```text
<interprete-del-proyecto> herramientas/bootstrap_admin.py --base principal
```

No hay contraseña por argumento o variable alternativa. La CLI valida el destino
antes de pedir contraseña, muestra únicamente entorno/host/puerto/base, clúster,
OID de base y revisión, y exige escribir esa descripción exacta. No acepta --yes,
--force, --skip-confirmation ni destinos libres de CLI. No ejecutarla en la base
de desarrollo ni una instalación real como parte de pruebas automatizadas.

Después solicita correo, nombre y contraseña/confirmación mediante getpass. Si
no hay terminal interactivo o getpass intenta degradar a eco, rechaza. Usa las
reglas existentes de correo/contraseña y ServicioContrasenas Argon2id fuera de
conexión y locks. No recorta ni trunca contraseña, no imprime hash o entradas y
no crea un archivo temporal de credenciales. Python no garantiza borrado seguro
de todas las copias de strings en memoria. La política mínima existente no se
presenta como una certificación de fortaleza o capacidad productiva.

La autorización no procede de una bandera: la identidad PostgreSQL se revalida
antes y después de esperar el bloqueo. Usuario admin activo y evento se confirman
en la misma transacción, y solo entonces aparece el mensaje de éxito. El resultado
interno contiene identificadores, sin contraseña/hash/sesión. Nunca serializar
AdminPreparado ni registrar campos privados o excepciones del driver.

## Concurrencia, auditoría y reintentos

El bloqueo SHARE ROW EXCLUSIVE de usuarios serializa otros bootstraps e INSERT
externos. No basta unicidad de email para dos candidatos de correos distintos.
El estado se relee tras el lock. Orden de alta: usuarios → auditoría; timeout o
deadlock generan error saneado y no un éxito parcial. No hay retry automático.

admin_bootstrap/success/initial_admin_created registra fecha PostgreSQL,
correlación del servidor, sujeto creado y actor postgresql_role con OID real.
No se inventa usuario SynapDesk actor ni IP acreditada. Las columnas opcionales
actor_tipo/actor_id conservan NULL para eventos anteriores. La auditoría sobrevive
al borrado del sujeto; un evento de bootstrap previo impide reutilizar la CLI
como recuperación. El downgrade 0005 se rechaza si perdería esa evidencia.

Fallo confirmado de usuario/auditoría/commit revierte ambos. Si la conexión se
pierde durante commit, no asumir rollback: comprobar el estado por un canal
administrativo autorizado antes de decidir otra ejecución. Si ya existen cuenta
y evento, no repetir; si hay estado inconsistente, detener y revisar. No borrar
usuarios o auditoría para forzar un nuevo bootstrap. Recuperación y altas posteriores
son procesos separados, fuera del alcance actual.

## Ensayos y validación local

Se conserva --base testing --ensayar solo para bases temporales exclusivas de
localhost:5433 con el patrón del validador; siempre rollback. Ese modo no habilita
alta persistente ni salta TLS del CLI operativo. La selección testing histórica
usa sslmode prefer, por lo que no sirve como configuración operativa de alta.

[validar_bootstrap_admin.py](../../backend/herramientas/validar_bootstrap_admin.py)
crea/migra una base temporal, verifica su identidad, ejecuta pip check, Alembic
upgrade/current/heads/check y las suites unitarias/PostgreSQL/TLS, y elimina solo
su propia base comprobando ausencia. Genera un informe auxiliar JSON C.1B en el
directorio local de auditorías; esa evidencia no forma parte del historial
versionado y debe conservarse aparte. No sobrescribe evidencia histórica de C.1
ni los seis auxiliares anteriores. El contrato aprobado aún contiene una referencia
a un informe auxiliar local: su sustitución por evidencia distribuible se propone
para revisión documental, sin modificar aquí ese contrato.

Los fixtures persistentes acreditan datos SQL reales de su base aislada y construyen
la evidencia interna de destino. No exponen ese mecanismo en CLI ni certifican
TLS PostgreSQL local. Los tests demuestran persistencia real, auditoría atómica,
login interno, procesos concurrentes, escritor externo, rollback, timeout y
deadlock. Node/FastAPI TLS sigue comprobado por sus cuatro pruebas existentes;
no equivale a verificar PostgreSQL/Render o permisos del host.

## Componentes y límites

- [ServicioBootstrapAdmin](../../backend/app/seguridad/bootstrap_admin.py):
  preparar conserva captura/validación/hashing; verificar_destino acredita canal,
  servidor, esquema y principal; crear confirma usuario y evento; ensayar revierte.
- [CLI](../../backend/herramientas/bootstrap_admin.py): única entrada operativa,
  sin ejecución automática al importar. FastAPI y Alembic no la llaman.
- [ServicioAuditoria](../../backend/app/seguridad/auditoria.py) y
  [0005_actor_bootstrap](../../backend/migraciones/versiones/0005_actor_bootstrap.py):
  actor externo compatible con eventos existentes, sin alterar revisiones previas.

No se modifican login, sesiones, CSRF, cuotas, cookies, proxy o ML. Login/me/logout
HTTP siguen sin registrar; CSRF HTTP permanece cerrado sin IP acreditada. Para
AUTH-07C.2 se reutilizan Usuario, normalización, Argon2id y transacciones, pero
faltan permisos de altas posteriores y actor admin vigente dentro de la transacción.
No se inicia ese proceso automáticamente.
