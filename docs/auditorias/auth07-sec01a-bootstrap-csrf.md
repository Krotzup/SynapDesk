# SYNAPDESK-AUTH07-SEC01A-PERSISTENT-CSRF-BOOTSTRAP

Fecha: 2026-11-12. Resultado: **IMPLEMENTED_AND_VALIDATED**, referido a la infraestructura interna solicitada. La emisión HTTP continúa cerrada. No certifica cuotas, rendimiento ni despliegue de producción. No se continuó con SEC-01B ni AUTH-07B.2.

## Preflight y conservación

Se leyó [CONTRIBUTING.md](../../CONTRIBUTING.md). No se encontró un AGENTS.md aplicable en los ancestros ni en las carpetas de implementación, migraciones, pruebas y documentación. Se aplicó la skill local Python fact-grounded coding, verificando código real, entorno Python, diagnósticos y pruebas ejecutadas.

| Dato | Resultado |
| --- | --- |
| Repositorio | `C:/Users/Felipe/Desktop/SynapDesk` |
| Remoto origin | `https://github.com/Krotzup/SynapDesk.git` |
| Rama | `funcionalidad/autenticacion-endpoints-v1` |
| HEAD inicial y final | `a59f506c123cfa92bafbf989ae414936ab3ffe17` |
| main local y origin/main después del fetch | `71f6b858afe304d18dd6cfe91abc7201cbe6f84f` |
| main local frente a origin/main | 0 commits de diferencia |
| HEAD frente a origin/main | 2 commits propios, 0 pendientes de incorporar |
| PR #33 | Incorporado; revisión 0003 preservada |
| Índice inicial/final | Vacío; ningún archivo agregado al índice |
| Operaciones Git incompletas | Ninguna: sin MERGE_HEAD, CHERRY_PICK_HEAD, REVERT_HEAD, rebase, sequencer, bisect ni index.lock |

El fetch necesitó ejecutarse con autorización de sandbox por la escritura de FETCH_HEAD; terminó correctamente. No hubo pull, merge, rebase, commit ni push. Existe un archivo de intercambio antiguo de mensaje de merge; no representa una operación Git activa y se dejó intacto.

El fetch actualizó dos ramas ajenas a main. `funcionalidad/proxy-mismo-origen` avanzó de `550d17e` a `658ee7e`: endurece perfiles de cookies, Set-Cookie y requestId; afecta frontend, ejemplo de entorno y contrato de transporte. Su contrato remoto todavía condiciona la IP a una frontera de confianza pendiente; no acredita IP para este backend. `mejora-recuperacion-semantica` avanzó de `174a0d3` a `ac9f025`: evaluación y documentación de ML, sin impacto en las cuotas. No se incorporaron estas ramas ni se modificaron sus componentes.

Los siete archivos locales originales conservaron exactamente estos SHA-256, comprobados al inicio y al final:

| Archivo original | SHA-256 |
| --- | --- |
| [backend/app/api/README.md](../../backend/app/api/README.md) | `6CC9105B1CB5A54393B244A834CF4370B4EE9EB46731D3FF85F8AA1E8522D3FB` |
| [backend/app/aplicacion.py](../../backend/app/aplicacion.py) | `E3975DCF97A6C26C08B9D10264798E83F6A6EA6FD106125EEF31A3F6774DB2D7` |
| [backend/pruebas/test_configuracion.py](../../backend/pruebas/test_configuracion.py) | `C6D1C6E26236DF8F014C6DD4E71D9C090FA7453A4A31A9BD3E55A954266C1682` |
| [backend/pruebas/test_http_fundamentos_auth.py](../../backend/pruebas/test_http_fundamentos_auth.py) | `BB0CB61DC7DA697AC65F43D1522537A52A9008B1CC6E9801D6FEF14E33162197` |
| [backend/app/api/csrf_auth.py](../../backend/app/api/csrf_auth.py) | `9000369434AAA117CFB113D0C62C03A01AFA3A936D4FB055494D8B47F331D974` |
| [backend/pruebas/integracion/test_csrf_http_sin_efectos.py](../../backend/pruebas/integracion/test_csrf_http_sin_efectos.py) | `1B65A69C600778836542A6AED911E88CFBDAE1C62BC08516371CD00799F7FE12` |
| [backend/pruebas/test_csrf_http_cerrado.py](../../backend/pruebas/test_csrf_http_cerrado.py) | `11729A4E20958C9B8616954605E8F48417A18E433446B1EBD79C4B408A23DCDF` |

Los cuatro primeros ya estaban modificados y los tres últimos ya eran nuevos. Los comentarios de AUTH-07B.1 que describen cuotas pendientes permanecen como evidencia de esa fase; este informe describe la infraestructura interna nueva. La conexión de emisión a HTTP sigue pendiente.

## Inspección y reutilización

Se inspeccionaron los contratos de [autenticación](../contratos/autenticacion-v1.md), [frontend/backend y errores](../contratos/frontend-backend.md) y [persistencia](../arquitectura/persistencia-inicial.md). No se modificaron contratos.

| Componente existente | Uso o decisión |
| --- | --- |
| [ServicioCsrf](../../backend/app/seguridad/csrf.py): crear_anonimo, recuperar_anonimo, emitir_token | Reutilizados sin modificar su implementación; validación de secreto, vigencia, revocación, bloqueo de contexto y límite de tokens. |
| [ContextoCsrf y TokenCsrf](../../backend/app/persistencia/modelos/csrf.py) | Se conserva el esquema y las FK RESTRICT; limpieza elimina primero tokens elegibles. |
| [ServicioIdentificadores](../../backend/app/seguridad/identificadores.py): ip_verificada | Se reutiliza su HMAC con IP canónica, mediante la abstracción existente. |
| [IpVerificada y ServicioIpConfiable](../../backend/app/seguridad/proxies.py): identificar | Única identidad IP admitida por el coordinador; pruebas construyen esta identidad con peer y red de documentación controlados. |
| [ServicioLimites](../../backend/app/seguridad/limites.py): reservar, consolidar | No se reutiliza para anónimos: exige cuenta e IP. No se modificó. |
| [LimiteAutenticacion](../../backend/app/persistencia/modelos/seguridad.py) | Independiente; ninguna cuenta ficticia ni escritura de bootstrap. |
| [ServicioAuditoria](../../backend/app/seguridad/auditoria.py): registrar | Catálogo existente preservado; no se añade un evento por rechazo anónimo. |
| [Transacciones](../../backend/app/seguridad/transacciones.py): operacion_bd, instante, reloj_postgresql | Reutilizadas para errores saneados, tiempo UTC y clock_timestamp real. |
| [Dependencias HTTP](../../backend/app/api/dependencias_auth.py): obtener_ip_verificada | Sigue rechazando toda IP HTTP; no se utilizan cabeceras ni Request.client como fuente acreditada. |
| [obtener_csrf](../../backend/app/api/csrf_auth.py) | Conserva Origin/Sec-Fetch-Site y cierre incondicional después del control de IP. |

## Persistencia y ámbitos

Se agrega [CuotaBootstrapCsrf](../../backend/app/persistencia/modelos/bootstrap_csrf.py), tabla `cuotas_bootstrap_csrf`. No se mezclan contadores ni reservas con login. Una PK compuesta `(ambito, identidad)` limita a una fila por identidad y ámbito, reciclada al cambiar la ventana. El registro contiene inicio, fin y usados; no es una tabla de eventos.

La [revisión 0004_bootstrap_csrf](../../backend/migraciones/versiones/0004_bootstrap_csrf.py) sigue a `0003_retirar_prioridad_critical`. No modifica 0001, 0002 ni 0003. Incluye CHECK para ámbitos cerrados, digest de 32 bytes, ventana positiva y contador entre 1 y 1.000.000; índice por fin para limpieza y PK para búsquedas/unicidad. Alembic check confirmó coincidencia con ORM.

| Control independiente | Identidad y momento |
| --- | --- |
| Creaciones por IP | `contextos_ip`, HMAC acreditado; reserva antes de crear. |
| Creaciones globales | `contextos_global`, identidad constante del servidor; reserva antes de crear. |
| Intentos por IP | `intentos_ip`, HMAC acreditado; incluye credencial inválida y saturación posterior. |
| Intentos globales | `intentos_global`, identidad constante del servidor; se evalúa primero. |
| Emisiones por contexto | `emisiones_contexto`, hash con dominio del UUID obtenido tras validar el secreto en BD. El UUID nunca es credencial. |
| Tokens vigentes | Conteo bajo bloqueo de contexto en ServicioCsrf; no usa filas de cuota nuevas. |

Las ventanas son discretas UTC, alineadas a múltiplos de su duración desde Unix epoch. No son ventanas deslizantes; pueden admitir ráfagas alrededor de un cambio de ventana. La cantidad máxima es independiente en cada ámbito. No hay lista de eventos por solicitud rechazada.

## Atomicidad, transacciones y concurrencia

[ServicioBootstrapCsrf.emitir](../../backend/app/seguridad/bootstrap_csrf.py) posee sus propias sesiones y transacciones. No acepta una Session de la petición, una reserva presentada por el cliente ni un UUID como autoridad.

1. **Admisión durable:** toma un advisory lock transaccional PostgreSQL estable y exclusivo de bootstrap; lee tiempo después del lock, limpia un lote y consume intentos globales y luego por IP. Para creación, consume además creación global y por IP. Confirma antes de continuar.
2. **Contexto existente:** valida el secreto con recuperar_anonimo, bajo bloqueo de fila. Reserva y confirma su cuota de emisión en otra transacción. Si la credencial no existe, expiró o fue revocada, rechaza; los intentos del paso anterior permanecen.
3. **Emisión:** en transacción independiente vuelve a validar el contexto, comprueba capacidad y llama a emitir_token. Solo devuelve secretos después del commit. Para contexto nuevo, crea contexto, su primera cuota y token en esta misma transacción.

Todos los escritores del coordinador y su limpieza respetan el mismo lock PostgreSQL. Se exige PostgreSQL y READ COMMITTED explícito; los procesos/conexiones comparten la exclusión aunque no compartan memoria. La PK refuerza la unicidad. El máximo de tokens también queda protegido por el lock de contexto existente en AUTH-06. La prueba concurrente usa ocho PID reales dentro de las transacciones de admisión; otra prueba utiliza motores y pools independientes. No se probaron procesos de sistema operativo separados; la evidencia multiproceso requerida se acredita mediante conexiones PostgreSQL independientes.

El orden de cuotas es **conservador**, no una devolución de presupuestos: si se agota un ámbito posterior, los anteriores ya consumidos se confirman. Por ejemplo, una IP sin presupuesto de creación puede consumir un intento y una reserva global de creación antes de su rechazo. El ámbito que rechaza no incrementa ni supera su máximo. Un rechazo global no inserta nuevas claves IP.

Un rollback de admisión antes del commit revierte esa admisión. Un fallo de emisión después del commit de admisión no la revierte. Para un contexto existente, tampoco revierte la cuota por contexto ya confirmada. En creación nueva, si falla la emisión se revierten contexto, token y su primera fila de cuota, conservando intentos y reservas de creación. Una caída entre fases puede desperdiciar cuota hasta el fin de la ventana; nunca genera una reserva reutilizable para emitir posteriormente sin contabilizar otro intento.

Los errores de capacidad durante una transacción no confirmada provocan rollback de esa transacción. No se promete contabilizar una admisión cuyo propio commit falló. Si se pierde la conexión durante commit, su resultado puede ser incierto: se rechaza sin devolver secretos, con presupuestos conservadores si PostgreSQL alcanzó a confirmar. No hay reintento automático que repita efectos.

## Saturación, limpieza y capacidad

Las cuotas agotadas producen `CuotaBootstrapAgotada`, distinta de ErrorSeguridad. Su retry_after es el techo de `(fin persistido - instante observado)`, no una constante. Refleja la primera espera comprobada; no garantiza que todos los demás presupuestos estén libres después. Este resultado aún no tiene traducción HTTP conectada.

La saturación de tokens conserva `LIMITE_TOKENS` de AUTH-06. No expulsa tokens válidos, no reemplaza contextos y no inventa Retry-After. PostgreSQL indisponible, configuración ausente o capacidad agotada generan `INFRAESTRUCTURA`; conflictos/bloqueos conservan la clasificación `TRANSACCION` existente. Ambos tipos de indisponibilidad se distinguen del agotamiento de cuota. statement_timeout real se probó con pg_sleep y lock_timeout con otro propietario del advisory lock; también se terminó una conexión real.

Se configuran topes de filas de cuota, contextos anónimos y tokens anónimos. Las comprobaciones y escrituras comparten el lock; al alcanzar capacidad se rechaza sin expulsar registros válidos. Estas garantías aplican al coordinador. Las primitivas internas AUTH-06 no sustituyen este control y no deben exponerse directamente para bootstrap; otros escritores deben respetar el mismo protocolo.

`limpiar()` confirma como máximo un lote por clase de registro: cuotas cuya ventana terminó; tokens anónimos expirados o invalidados; contextos anónimos expirados sin tokens restantes. También se ejecuta un lote en admisión y emisión. No elimina sesiones ni contextos autenticados. Una FK RESTRICT impide borrar un contexto con tokens. Las pruebas verifican lotes de tamaño uno, preservación de tokens válidos y drenaje de expirados.

La retención lógica es la vigencia configurada; el volumen residual también queda acotado por los topes. Para una cota temporal de eliminación física sin tráfico, el operador debe programar llamadas a limpiar y vigilar su atraso; esta tarea no configura un scheduler ni afirma que Render lo tenga. Sin llamadas, filas expiradas pueden permanecer almacenadas, aunque no admiten uso ni crecimiento ilimitado. Si el atraso consume la capacidad, el servicio falla cerrado hasta limpiar. Autovacuum, espacio físico/MVCC, frecuencia del operador y alertas requieren configuración operativa y mediciones antes de producción; los topes lógicos no certifican bytes de disco. El lock común serializa el bootstrap y puede limitar rendimiento; su escalabilidad aún no está calibrada.

Los límites de espera son explícitos por sentencia y por lock; no constituyen un deadline total de solicitud. El motor habitual añade connect_timeout y pool_timeout de cinco segundos. No se añade un bucle de reintento ilimitado.

## Configuración explícita

[PoliticaBootstrap](../../backend/app/seguridad/politica_bootstrap.py) separa todos los parámetros de la persistencia. [Configuracion](../../backend/app/configuracion.py) agrega únicamente `auth_bootstrap`, cargable como JSON `AUTH_BOOTSTRAP`. Por defecto es None; `null` también desactiva. Cada campo de la política es obligatorio, sin cuotas implícitas.

`perfil=ensayo` solo se acepta en APP_ENV=testing. `perfil=aprobado` exige que el operador suministre todos los valores tras la aprobación externa; la etiqueta no certifica esa aprobación ni activa la ruta HTTP. Se exige además la clave HMAC existente, sin valor predeterminado. No se agregaron secretos al repositorio.

Hay validación estricta de enteros, rechazo de booleanos/coerciones y campos extra. Cuotas: 1..1.000.000; ventanas/duraciones: 1..86.400 segundos; máximo de tokens: 1..1.000; lotes: 1..1.000; lock_timeout: 1..5.000 ms; statement_timeout: 1..10.000 ms. Se verifica token <= contexto, cuota por contexto >= tokens simultáneos, lock_timeout < statement_timeout y capacidad de tokens >= capacidad de contextos. La política es inmutable y el servicio copia la configuración. Datos inválidos impiden cargar configuración; ausencia o alteración inválida al construir el servicio produce cierre por infraestructura.

La duración y máximo de tokens de bootstrap se toman obligatoriamente de su política explícita, sin activar silenciosamente los defaults provisionales de AUTH-06. AUTH-06/login conservan sus propios parámetros. Todos los procesos deben compartir política, HMAC y reloj PostgreSQL; rotaciones y cambios de cuota requieren un procedimiento coordinado, drenando ventanas/contextos si corresponde. No se implementa rotación en caliente ni se aceptan versiones de HMAC elegidas por el cliente.

Estos son **solo candidatos de ensayo**, presentes en [fixtures](../../backend/pruebas/bootstrap_auxiliar.py), sin política de producción aprobada:

| Parámetro | Candidato |
| --- | --- |
| Creaciones IP / global | 60 / 900 s; 1000 / 900 s |
| Intentos IP / global | 120 / 60 s; 1500 / 60 s |
| Emisiones por contexto | 12 / 60 s |
| Tokens vigentes por contexto | 8 |
| Token / contexto | 600 s / 900 s |
| Filas cuota / contextos / tokens | 10000 / 2000 / 16000 |
| Lote / lock_timeout / statement_timeout | 100 / 1000 ms / 3000 ms |

Para ensayar, construir Configuracion con los datos explícitos del fixture y un HMAC aleatorio local; usar ip_controlada exclusivamente desde pruebas. Para configurar mediante entorno, serializar la política completa como objeto JSON en AUTH_BOOTSTRAP. No existe un modo de prueba que habilite IP confiable en HTTP.

## Frontera HTTP y decisiones pendientes

La integración segura es interna: emitir coordina los servicios AUTH-06 y confirma sus transacciones; HTTP permanece desacoplado de la emisión. La ruta real sigue en 503 SERVICE_UNAVAILABLE con bootstrap de origen válido, incluso con política completa. No emite cookies ni token, no confía en X-Forwarded-For, Forwarded, X-Real-IP, cabecera propia o loopback. Un origen rechazado conserva 403; ausencia de configuración de orígenes conserva el error previo de AUTH-07A. No se modificaron esas decisiones.

Quedan para aprobación/diseño posterior: autenticidad y aislamiento del intermediario, IP real del transporte, metadatos reconstruidos, configuración real Next.js público/Render y FastAPI privado/Render; parámetros productivos y calibración; traducción de agotamiento/saturación/capacidad al contrato de errores; cookies y recuperación de contextos. El contrato de autenticación menciona aún Vercel; el objetivo comunicado para esta tarea es Next.js en Render. Se registra la discrepancia sin editar unilateralmente el contrato ni afirmar infraestructura desplegada.

No se elige un código HTTP nuevo para saturación. La respuesta contractual futura deberá decidir si `RATE_LIMITED` cubre tanto ventanas como tokens simultáneos y qué espera puede afirmarse, o si exige una ampliación aprobada. El endpoint actual no envía Retry-After. No se modificó el catálogo general de errores.

## Validación ejecutada

[validar_bootstrap_csrf.py](../../backend/herramientas/validar_bootstrap_csrf.py) crea una base aleatoria exclusiva `synapdesk_auth07_sec01a_<uuid>`, verifica current_database, ejecuta checks y elimina exclusivamente esa base. Se invoca desde backend con el intérprete del entorno `.venv`, sin mostrar credenciales. Rechaza hosts no locales y puertos diferentes de 5433 antes de conectar. Solo lee la configuración de desarrollo para seleccionar el entorno existente; no abre una conexión a localhost:5432.

Resultado final reproducible: [auth07-sec01a-validacion.json](auth07-sec01a-validacion.json). PostgreSQL 17.11; conexión cliente exclusivamente 5433. El puerto interno que PostgreSQL informa es 5432 dentro del contenedor de pruebas; corresponde al mapeo local 5433 y no a la instancia de desarrollo. La base temporal fue eliminada y su ausencia verificada.

| Comprobación final | Resultado |
| --- | --- |
| pip check | No broken requirements found |
| Alembic upgrade head | 0001 → 0002 → 0003 → 0004, correcto |
| Alembic current / heads | 0004_bootstrap_csrf, único head |
| Alembic check | No new upgrade operations detected |
| Suite unitaria completa | 403 aprobadas |
| Suite PostgreSQL completa con EJECUTAR_PRUEBAS_BD=1 | 166 aprobadas |
| Total | 569 aprobadas, 0 fallidas, 0 omitidas |
| Regresión AUTH-06 / AUTH-07A / AUTH-07B.1 | Incluida en ambas suites completas |
| git diff --check | Correcto |
| Diagnósticos del editor, archivos nuevos de aplicación | Sin errores |
| Revisión de secretos y diff | Sin credenciales nuevas detectadas; HMAC de fixtures se genera al ejecutar |

La referencia inicial suministrada era 468 pruebas aprobadas. Se añadieron 101 casos netos. Durante el desarrollo hubo una invocación inicial desde un directorio sin import de app y ejecuciones intermedias con expectativas antiguas de head/ejemplo de entorno. Se corrigieron esos problemas y se repitieron las suites completas. No se presentan esas ejecuciones intermedias como exitosas. Todas las bases temporales creadas por el validador fueron eliminadas.

Las pruebas nuevas cubren admisión/creación, intentos, independencia de login, IP/contextos, presupuesto global, ventanas, ocho conexiones concurrentes, motores independientes, concurrencia por contexto, rollback anterior/posterior al commit de admisión, fallo real de commit, errores/restricciones PostgreSQL, contexto inexistente/arbitrario/revocado, tokens saturados, capacidad, limpieza, falta de IP/configuración y ausencia de secretos. Las pruebas HTTP adicionales confirman cierre aun con la política completa y cabeceras falsificadas.

## Diff completo e inventario

Los siete archivos originales conservan el contenido descrito en la tabla de hashes. Su diff frente a HEAD corresponde a AUTH-07B.1: registro de ruta, documentación parcial, inventarios de rutas y pruebas de cierre/ausencia de efectos; no fue reemplazado ni restaurado.

Archivos existentes modificados **por esta tarea**:

| Archivo | Explicación |
| --- | --- |
| [.env.example](../../.env.example) | Documenta AUTH_BOOTSTRAP desactivado, sin cuotas ni secretos activos. |
| [backend/app/configuracion.py](../../backend/app/configuracion.py) | Campo opcional de política explícita y su import. |
| [backend/app/persistencia/modelos/__init__.py](../../backend/app/persistencia/modelos/__init__.py) | Registro/export del nuevo modelo para ORM/Alembic. |
| [backend/pruebas/test_catalogo_prioridad.py](../../backend/pruebas/test_catalogo_prioridad.py) | Actualiza únicamente el head esperado; conserva las comprobaciones de 0003. |
| [backend/pruebas/integracion/test_migracion_inicial.py](../../backend/pruebas/integracion/test_migracion_inicial.py) | Verifica nuevo head y tabla; conserva downgrade/upgrade y comparación ORM. |

Archivos creados **por esta tarea**:

| Archivo | Explicación |
| --- | --- |
| [backend/app/seguridad/politica_bootstrap.py](../../backend/app/seguridad/politica_bootstrap.py) | Configuración estricta, obligatoria y coherente. |
| [backend/app/seguridad/bootstrap_csrf.py](../../backend/app/seguridad/bootstrap_csrf.py) | Coordinación transaccional, cuotas, capacidad, limpieza y resultados internos. |
| [backend/app/persistencia/modelos/bootstrap_csrf.py](../../backend/app/persistencia/modelos/bootstrap_csrf.py) | Tabla acotada por ámbito e identidad. |
| [backend/migraciones/versiones/0004_bootstrap_csrf.py](../../backend/migraciones/versiones/0004_bootstrap_csrf.py) | Esquema nuevo y downgrade propio; migraciones anteriores intactas. |
| [backend/pruebas/bootstrap_auxiliar.py](../../backend/pruebas/bootstrap_auxiliar.py) | Política candidata y creación controlada de IP para pruebas. |
| [backend/pruebas/test_bootstrap_csrf.py](../../backend/pruebas/test_bootstrap_csrf.py) | Validación de parámetros y cierre HTTP. |
| [backend/pruebas/integracion/test_bootstrap_csrf.py](../../backend/pruebas/integracion/test_bootstrap_csrf.py) | Atomicidad/concurrencia/errores/capacidad con PostgreSQL real. |
| [backend/herramientas/validar_bootstrap_csrf.py](../../backend/herramientas/validar_bootstrap_csrf.py) | Base temporal aislada, checks reproducibles, eliminación verificada y reporte saneado. |
| [docs/auditorias/auth07-sec01a-validacion.json](auth07-sec01a-validacion.json) | Evidencia estructurada de la ejecución final. |
| [docs/auditorias/auth07-sec01a-bootstrap-csrf.md](auth07-sec01a-bootstrap-csrf.md) | Este informe técnico y de revisión humana. |

Worktree final: 9 archivos rastreados modificados (4 originales + 5 de esta tarea), 13 nuevos (3 originales + 10 de esta tarea), índice vacío. Sin modificaciones de frontend, ML, login, contratos ni migraciones anteriores. Sin commits ni push. Los archivos temporales de ejecución fueron retirados.

## Informe solicitado

```text
TASK: SYNAPDESK-AUTH07-SEC01A-PERSISTENT-CSRF-BOOTSTRAP
INITIAL_HEAD: a59f506c123cfa92bafbf989ae414936ab3ffe17
FINAL_HEAD: a59f506c123cfa92bafbf989ae414936ab3ffe17
CURRENT_BRANCH: funcionalidad/autenticacion-endpoints-v1
ORIGIN_MAIN_HEAD: 71f6b858afe304d18dd6cfe91abc7201cbe6f84f
AUTH07B1_FILES_PRESERVED: YES; 7/7 hashes SHA-256 idénticos
BOOTSTRAP_SERVICE_IMPLEMENTED: YES; coordinador interno, emisión HTTP cerrada
PERSISTENCE_MODEL: CuotaBootstrapCsrf; tabla propia + contextos/tokens existentes
ALEMBIC_REVISION: 0004_bootstrap_csrf; posterior a 0003
RATE_LIMIT_SCOPES: contextos_ip, contextos_global, intentos_ip, intentos_global, emisiones_contexto, tokens_vigentes
ATOMICITY: PostgreSQL advisory lock transaccional + PK + lock de contexto; READ COMMITTED
CONCURRENCY: 8 conexiones reales, motores independientes y solicitudes simultáneas por contexto
ROLLBACK_BEHAVIOR: admisión confirmada sobrevive a fallo de emisión; reserva de contexto existente también
CLEANUP_POLICY: lotes explícitos; expirados/invalidados; topes de filas; operación programable, scheduler no desplegado
CONFIGURATION: AUTH_BOOTSTRAP=None por defecto; campos obligatorios; ensayo solo testing; HMAC obligatorio
PROPOSED_QUOTAS: 60/900s IP creación; 1000/900s global creación; 120/60s IP intentos; 1500/60s global intentos; 12/60s contexto; 8 tokens; token600s/contexto900s
CLIENT_IP_REQUIREMENT: IpVerificada interna; ninguna cabecera HTTP acredita IP
CSRF_HTTP_STATUS: 503 con bootstrap válido; rechazos previos de Origin conservados; sin emisión/cookies
FILES_MODIFIED: 5 por esta tarea; inventario detallado arriba; 4 modificaciones previas preservadas
FILES_CREATED: 10 por esta tarea; inventario detallado arriba; 3 nuevos previos preservados
UNIT_TESTS_PASSED: 403
POSTGRESQL_TESTS_PASSED: 166
TESTS_FAILED: 0 en validación final
TESTS_SKIPPED: 0 en validación final
ALEMBIC_STATUS: upgrade/current/heads/check correctos; head único; base temporal eliminada
SECURITY_FINDINGS: sin credenciales nuevas; serialización global y mantenimiento físico requieren calibración operativa
CONTRACT_DECISIONS_PENDING: frontera de confianza, parámetros productivos, traducción HTTP de cuotas/saturación, cookies y discrepancia Render/Vercel
WORKTREE_STATUS: 9 modificados rastreados + 13 nuevos; índice vacío; 7 originales intactos
COMMIT_CREATED: NO
PUSH_EXECUTED: NO
ERRORS: ninguno pendiente; incidencias intermedias corregidas y registradas arriba
BLOCKERS: ninguno para la infraestructura interna; HTTP continúa cerrado por diseño y decisiones pendientes
FINAL_STATUS: IMPLEMENTED_AND_VALIDATED
```

## Revisión posterior y checkpoint — SYNAPDESK-AUTH07-SEC01A-REVIEW-AND-CHECKPOINT

Esta sección corresponde a la revisión posterior del 12-11-2026. Los estados Git y «sin commits» de las secciones anteriores describen la ejecución original de SEC-01A; no representan el estado después del checkpoint.

### Preflight repetido

HEAD inicial: `a59f506c123cfa92bafbf989ae414936ab3ffe17`. Rama confirmada: `funcionalidad/autenticacion-endpoints-v1`. Origin confirmado: `https://github.com/Krotzup/SynapDesk.git`. main local y origin/main permanecen en `71f6b858afe304d18dd6cfe91abc7201cbe6f84f`, sin diferencias; el HEAD inicial ya contiene main. Índice inicial vacío y ninguna operación Git incompleta. CONTRIBUTING leído de nuevo; sin AGENTS.md aplicable encontrado.

El nuevo fetch únicamente descubrió `origin/funcionalidad/prototipo-rag-llm`, head `eafd714`, con cambios en dos archivos del prototipo RAG de ML. No afecta autenticación ni exige conciliación. Las ramas remotas conocidas del proxy y recuperación semántica no avanzaron en este fetch. No se fusionaron ramas.

Se inventariaron 9 archivos rastreados modificados y 13 nuevos: 22 en total. Estos son sus **hashes de preflight**, anteriores a actualizar este informe y repetir la evidencia JSON; no se presentan como hashes finales de esos dos documentos:

| Archivo pendiente | SHA-256 inicial del checkpoint |
| --- | --- |
| [backend/app/api/csrf_auth.py](../../backend/app/api/csrf_auth.py) | `9000369434AAA117CFB113D0C62C03A01AFA3A936D4FB055494D8B47F331D974` |
| [backend/app/persistencia/modelos/bootstrap_csrf.py](../../backend/app/persistencia/modelos/bootstrap_csrf.py) | `250630C527992FA8C7024EF5EDE87FB9D05FA848260241FA032145722BC798A3` |
| [backend/app/seguridad/bootstrap_csrf.py](../../backend/app/seguridad/bootstrap_csrf.py) | `6064A0EDB62970B483A6805EB5EC5F959FFD64CA7052607415B3BFEDF16C3234` |
| [backend/app/seguridad/politica_bootstrap.py](../../backend/app/seguridad/politica_bootstrap.py) | `2B47DC4E82B2CFDBC1FDF9B77DD5470905134DA8938FE1FA1E1A77FB3399853E` |
| [backend/herramientas/validar_bootstrap_csrf.py](../../backend/herramientas/validar_bootstrap_csrf.py) | `75D672CD54E4AAF1D3A1769196401DF6355CCE0E7DCF48F1F3AF8073B7AE3A42` |
| [backend/migraciones/versiones/0004_bootstrap_csrf.py](../../backend/migraciones/versiones/0004_bootstrap_csrf.py) | `7DF3BA335B682398C0176C8906F18F3D490BFD4E36872161003D3F3E02C6CB20` |
| [backend/pruebas/bootstrap_auxiliar.py](../../backend/pruebas/bootstrap_auxiliar.py) | `03F8078B436E1D5E506E7773FB433C994C806E43E96654F7EE56CCB47A636517` |
| [backend/pruebas/integracion/test_bootstrap_csrf.py](../../backend/pruebas/integracion/test_bootstrap_csrf.py) | `08F3C7358245D51E9C6322EC444E87018BC6963BCDA79363C4D16481E65C3E9A` |
| [backend/pruebas/integracion/test_csrf_http_sin_efectos.py](../../backend/pruebas/integracion/test_csrf_http_sin_efectos.py) | `1B65A69C600778836542A6AED911E88CFBDAE1C62BC08516371CD00799F7FE12` |
| [backend/pruebas/test_bootstrap_csrf.py](../../backend/pruebas/test_bootstrap_csrf.py) | `20035F9775FD0E6688402902BED0B90A79E5B2208D9879F5D24C723EC08604EF` |
| [backend/pruebas/test_csrf_http_cerrado.py](../../backend/pruebas/test_csrf_http_cerrado.py) | `11729A4E20958C9B8616954605E8F48417A18E433446B1EBD79C4B408A23DCDF` |
| [docs/auditorias/auth07-sec01a-bootstrap-csrf.md](../../docs/auditorias/auth07-sec01a-bootstrap-csrf.md) | `268584E7EF4B9CF6E3B7D94C777391AD76AC21A8C4D4272F9CA8270C0E688173` |
| [docs/auditorias/auth07-sec01a-validacion.json](../../docs/auditorias/auth07-sec01a-validacion.json) | `855C074DE3269458A1CB05EDD5ADC6EC83572D7502D919B7043790BE3FD2DA8B` |
| [.env.example](../../.env.example) | `F16382FA577AA0B5C9AE791F1FE16E293FB452865BBD9F2CE13A1D94045A03AA` |
| [backend/app/api/README.md](../../backend/app/api/README.md) | `6CC9105B1CB5A54393B244A834CF4370B4EE9EB46731D3FF85F8AA1E8522D3FB` |
| [backend/app/aplicacion.py](../../backend/app/aplicacion.py) | `E3975DCF97A6C26C08B9D10264798E83F6A6EA6FD106125EEF31A3F6774DB2D7` |
| [backend/app/configuracion.py](../../backend/app/configuracion.py) | `312A1CFDE205BBA7D6DEA0798CB33AFDD0A97848EB1DFF517BE3480CE1C3B576` |
| [backend/app/persistencia/modelos/__init__.py](../../backend/app/persistencia/modelos/__init__.py) | `E8B8AF104B498C54145564579E13A8274F3D7635323FCD6D367016793FA309BE` |
| [backend/pruebas/integracion/test_migracion_inicial.py](../../backend/pruebas/integracion/test_migracion_inicial.py) | `5E9BBD42EB74C158F39F769722998EEC752C3F79038481FF31882B5A3334EB2C` |
| [backend/pruebas/test_catalogo_prioridad.py](../../backend/pruebas/test_catalogo_prioridad.py) | `48FD787028FDF65EC8F1F1BFDCA63BAA56663B8FE0BC08D8B825140E99908399` |
| [backend/pruebas/test_configuracion.py](../../backend/pruebas/test_configuracion.py) | `C6D1C6E26236DF8F014C6DD4E71D9C090FA7453A4A31A9BD3E55A954266C1682` |
| [backend/pruebas/test_http_fundamentos_auth.py](../../backend/pruebas/test_http_fundamentos_auth.py) | `BB0CB61DC7DA697AC65F43D1522537A52A9008B1CC6E9801D6FEF14E33162197` |

Se registraron asimismo hashes privados para la configuración local del backend, el entorno local del frontend y los ajustes del editor, sin copiar sus contenidos al informe ni prepararlos para commit. Estos tres recursos privados están excluidos de Git y no forman parte de la evidencia publicada. Su conservación se comprueba antes y después de los commits. Los 20 archivos restantes del inventario mantienen sus hashes iniciales: no se modificaron código, tests, migraciones ni ejemplos durante esta tarea. Solo se actualizan el informe y la evidencia de validación.

### Separación revisada

El primer commit local es `8238d497ad4fb97c5732f2651e97451ff992ca09`: **feat(auth): prepara endpoint HTTP CSRF con rechazo seguro**. Incluye exactamente los siete archivos originales listados en la tabla de conservación AUTH-07B.1. Se revisó íntegramente su diff preparado; no mezcla configuración, modelo ni migración SEC-01A. Una copia temporal de HEAD inicial con únicamente esos siete archivos pasó por separado **339 pruebas unitarias**, sin código SEC-01A. La copia temporal fue eliminada.

El segundo checkpoint corresponde exclusivamente a los quince archivos SEC-01A ya inventariados en la sección «Diff completo e inventario», con el mensaje **feat(auth): incorpora cuotas persistentes de bootstrap CSRF**. Incluye configuración, modelo, migración, coordinador, pruebas, herramienta e informe/evidencia SEC-01A. Su SHA se informa al concluir la operación; no se intenta insertar el hash del propio commit en su contenido.

Los dos ajustes de inventario de rutas pertenecen a AUTH-07B.1. Los ajustes de head de Alembic pertenecen a SEC-01A. No se encontró un archivo que requiriera separar fragmentos incompatibles. No se modificaron contratos ni se implementó funcionalidad adicional en esta revisión.

### Revisión técnica y de seguridad

| Control | Conclusión y límite comprobado |
| --- | --- |
| IP acreditada | La ruta no toma IP confiable de ninguna cabecera ni del peer reinterpretado; obtener_ip_verificada sigue rechazando. IpVerificada es una abstracción interna, no un dato deserializado desde HTTP. |
| Cuotas de ensayo | Solo testing admite perfil ensayo. Ausencia de política cierra el servicio; aprobado exige valores explícitos y no equivale a aprobación externa automática. |
| Bootstrap cerrado | La configuración completa tampoco activa emisión HTTP; se preservan 503, no-store y ausencia de Set-Cookie. |
| Rollback posterior | Los intentos y reservas de creación confirmados sobreviven a fallo de emisión; para contexto existente sobrevive también su reserva propia. La admisión cuyo propio commit falla no se declara contabilizada. |
| Concurrencia | Locks PostgreSQL comunes, READ COMMITTED, PK y bloqueo de contexto respaldados por ocho conexiones reales y motores independientes. No se afirma una prueba con procesos de SO distintos. |
| Identificadores arbitrarios | Se valida el secreto opaco contra BD antes de derivar identidad por UUID; inexistencia, revocación o saturación no crean un reemplazo. |
| Limpieza | Filtros explícitos de anonimato/expiración, lote y FK; no borra sesiones ni contextos autenticados. Las pruebas usan exclusivamente base temporal exclusiva. |
| Información sensible | Errores saneados y secretos fuera de repr; HMAC de IP y secretos de fixtures generados al ejecutar. Revisión de adiciones sin credenciales nuevas. |
| Regresión | AUTH-06, AUTH-07A y AUTH-07B.1 incluidos en suites completas repetidas, sin fallos. |
| Operación futura | No hay scheduler desplegado, calibración de throughput ni aprobación de cuotas productivas. No deben exponerse primitivas AUTH-06 saltando el coordinador. |

### Migración 0004 y validación repetida

down_revision es exactamente `0003_retirar_prioridad_critical`; las revisiones 0001, 0002 y 0003 permanecen intactas. Tabla, PK compuesta, índice por expiración y cuatro CHECK coinciden entre SQLAlchemy/Alembic y PostgreSQL 17.11.

Se repitió [la validación completa](auth07-sec01a-validacion.json) sin cambios funcionales: **403 unitarias + 166 PostgreSQL = 569 aprobadas**, **0 fallidas, 0 omitidas**. pip check y Alembic upgrade/current/heads/check correctos. EJECUTAR_PRUEBAS_BD=1 para integración. La base temporal exclusiva fue eliminada y su ausencia verificada.

Adicionalmente se ejecutó en otra base temporal el recorrido **0003 → 0004 → 0003 → 0004**, sembrando un contexto, un token y un contador de cuota. El downgrade conserva el contexto/token (1/1), elimina únicamente la tabla nueva y pierde el contador; el upgrade posterior la reconstruye vacía y Alembic check vuelve a pasar. La base adicional también fue eliminada.

**Riesgo de downgrade:** borra el presupuesto persistido y una reaplicación reinicia cuotas. Cualquier reversión operativa requiere detener el bootstrap y coordinar un enfriamiento/restauración conforme a la política aprobada; no debe usarse downgrade/upgrade como reinicio de cuotas con emisión habilitada. No se ejecutó migración alguna sobre la instancia de desarrollo. Todas las conexiones de prueba usan el puerto cliente 5433; el puerto 5432 informado dentro del contenedor no es una conexión al servidor de desarrollo.

Las comprobaciones ligeras incluyen diff --check, diagnósticos, revisión de rutas preparadas, secretos y conservación de hashes. No hay cambios de código después de las 569 pruebas: solo este apéndice y la evidencia JSON de la repetición.

### Preparación de SEC-01B y AUTH-07B, sin implementarlas

El [PR #30](https://github.com/Krotzup/SynapDesk/pull/30) tiene head **658ee7e78c6715309a952875e4c1072eb5efef91**, confirmado por refs/pull/30/head. No está incorporado en esta rama ni en origin/main. La existencia de refs/pull/30/merge es una referencia sintética y no prueba que se haya fusionado. No se abrió un PR nuevo.

| Área futura | Archivos concretos y dependencia |
| --- | --- |
| Acreditación backend | [dependencias_auth.py](../../backend/app/api/dependencias_auth.py), [proxies.py](../../backend/app/seguridad/proxies.py), [configuracion.py](../../backend/app/configuracion.py), [aplicacion.py](../../backend/app/aplicacion.py), [infraestructura](../../infra/README.md). Definir peer real, autenticidad del servicio y metadatos reconstruidos antes de adaptar obtener_ip_verificada. |
| Emisión HTTP posterior | [csrf_auth.py](../../backend/app/api/csrf_auth.py), [bootstrap_csrf.py](../../backend/app/seguridad/bootstrap_csrf.py), [cookies_auth.py](../../backend/app/api/cookies_auth.py), [respuestas_auth.py](../../backend/app/api/respuestas_auth.py), [errores_auth.py](../../backend/app/api/errores_auth.py). Requiere confianza y decisiones de respuesta/cookies aprobadas; commit antes de emitir cookies. |
| Proxy PR #30 | [backend-proxy.ts remoto](https://github.com/Krotzup/SynapDesk/blob/658ee7e78c6715309a952875e4c1072eb5efef91/frontend/src/lib/backend-proxy.ts), Route Handler de ruta dinámica en frontend/src/app/api/v1 y transport/client.ts, transport/server.ts de esa revisión. Esos archivos se inspeccionaron en la referencia remota; no se crearon en el checkout. |
| Cliente disponible | [auth.ts](../../frontend/src/services/auth.ts), [csrf.ts](../../frontend/src/lib/csrf.ts), [auth-sync.ts](../../frontend/src/lib/auth-sync.ts), [AuthProvider.tsx](../../frontend/src/components/auth/AuthProvider.tsx), [api.ts](../../frontend/src/lib/api.ts). Ya existen consumo de DTO, coordinación de CSRF/cambios de sesión y estados de interfaz; no acreditan autenticación real. |
| Pruebas que ampliar después | [test_origen_ip_limites_auditoria.py](../../backend/pruebas/test_origen_ip_limites_auditoria.py), [test_http_fundamentos_auth.py](../../backend/pruebas/test_http_fundamentos_auth.py), [test_csrf_http_cerrado.py](../../backend/pruebas/test_csrf_http_cerrado.py), [test_bootstrap_csrf.py](../../backend/pruebas/integracion/test_bootstrap_csrf.py); pruebas del proxy incluidas en PR #30 y una futura suite de integración del canal completo. |

El proxy inspeccionado usa destino de servidor, allowlists de cabeceras/cookies, Origin sin fabricar, múltiples Set-Cookie del perfil activo, no-store, rechazo de redirecciones, timeout y requestId de servidor. **Descarta X-Forwarded-*, Forwarded, X-Real-IP y X-SynapDesk-Client-IP del navegador; todavía no construye una IP acreditada.** Incorporar el transporte no reemplaza SEC-01B. La red privada de Render por sí sola tampoco identifica al usuario original.

**Decisiones aprobadas:** FastAPI como autoridad; sesiones opacas y CSRF sincronizado persistentes; navegador mediante mismo origen; Origin estricto en mutaciones; cookies necesarias y secretos solo de servidor; no-store; mutaciones V1 mediante fetch cliente; logout idempotente con los controles documentados. La aprobación no prueba implementación/deploy.

**Implementación existente:** servicios AUTH-06 de sesiones, contraseñas/cuentas, origen, identificadores, límites de login y auditoría; utilidades HTTP AUTH-07A; endpoint parcial cerrado AUTH-07B.1; coordinador persistente SEC-01A. Proxy/SSR existe en la rama del PR #30, fuera de esta rama; frontend local tiene componentes de consumo y mocks. No existen aquí endpoints reales login/me/logout.

**Propuestas/decisiones pendientes:** mecanismo exacto de autenticidad servicio-a-servicio, aislamiento de acceso directo, fuente de IP real y su cadena de intermediarios, cabecera o metadato protegido y tratamiento de duplicados/IPv4/IPv6; rotación/revocación de credenciales internas; origen y perfiles de cookies por entorno; cuotas productivas, errores/Retry-After/saturación, limpieza programada y observabilidad. La arquitectura objetivo Next.js público Render/FastAPI privado Render requiere conciliar la referencia Vercel del contrato mediante revisión humana. No se aprobó ni escogió unilateralmente ningún mecanismo nuevo.

**Pruebas mínimas de SEC-01B:** cliente directo y servicio no autorizado rechazados; IP ausente/ambigua/cadena no verificable rechazada; suplantación de cabeceras desde navegador descartada; identidad del peer real no alterada por Uvicorn; canal autorizado entrega solo la IP reconstruida; IP canónica estable IPv4/IPv6; secreto interno incorrecto/ausente/revocado, si ese mecanismo llegara a aprobarse; propagación segura de Origin/cookies y no-store; fallo del verificador o PostgreSQL conserva 503 y ausencia de efectos; prueba end-to-end Next.js → backend privado → PostgreSQL y prueba de bloqueo del acceso directo. No basta con mocks de request.client o una cabecera propia.

**Recomendación concreta de paralelismo, pendiente de asignación humana:** Valentina y América pueden repartir dos frentes sin esperar una emisión HTTP exitosa: (1) revisar/probar el transporte del PR #30 y preparar el consumo frontend con contratos/fixtures de 403, 429 propuesto y 503, cookies, múltiples pestañas y cero reintento de mutaciones con resultado incierto; (2) preparar y probar la orquestación backend AUTH-07B con dependencias internas controladas, DTO, límites, transacciones y cookies tras commit, manteniendo las rutas reales cerradas. La lectura de identidad /me puede diseñarse y probarse con sesiones internas sin extracción IP, conservando no-store y la política de actividad por aprobar. Login/logout y emisión real no se habilitan hasta resolver confianza, políticas y gates correspondientes. Las pruebas locales controladas no autorizan un bypass de producción. Este reparto es una propuesta, no atribuye responsabilidades previamente acordadas ni inicia desarrollo.

No hubo push, PR ni fusión. El cierre del checkpoint y los SHA de ambos commits se informan en la respuesta de esta tarea después de verificar el worktree.
