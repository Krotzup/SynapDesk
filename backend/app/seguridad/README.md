# Servicios internos de seguridad

## Alcance

[ServicioSesiones](sesiones.py) y [ServicioCsrf](csrf.py) reutilizan los [modelos](../persistencia/modelos/) y las migraciones existentes. No autentican contraseñas, verifican Origin, emiten cookies ni implementan login/logout HTTP, proxy, cuotas de login o auditoría operativa. Los [fundamentos criptográficos](../../README.md#fundamentos-de-seguridad) permanecen independientes de esta orquestación.

## Transacciones y reloj

Una SQLAlchemy Session por petición o hilo. Las operaciones requieren una transacción activa. Se recomienda [transaccion_seguridad](transacciones.py), que crea el límite de commit/rollback del llamador, incluye errores de commit y rechaza anidarse sobre una transacción ya iniciada por autobegin. También pueden componerse dentro de una transacción explícita equivalente; quien la administre debe sanear errores de commit. Los métodos de servicio hacen flush pero nunca commit. No interceptar un error para continuar confirmando el mismo flujo.

Los resultados de emisión son provisionales hasta que el bloque transaccional termina correctamente. No enviar secretos, confirmar acciones externas ni emitir futuras cookies dentro del bloque. Si un commit falla, rollback y error; no reutilizar el resultado. Los resultados congelados ocultan los secretos en repr y usan SecretStr; no serializar sus campos secretos ni registrar get_secret_value().

Se bloquean usuarios por UUID ordenado mediante FOR SHARE, después la sesión mediante FOR UPDATE y finalmente sus contextos ordenados. La lectura de autorización se refresca desde PostgreSQL con populate_existing; un objeto ORM antiguo no concede acceso. Los cambios de usuario por UPDATE esperan los locks compatibles con este orden. Una futura operación que abarque varias sesiones/contextos debe coordinar todos sus locks en el mismo orden; no alternar órdenes entre servicios ni compartir Session. Los locks duran hasta terminar la transacción y cubren también la futura escritura autorizada. Se usa no_autoflush durante la operación para no persistir cambios pendientes antes de sus locks; el llamador debe delimitar cuidadosamente el trabajo de la transacción.

[reloj_postgresql](transacciones.py) consulta clock_timestamp() después de obtener los locks relevantes. A diferencia de now(), refleja el instante real aunque la transacción haya esperado. El reloj admite inyección explícita para pruebas; debe devolver una fecha con zona, convertida a UTC. No tomar tiempo de una petición cliente ni usar relojes ficticios en despliegue. Los fallos de infraestructura no equivalen a una sesión ausente.

## Sesiones

- `crear(usuario_id, presentada=...)`: primitiva posterior a verificar credenciales. Genera 32 bytes CSPRNG y devuelve su base64url canónico sin padding como SecretStr; persiste SHA-256 de los bytes originales, nunca el secreto. UUID interno y credencial son independientes.
- `consultar(credencial)`: comprueba revocación, usuario activo, rol vigente admitido y ambos vencimientos. Devuelve identidad mínima sin modelo ORM, contraseña ni digest. No renueva actividad.
- `registrar_actividad(credencial)`: operación explícita, monotónica y posterior a autorización por el llamador. No extiende el máximo absoluto. El contrato todavía propone qué peticiones cuentan como actividad, incluido el sondeo de me; no se elige esa política automáticamente.
- `revocar(credencial)`: revoca solo esa fila y sus contextos/tokens. Devuelve false si ya estaba revocada; una credencial desconocida produce el código interno correspondiente. La semántica HTTP de logout se implementará aparte.

Los límites aprobados permanecen en ocho horas absolutas desde creación y treinta minutos desde última actividad; igualdad con cualquiera de los límites significa caducidad. También se comprueba el máximo de ocho horas si una fila declara una expiración posterior. Un login futuro solo reemplazará la sesión válida presentada: la primitiva revoca esa sesión y sus contextos dentro de la misma transacción que crea la nueva. No afecta otras sesiones del usuario. Una credencial presentada ausente de la base, caducada o revocada se rechaza; la recuperación de ese caso no se inventa aquí.

La transición completa requiere que la futura orquestación verifique contraseña, contexto/token, usuario/rol y ausencia de cambio concurrente del hash; invalide el contexto anterior y confirme la auditoría antes de emitir la cookie. Crear una sesión internamente no implementa ese login ni aprueba sus detalles pendientes.

## Contextos y tokens CSRF

`crear_anonimo` devuelve un secreto independiente y guarda solo su digest. `recuperar_anonimo` exige ese secreto y comprueba revocación/expiración. `obtener_autenticado` exige una credencial de sesión válida y reutiliza el único contexto autenticado de esa sesión, creándolo cuando aún no existe bajo el lock de sesión. No revive un contexto ya revocado o vencido ni acepta el secreto anónimo como sesión.

Las operaciones de token reciben exactamente una vinculación: `anonimo=secreto` o `sesion=credencial`. No aceptan un UUID de contexto como prueba de posesión. `emitir_token` crea una prueba nueva y guarda su digest; `validar_token` comprueba vinculación, estado y vencimiento, con comparación final del digest mediante compare_digest. El token es reutilizable mientras siga válido: no es de un solo uso ni garantiza impedir repetición si se roban token y credencial. `invalidar_token` y `invalidar_contexto` revocan las pruebas correspondientes; la revocación de sesión invalida también sus contextos/tokens.

Ni obtener contexto, emitir, validar ni renovar tokens llama a registrar_actividad. El token expira como máximo al vencer su contexto; si es autenticado, se recorta también por máximo absoluto e inactividad de la sesión. El contexto autenticado conserva como tope el máximo absoluto, pero cada operación comprueba además la inactividad vigente de la sesión. Los vencimientos ya emitidos no se prolongan al renovar actividad.

Configuración en [Configuracion](../configuracion.py), con las variables habituales de BaseSettings:

| Variable | Valor inicial | Estado |
| --- | --- | --- |
| AUTH_CSRF_TOKEN_BYTES | 32; admite aumentos, no secretos inferiores a 32 bytes | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| AUTH_CSRF_TOKEN_SEGUNDOS | 600 | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| AUTH_CSRF_CONTEXTO_SEGUNDOS | 900 para contexto anónimo | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| AUTH_CSRF_MAX_TOKENS | 8 tokens vigentes por contexto | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |

Los valores se ajustan sin migración. El contexto se bloquea al contar y emitir, por lo que emisores concurrentes no superan la cuota. Los tokens vencidos o invalidados dejan de contar; no se eliminan registros ni se expulsan tokens vigentes de otras pestañas. Al saturarse se devuelve LIMITE_TOKENS; la política HTTP/espera seguirá el contrato posterior. Múltiples pestañas pueden agotar la cuota: coordinar renovación y esperar vencimiento, sin tratar la saturación como permiso para repetir una mutación. No se implementa limpieza ni se fija retención.

## Errores internos

[ErrorSeguridad y CodigoSeguridad](transacciones.py) distinguen sesión inexistente/vencida/revocada, usuario inexistente/inactivo, rol inválido, contexto inválido, token inválido/vencido, cuota de tokens, fallo transaccional e infraestructura. No transportan secretos, SQL ni mensajes del driver. Conflictos de integridad, serialización, deadlock y lock timeout se distinguen de desconexión/indisponibilidad; no se reintentan automáticamente. La capa HTTP posterior traducirá estos códigos al contrato público, conservando ApiErrorBody y la precedencia de logout. Estos códigos internos no son nuevos códigos HTTP aprobados.

## Verificación

Las [pruebas unitarias](../../pruebas/test_servicios_seguridad.py) comprueban representación opaca, validación, configuración y errores. Las [pruebas PostgreSQL](../../pruebas/integracion/test_servicios_sesion_csrf.py) usan conexiones separadas, pg_stat_activity para demostrar esperas reales de locks, relojes controlados, rollback y fallo real de commit. Comprueban cuota concurrente de ocho tokens, revocación frente a actualización de actividad, expiración durante espera, contexto invalidado durante emisión y desconexión de una conexión propia. No sustituyen transacciones por mocks.

Seguir el [procedimiento de pruebas](../../README.md#integración-con-postgresql-real) con EJECUTAR_PRUEBAS_BD=1 y una base temporal nueva en la instancia exclusiva de 5433. No utilizar synapdesk_test compartida ni desarrollo en 5432 para las pruebas que confirman cambios. Los fixtures limpian solo las filas que crearon; los recursos temporales de la ejecución deben eliminarse después de cerrar sus conexiones. La suite conserva las regresiones de persistencia y fundamentos previos. Estos ensayos son funcionales, no benchmarks ni certificación de despliegue.

## AUTH-06C: Origin público

[ServicioOrigen](origenes.py) recibe todas las ocurrencias originales de Origin en una lista o tupla. Una ausencia, `null`, múltiples ocurrencias (incluso iguales), listas combinadas, espacios/controles, credenciales, rutas, query, fragmento y representaciones ambiguas producen `ORIGIN_INVALIDO`. El adaptador futuro no debe unir ocurrencias ni seleccionar la primera. No recibe Host, X-Forwarded-Host, Referer ni un origen inferido del destino FastAPI.

`AUTH_ORIGENES_PERMITIDOS` es una lista JSON explícita, independiente de CORS. Para desarrollo local se puede configurar:

```env
AUTH_ORIGENES_PERMITIDOS=["http://localhost:3000"]
```

Se comparan esquema HTTP/HTTPS, host canónico y puerto efectivo; `https://example.invalid` equivale a `https://example.invalid:443`, pero cambiar esquema o puerto cambia el origen. Se admiten DNS ASCII e IP literales válidas, incluidas IPv6 entre corchetes. `localhost`, `127.0.0.1` y otros subdominios no se sustituyen entre sí. No hay comodines, permisos automáticos para localhost ni excepciones para clientes externos. El valor de Origin no lleva `/` final.

La lista vacía permite construir la configuración general, pero impide construir el servicio de Origin. Una lista inválida o duplicada se rechaza al cargar configuración; `ErrorConfiguracionSeguridad` distingue configuración del servidor frente a `ErrorSeguridad(ORIGIN_INVALIDO)` por entrada de solicitud. No registrar valores recibidos ni serializar entradas de errores Pydantic. El servicio estricto no selecciona qué operaciones HTTP exigen Origin: esa conexión queda para AUTH-07 conforme al contrato, sin añadir excepciones aquí.

## AUTH-06C: frontera de confianza de IP

[ServicioIpConfiable](proxies.py) implementa únicamente una primitiva independiente de un salto. Recibe el peer real del transporte y una sola dirección cliente reconstruida por un intermediario autorizado. No extrae IP de Request, no interpreta X-Forwarded-For y no deduce automáticamente cadenas de proxies. `AUTH_PROXIES_AUTORIZADOS` es una lista JSON de IP/CIDR canónicos; por defecto `[]` no autoriza ningún peer. Rechaza redes universales, comodines, hostnames, CIDR ambiguos y zonas IPv6. Una IP de cliente ausente, múltiple, malformada o procedente de otro peer produce `IP_NO_VERIFICABLE`; no se inventa una IP ni se omite silenciosamente su cuota.

La instancia devuelve únicamente [IpVerificada](proxies.py), que contiene los 32 bytes HMAC del [servicio AUTH-06A](identificadores.py), sin IP original. Canonicaliza IPv4, IPv6 y IPv4 mapeada en IPv6 antes de derivar el identificador. Cuenta e IP usan dominios HMAC distintos. Los objetos tipados son una frontera interna de código confiable, no una prueba de autenticidad de una cabecera cliente.

El despliegue debe acreditar quién puede conectar a FastAPI, impedir acceso directo que suplante al proxy y garantizar que Next.js/intermediarios descartan los metadatos de IP del navegador y reconstruyen únicamente el dato autorizado. **No pasar `Request.client` como peer real si Uvicorn u otro servidor ya lo reescribió desde cabeceras reenviadas.** Una IP en una cabecera con nombre privado no autentica a su emisor. Tampoco se considera confiable automáticamente una red privada, loopback ni un host de Vercel/Render.

Autenticidad de Next.js, redes concretas, restricción del acceso a FastAPI, metadato operativo y eventual cadena de varios saltos permanecen `PENDING_DESIGN`; no hay adaptador de despliegue, middleware ni configuración de proxy aprobados por esta implementación. No activar esta primitiva con datos cuya procedencia no pueda acreditarse.

## AUTH-06C: límites persistentes provisionales

[ServicioLimites](limites.py) requiere configuración explícita de las seis variables siguientes. No se asignan cuotas de producción por defecto:

| Variable | Requisito / uso |
| --- | --- |
| `AUTH_LIMITE_CUENTA_INTENTOS` | Entero positivo: capacidad por cuenta normalizada |
| `AUTH_LIMITE_CUENTA_VENTANA_SEGUNDOS` | Entero positivo: ventana por cuenta |
| `AUTH_LIMITE_CUENTA_BLOQUEO_SEGUNDOS` | Entero positivo: bloqueo al ocupar su última plaza |
| `AUTH_LIMITE_IP_INTENTOS` | Entero positivo: capacidad por IP verificada |
| `AUTH_LIMITE_IP_VENTANA_SEGUNDOS` | Entero positivo: ventana por IP |
| `AUTH_LIMITE_IP_BLOQUEO_SEGUNDOS` | Entero positivo: bloqueo al ocupar su última plaza |
| `AUTH_LIMITE_REINTENTOS_VERSION` | De 0 a 5 reintentos adicionales de conflicto optimista; inicialmente 2 |

Estos parámetros y la estrategia operativa son `PROVISIONAL_CONFIGURATION` / `PENDING_MEASUREMENT`. Los fixtures configuran cuotas pequeñas explícitas (cuenta 2, IP 3, ventanas 60 s y bloqueos 20 s), exclusivamente para pruebas. No se aprueban esas cifras para ningún despliegue. Todos los workers deben usar la misma configuración y la misma clave HMAC estable. Cambiar cuotas, ventanas o claves durante ventanas activas necesita una transición coordinada; esta tarea no implementa rotación ni migra automáticamente contadores.

`reservar(cuenta=..., ip=...)` usa siempre ambas identidades, exista o no el usuario. Reserva una plaza en ambas cuotas atómicamente. La política implementada es conservadora: **todo intento reservado consume capacidad hasta terminar la ventana/bloqueo, incluidos éxitos e interrupciones de infraestructura posteriores al commit de reserva**. No se devuelve capacidad por éxito ni se borran límites globalmente. Distinguir fallos de credenciales y devolver plazas de cuenta exigiría una política adicional; no se aprueba implícitamente aquí. No se implementa todavía la orquestación de login ni la cuota de bootstrap CSRF.

Cada cuota mantiene una fila vigente en el [modelo existente](../persistencia/modelos/seguridad.py), con tipos internos `cuenta` e `ip` y clave HMAC. Al vencer, se reutiliza esa fila actualizando su ventana; no constituye un historial de ventanas. El servicio toma advisory locks transaccionales ordenados por clave numérica antes de leer/crear filas, también cuando aún no existen, y después FOR UPDATE con refresco del ORM. Todos los escritores de estos tipos deben respetar este protocolo. Una duplicidad inesperada de filas se rechaza, sin escoger una arbitrariamente. Las restricciones existentes de unicidad/versionado permanecen vigentes y no hay migraciones nuevas.

Se comprueba `intentos + reservas` contra la cuota bajo esos locks, que duran hasta commit/rollback. Se adquieren todas las claves antes de leer el reloj PostgreSQL; esperar un lock no congela el tiempo. La última reserva permitida fija `bloqueado_hasta`. Los rechazos posteriores no prolongan ese bloqueo. La recuperación ocurre al alcanzar el máximo entre fin de ventana y bloqueo; las reservas abandonadas también dejan de consumir capacidad en ese momento. No se crean filas para nuevas identidades cuando la otra cuota ya rechaza el intento.

Una fila adicional del mismo modelo, tipo `reserva`, actúa como comprobante por intento: `reservas=1/intentos=0` está abierta y `reservas=0/intentos=1` está consolidada. Su digest SHA-256 vincula UUID aleatorios, identidades ya seudonimizadas y ventanas internas; no deriva de correo/IP en claro ni sustituye su HMAC. El recibo interno devuelto incluye referencias mínimas y vence al terminar la primera ventana de las dos. No es un token HTTP ni debe aceptarse del cliente.

`consolidar(reserva)` mueve contadores de reserva a intento sin reducir la suma y marca el comprobante bajo los mismos locks. Es idempotente incluso desde conexiones distintas: una segunda consolidación devuelve false. Un recibo modificado produce `RESERVA_INVALIDA`; uno vencido devuelve false y no modifica ventanas nuevas. Si el proceso desaparece, la capacidad queda ocupada solo hasta el vencimiento finito. AUTH-07 deberá tratar recibos vencidos/ya consumidos como incapaces de autorizar nuevos efectos y volver a validar todos los controles necesarios antes de emitir una sesión.

Una denegación devuelve [DecisionLimite](limites.py), con `codigo=RATE_LIMITED`, tiempo UTC observado y `reintentar_en`. `retry_after` es el techo en segundos de la diferencia entre ese plazo verificable y el reloj observado después de los locks; se toma el máximo de las cuotas que deniegan. La futura capa HTTP podrá construir 429 y Retry-After sin revelar existencia de cuentas. No se generan respuestas HTTP aquí.

Las operaciones requieren una transacción activa y una Session sin escrituras pendientes al entrar. Se recomienda reservar primero en una transacción corta y confirmar **antes** de ejecutar Argon2id fuera de locks. Consolidar será parte de otra transacción corta; debe ejecutarse antes de adquirir locks de usuario/sesión/contexto cuando se compongan servicios AUTH-06B, seguido de efectos y auditoría. No invertir ese orden. No mantener la transacción de reserva abierta durante el hash.

Los conflictos `StaleDataError` se reintentan solo dentro del savepoint del limitador, con rollback y nueva lectura; nunca se repiten Argon2, escrituras de sesión ni auditoría ajena. Al agotar el máximo se devuelve `CONFLICTO_VERSION`. Los fallos de integridad, serialización, deadlock/timeout o desconexión usan los errores saneados existentes de transacción/infraestructura, sin tratarlos como cuota agotada ni conceder acceso. Un rollback de reserva no consume capacidad; una reserva ya confirmada conserva su capacidad finita si una operación posterior falla. No hay bloqueos permanentes por indisponibilidad.

## AUTH-06C: auditoría mínima y atomicidad

[ServicioAuditoria](auditoria.py) persiste en [EventoAutenticacion](../persistencia/modelos/seguridad.py) y exige una transacción activa. Acepta enums reales de tipo/resultado/motivo, UUID internos opcionales de usuario/sesión y request ID UUID generado por servidor, además de la IP ya seudonimizada opcional. No acepta motivos libres, diccionarios de metadatos, cabeceras ni request IDs cliente sin filtrar. Los eventos incluyen login exitoso/fallido, bloqueo, creación/revocación de sesión y validaciones relevantes (Origin, IP, CSRF y sesión). Es un catálogo interno implementado para revisión, sin aprobar nuevos códigos públicos ni automatizar cuándo se emiten.

El servicio toma tiempo UTC del servidor, hace flush y devuelve [EventoPreparado](auditoria.py), cuyo UUID **es provisional hasta commit**. No escribe logs ni afirma por sí mismo que el evento quedó confirmado. No recibe ni persiste contraseñas, claves HMAC, credenciales/cookies, tokens CSRF o digest de credenciales. Los errores de persistencia se sanean mediante [operacion_bd](transacciones.py); el llamador debe usar [transaccion_seguridad](transacciones.py) o sanear también errores del commit equivalente.

- Éxito, creación/reemplazo/revocación: componer efectos de sesión y evento en la misma transacción; si el registro/commit falla, rollback de todo y ningún éxito ni cookie. No se conectan automáticamente los servicios para inventar una orquestación HTTP.
- Rechazo: terminar el rollback de la operación fallida y registrar el rechazo en otra Session/transacción explícita. Solo después de su commit puede afirmarse persistencia. Un bloqueo decidido con estado válido puede auditarse dentro de la propia transacción del límite, sin lanzar una excepción que revierta ese registro.
- PostgreSQL indisponible: propagar error de infraestructura; no inventar evento persistido. La futura capa operativa podrá emitir un aviso fijo saneado y request ID del servidor, sin valores recibidos. No registrar una revocación inexistente.

Las relaciones son opcionales; las FK existentes conservan `SET NULL` para eventos cuando se eliminan referencias. No hay purga automática, acceso HTTP, deduplicación ni plazo de retención asignado. También quedan pendientes la retención/purga de comprobantes de reserva y la capacidad global ante muchas identidades; probar cuotas por clave no certifica protección total de recursos ni presupuesto de Argon2 entre workers.

## Decisiones conservadas y pendientes

Se conservan las decisiones del [contrato](../../../docs/contratos/autenticacion-v1.md): origen público estricto, proxy público de mismo origen, persistencia de controles, minimización de secretos y reglas de sesión/CSRF ya aprobadas. AUTH-06A/B permanecen reutilizables y sus APIs existentes se preservan. Los nuevos comportamientos internos están implementados para revisión y no cambian el estado de aprobación del contrato.

Siguen pendientes cuotas/ventanas y duración definitiva de bloqueos, política diferenciada de reservas/fallos, mediciones de NAT/saturación y capacidad, autenticidad/topología de proxy y despliegue, nuevas excepciones de Origin, retención/acceso/purga de auditoría y reservas, rotación HMAC, matriz detallada de permisos, actividad exacta de sesión y cualquier nueva política de expulsión CSRF. No se comienza AUTH-07.

Las observaciones de revisión V1–V4 se conservan pendientes, sin cambiar servicios ni contratos: V1, recuperación del login ante cookie de sesión vencida/inexistente/revocada; V2, traducción HTTP de `TOKEN_INVALIDO`, `TOKEN_VENCIDO` y `CONTEXTO_INVALIDO` a `CSRF_INVALID` cuando corresponda, definiendo separadamente `LIMITE_TOKENS`; V3, calibración del consumo de cuotas por logins exitosos; V4, evaluación del máximo provisional de ocho tokens CSRF simultáneos sin aprobar una nueva expulsión. Sus decisiones se resolverán en AUTH-07 o calibración posterior.

Las [pruebas unitarias AUTH-06C](../../pruebas/test_origen_ip_limites_auditoria.py) cubren Origin, configuración, canonicalización/procedencia de IP, HMAC, redondeo de espera y rechazo de datos sensibles. Las [pruebas PostgreSQL AUTH-06C](../../pruebas/integracion/test_controles_persistentes.py) verifican límites exactos, NAT, múltiples workers/conexiones, espera real de locks, cambio de ventana, consolidación idempotente, conflictos/reintentos acotados, rollback/fallo real de commit, desconexión y atomicidad/minimización de auditoría junto a los servicios AUTH-06B. La recuperación ante conflicto se inyecta dentro de savepoints reales; la regresión de persistencia conserva además el conflicto optimista real entre conexiones.
