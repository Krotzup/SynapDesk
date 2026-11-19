# CI de backend y autenticación

El [workflow Backend Auth CI](../../.github/workflows/backend-auth-ci.yml) está
preparado para PR dirigidos a main y push a main. No usa filtros de rutas: un
cambio exclusivo de código auth, tests, migraciones, contratos o del workflow
ejecuta los cinco jobs. También se ejecuta para otros cambios hacia main, lo
que mantiene disponibles los mismos checks para protección de rama y evita
omisiones por listas parciales de rutas o límites del diff de GitHub.
Los PR Draft no se excluyen. GitHub puede exigir aprobación de una primera
ejecución desde un fork según la configuración del repositorio.

Se declaran los tipos `opened`, `synchronize`, `reopened`, `edited` y
`ready_for_review`: conservan los eventos predeterminados y cubren cambiar la
base hacia main o sacar un PR de Draft. No hay filtros de paths ni condiciones
para saltar jobs. No se añade `workflow_dispatch` ni ejecución de un SHA libre.
La configuración no es retroactiva: tras integrar este arreglo a main mediante
el flujo autorizado, un PR ya abierto requiere otro evento permitido (por
ejemplo, actualizar su descripción). Comprobar la ejecución sobre su head y
la previsualización de integración; un run de main sin tickets no valida ese PR.

## Checks estables

| Job | Nombre visible | Comando desde backend |
| --- | --- | --- |
| unitarias | Backend Auth / Unitarias | `python -m herramientas.ci_backend unitarias` |
| postgresql | Backend Auth / PostgreSQL | `python -m herramientas.ci_backend postgresql` |
| tls | Backend Auth / TLS | `python -m herramientas.ci_backend tls` |
| alembic | Backend Auth / Alembic | `python -m herramientas.ci_backend migraciones` |
| documentacion | Backend Auth / Documentación y contratos | `python -m herramientas.validar_ci documentacion`, `secretos` y `workflow` |

Los jobs son independientes y obligatorios: no usan `if`, `needs` ni
`continue-on-error`. Cada uno tiene un límite exterior de 15 minutos.
El [ejecutor](ci_backend.py) propaga errores de procesos, timeout, cero pruebas,
fallos y casos omitidos; no permite convertir una integración no configurada
en un job verde con skips. Los XML de pytest son temporales y se validan antes
de su eliminación. No se suben artefactos ni se guardan credenciales en ellos.

Se usa Python 3.12, igual que la validación existente, y las
[dependencias de desarrollo](../requirements-dev.txt) con versiones exactas.
Todos los jobs ejecutan `pip check`. Unitarias/PostgreSQL/TLS/Alembic comprueban
importaciones reales y configuración aislada; el cliente instalado del proyecto
es `httpx2`. PyYAML 6.0.3 es una dependencia adicional exclusiva de desarrollo:
permite inspeccionar con carga segura el YAML real, sus triggers y controles.
Se rechazan claves YAML duplicadas. No se añadieron dependencias productivas.

## Aislamiento PostgreSQL

PostgreSQL y Alembic usan servicios independientes en runners hospedados
`ubuntu-24.04`, sin volúmenes persistentes ni endpoints externos. La imagen es
`pgvector/pgvector:0.8.6-pg17-bookworm`, con la misma versión exacta del
[compose existente](../../compose.yaml). El healthcheck comprueba el usuario y
la base de control del servicio. El puerto del servicio se publica únicamente
en `127.0.0.1:5433`, manteniendo las guardas locales sin introducir excepciones.
Se verifica PostgreSQL, vector y el head único `0007_recomendaciones_rag`.

El usuario `synapdesk_ci` y la base `synapdesk_ci_control` pertenecen solo al
servicio efímero. Su contraseña se deriva de los identificadores públicos de
ejecución/intento: es una credencial de ensayo pública, distinta por ejecución,
sin relación con secretos operativos. Se enmascara antes de transferirla por
`GITHUB_ENV`. No se usan GitHub Secrets, configuraciones privadas ni recursos
de desarrollo/producción. El nombre principal es un marcador no utilizado.

Se reutiliza [base_propia](arnes_http_seguro/infraestructura.py): verifica
identidad y loopback:5433, crea una base aleatoria con prefijo propio, prepara
vector y ejecuta `upgrade head`, `current`, `heads` y `check` desde esquema
vacío. Las pruebas PostgreSQL reciben exclusivamente esa base. Al salir se
terminan solo sus sesiones, se elimina esa base y se comprueba su ausencia.
El servicio completo desaparece con el job. No se ejecuta Docker local ni se
detienen contenedores compartidos. La suite PostgreSQL excluye únicamente el
archivo TLS, ejecutado por separado.

Los temporales y el XML de pytest usan un `TemporaryDirectory` separado de los
recursos del arnés: pytest puede crear enlaces `*current` en Linux. Se elimina
ese árbol propio sin seguir sus enlaces y se comprueba su ausencia antes de
declarar `pytest_temporary_deleted`. La guarda del arnés conserva el rechazo de
cualquier symlink/junction en sus recursos, incluso si se llama `*current`.
Un error de borrado o un temporal residual hace fallar el job; también se
ejecutan el cierre de la base y la limpieza de recursos por sus bloques finales.

## Autenticación y TLS

Las suites existentes cubren Argon2id, sesiones, expiraciones, CSRF, Origin,
SEC-01A/01B, cuotas, bootstrap, admin/agent, autorización transaccional y
auditoría. Incluyen las 182 regresiones h11 de F1, sin duplicarlas.
CSRF HTTP debe seguir cerrado con 503 y login/me/logout sin registrar con 404;
estas regresiones forman parte de unitarias e integración. P4 continúa pendiente
de implementación y C01–C09 pendientes; el workflow no aprueba ni implementa
esas capacidades.

El [archivo TLS existente](../pruebas/integracion/test_intermediario_tls.py)
produce cuatro casos: TLS autenticado/duplicados/concurrencia/CSRF cerrado,
rechazo de CA o hostname incorrectos y dos variantes de rechazo de HTTP con
protocolo falsificado. OpenSSL genera certificado/clave temporal de localhost;
la confianza se limita al contexto TLS del cliente de ensayo. Se limpian
certificados, listeners y directorios propios, sin desactivar verificación.
Las credenciales SEC-01B se generan en las fixtures y no se usan para usuarios.
Esto no acredita IP, TLS ni operación en Render.

## Documentación, contratos y secretos

El [validador](validar_ci.py) revisa Markdown de backend, contratos,
arquitectura, CONTRIBUTING, configuración documental de GitHub y el informe
SEC-01A versionado. Comprueba destinos presentes en Git, anclas de encabezados
ATX/Setext (Unicode y repetidas), anclas HTML explícitas y ejemplos JSON. Ignora
enlaces/encabezados dentro de código cercado y no hace solicitudes a URLs
externas. Valida además los JSON versionados y el estado vigente de P1–P10,
C01–C09, P4 y los campos de ApiErrorBody/AuthUser. Los cambios contractuales
futuros deben actualizar conscientemente estas comprobaciones.

El control de secretos cubre backend/auth, contratos, arquitectura, CI,
infraestructura PostgreSQL y archivos de entorno. Inspecciona el árbol y los
blobs del intervalo `CI_BASE_SHA..HEAD`, con checkout de historial completo;
no ignora directorios de tests. Detecta claves privadas, tokens GitHub/AWS,
URLs PostgreSQL con contraseña, variables sensibles y archivos privados.
Sus excepciones son exclusivamente tres líneas públicas exactas de la plantilla
de entorno; una coincidencia en otro archivo falla y requiere revisión humana.
Solo informa ruta, línea y regla, sin el contenido. Es un control por patrones,
no una garantía exhaustiva ni un escaneo del código ML ajeno a este incremento.

`actionlint` 1.7.11 verifica sintaxis, esquema y expresiones del workflow; el
binario oficial Linux se fija con SHA-256. Checkout y setup-python también
usan SHA de commit completos. Se exige `contents: read`, checkout sin persistir
credenciales, runners hospedados y ausencia de `pull_request_target`, despliegues
y pasos que publiquen artefactos. No se modificó el workflow de ML.

## Repetición y alcance pendiente

Con el entorno elegido, instalar las dependencias de desarrollo, ejecutar
`python -m pip check` y después los comandos de la tabla. PostgreSQL y Alembic
requieren la configuración explícita de testing en loopback:5433 y crean sus
propias bases; nunca deben apuntarse a infraestructura externa. En unitarias y
TLS no se necesita PostgreSQL.

Antes de versionar archivos nuevos, el validador admite `--incluir ruta ...`
para un inventario de candidatos explícito, sin preparar el índice ni considerar
versionables los auxiliares por existir localmente. `secretos --base SHA` permite
repetir el intervalo histórico fuera de Actions. Los
[tests de guardas](../pruebas/test_ci_backend.py) verifican fallos y omisiones.

El arnés completo Node/Next.js de AUTH-07D.2 no es un check obligatorio: necesita
componentes y fixtures de PR #30/#32 fuera de este runner. Sus 75 casos locales
reportados son evidencia histórica; sus guardas Python sí siguen en unitarias.
Consultar su [procedimiento reproducible](arnes_http_seguro/README.md). CI no
depende de los informes auxiliares excluidos ni presenta pruebas locales como
evidencia Render.

Una validación local del YAML y de estos comandos no demuestra una ejecución
exitosa de GitHub Actions. Tras un commit/push posteriormente autorizado, habrá
que comprobar cinco checks reales, logs, aislamiento y limpieza Linux. Solo
después corresponde configurar estos nombres como requeridos en la protección
de main. Este incremento no configura esa protección, aprueba ni fusiona el PR.

Referencias oficiales: [servicios PostgreSQL en Actions](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers),
[sintaxis y permisos de workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
y [release actionlint 1.7.11](https://github.com/rhysd/actionlint/releases/tag/v1.7.11).
