# AUTH-07D.3 — compatibilidad, aceptación e integración

**CONTRACTS_FORMALIZED en el alcance expresamente aprobado.** Revisión del
13-11-2026. Formalización documental; no cambia código, registra rutas ni
acredita Render. Las decisiones adicionales señaladas como PROPUESTA siguen
pendientes. La habilitación de tráfico conserva sus condiciones independientes.

Fuentes normativas: [autenticación V1](autenticacion-v1.md),
[HTTP V1](autenticacion-http-adaptadores-v1.md),
[contrato general y errores](frontend-backend.md),
[SEC-01B](comunicacion-interna-segura-v1.md) y
[responsabilidades y especificaciones PR30/PR32](integracion-http-pr30-pr32-v1.md).
La [matriz anterior D.1/D.2](auth07d2-matriz-decisiones-y-plan.md) queda como
antecedente histórico, sustituido en sus decisiones por D.3.

## 1. Evidencia y límites

Backend revisado: `2c52d78d1d71694ed3b01521bd3210dd7906a8db`, padre
`f0814238eb470f830d35a1255a7089d8d52623fe`. Main remoto consultado:
`6ce66a7221eafa3bd04f29c4e9bac7ca97df3f1b`; su único cambio no integrado es
PR #29, interfaz del asistente con mocks, sin transporte de autenticación.
No se integraron cambios remotos. Los checkpoints anteriores son ancestros.

La [guía reproducible D.2](../../backend/herramientas/arnes_http_seguro/README.md)
conserva el resumen histórico y la matriz de casos del transporte. Los informes
detallados son auxiliares locales excluidos de Git, sin ser una dependencia de
lectura de este contrato. Resultado histórico declarado: 75 casos del arnés;
validación separada de 660 unitarias
y 351 de integración, que ya incluyen cuatro TLS. Total histórico: 1086, cero
fallos y cero omitidas en la validación final. D.3 no presenta esos resultados
como una nueva ejecución.

Se ejecutaron Node 24.22.1, Next 16.3.4 (dev --webpack), Uvicorn/FastAPI y
PostgreSQL 17.11 con esquema 0006. CA y hostname fueron verificados en
Node→FastAPI. Next recibió HTTP de loopback desde un cliente Node, no un
navegador. No se certificaron build productivo, cookies Secure en navegador,
TLS del ingreso público, despliegue o procedencia IP Render.

Tres fuentes exactas de PR30 se ejecutaron sin modificar algoritmos: helper
proxy, Route Handler y SSR. El éxito SEC-01B a través de Next procede de
`/ensayo-canal`, **sustituto de prueba**, no del PR30 real. Las sondas FastAPI
están en una aplicación separada; contextos persistentes se crean internamente
y las cookies de emisión son marcadores, no sesiones emitidas por HTTP.
PR32 se inspeccionó estáticamente; no se ejecutó su búsqueda/ML en el arnés.

## 2. Políticas HTTP aprobadas P1–P10

| Política | Regla formalizada | Aplicación y estado |
| --- | --- | --- |
| P1 | Rechazar cookies malformadas, duplicadas o de perfiles mezclados, sin convertirlas en anónimas. | Backend estricto; PR30 incumple dos casos reproducidos. Clasificación pública exacta de CookieAmbigua pendiente. |
| P2 | Sin recuperación automática de sesión vencida, revocada o inválida. | La sesión presentada selecciona su rama. Limpieza explícita en logout no equivale a recuperación ni concede identidad. |
| P3 | /me no renueva inactividad ni expiración absoluta. | ServicioConsultaSesion ya cumple: ocho horas absolutas y treinta minutos de inactividad no cambian. |
| P4 | Logout puede revocar una sesión verificable de cuenta inactiva con sus controles. | Implementada internamente para revocación y validada en testing aislado. No concede identidad activa, recursos o contexto CSRF nuevo. |
| P5 | Origin, servicio, IP, sesión y CSRF son independientes, según endpoint. | Bearer no acredita usuario/IP; no añadir IP o cuotas de login a me/logout por analogía. |
| P6 | Conservar ApiErrorBody, requestId y no-store. | Cuatro campos dentro de error; sin name ni requestId adicional en AuthUser. |
| P7 | Sin cuotas de ensayo en producción; cierre si falta política necesaria aprobada/configurada. | No modificar consumo de reservas o umbrales actuales mediante documentación. |
| P8 | Presupuestos por operación/tramo; sin reintentos automáticos de escrituras. | Sustituye el reenvío automático de mutación tras renovar CSRF; no fija cifras productivas. |
| P9 | IP original únicamente desde cadena acreditada. | Render pendiente de evidencia; ni bearer, red privada, loopback o cabecera arbitraria bastan. |
| P10 | Falta de control obligatorio mantiene la operación cerrada. | Sin excepciones por localhost/desarrollo ni rutas parciales para probar. |

P8 conserva la renovación preventiva coordinada de CSRF, pero obtener una prueba
nueva no reenvía automáticamente la escritura. Las políticas anteriores de
altas internas AUTH-07C.1/C.2 y su entrega externa de credenciales no cambian.

## 3. Matriz de compatibilidad con el backend

| Requisito | Contrato / aprobación | Comportamiento observado y fuente | Estado | Corrección requerida / responsable |
| --- | --- | --- | --- | --- |
| Identidad | AuthUser dentro de user: id, email, role | [DTO](../../backend/app/api/esquemas_auth.py) y proyección explícita; extra=forbid | CONFORME INTERNO | Adaptar consumidores Next, sin agregar name. |
| Cookies estrictas | P1, sin identidad ambigua | [lector](../../backend/app/api/cookies_auth.py) y [extraer_cookies](../../backend/app/api/adaptadores_auth.py) conservan originales y rechazan mezcla reservada | CONFORME en perfiles ensayados; rechazo público pendiente | Acordar clasificación; Valentina debe validar antes de filtrar. Configuración de nombres interoperable pendiente. |
| Sin recuperación | P2 | Adaptador elige PruebaSesionLogin cuando hay cookie de sesión, incluso inválida | CONFORME CANDIDATO | Mantener rechazo; no usar contexto anónimo coexistente como fallback. |
| /me sin actividad | P3 | [consulta](../../backend/app/seguridad/operaciones_sesion.py) no llama registrar_actividad ni emite cookies | CONFORME INTERNO | Pruebas de fecha antes/después y expiración a treinta minutos en integración futura. |
| Logout inactivo | P4 | [ServicioLogout](../../backend/app/seguridad/operaciones_sesion.py) usa verificación específica de cierre y [CSRF](../../backend/app/seguridad/csrf.py) comprueba un token existente ligado a esa sesión | CONFORME INTERNO / TESTING | Consulta general, emisión de sesiones/contextos/tokens y operaciones protegidas siguen exigiendo cuenta activa. No habilita rutas de staging. |
| Origin / servicio | P5, Origin estricto y SEC-01B | [frontera](../../backend/app/api/dependencias_auth.py), [bootstrap](../../backend/app/api/csrf_auth.py); intermediario separado | CONFORME CANDIDATO | Componer por endpoint con precedencia explícita; probar pares de errores al registrar en otra tarea. |
| IP | P9/P10 | obtener_ip_verificada siempre rechaza después de SEC-01B | CIERRE CORRECTO | Infraestructura y backend: acreditar fuente antes de diseñar adaptador productivo. |
| Errores | P6 y contrato general 422 | [manejadores](../../backend/app/api/errores_auth.py) saneados, CookieAmbigua cae en 500 | PARCIAL / catálogo adicional PROPUESTA | No inventar COOKIE_INVALID u otro código; resolver clasificación antes de exponer. |
| Commit / cookies | Sesión/contexto/auditoría antes de respuesta | [adaptador](../../backend/app/api/adaptadores_auth.py) emite tras retorno confirmado; lectura posterior de reloj puede fallar | CONFORME CANDIDATO | Conservar pruebas PostgreSQL; reconocer resultado incierto sin retry ni éxito aparente. |
| Cuotas | P7, consumo existente | [bootstrap](../../backend/app/seguridad/bootstrap_csrf.py) acepta ensayo solo en testing; login exige seis parámetros; emisión autenticada usa max_tokens | PARCIAL PARA PRODUCCIÓN | Medir/aprobar parámetros, admisión autenticada y saturación. Etiqueta perfil=aprobado no prueba aprobación humana. |
| Timeouts | P8 | Motor 5 s conexión/pool/sentencia; no deadline total por auth. PR30/32 30 s backend | PENDIENTE DE MEDICIÓN/DECISIÓN | Presupuestos compatibles y límites de admisión por tramo, sin alterar valores aquí. |
| Composición por worker | P5/P7: controles por operación sin defaults de ensayo | [AdaptadorAuth.__init__](../../backend/app/api/adaptadores_auth.py) construye siempre ServicioLogin; exige HMAC, seis parámetros de límites y capacidad Argon2, incluso al preparar solo me/logout | ACOPLAMIENTO DE INICIALIZACIÓN EXISTENTE | Backend: configuración completa validada o composición explícita por endpoint en tarea autorizada; no inventar cuotas de ensayo para instanciar lecturas/cierre. No equivale a consumo de cuota de login por me/logout. |
| Rutas reales | P10 | GET csrf rechaza aun sustituyendo IP en test; login/me/logout no registrados, 404 | CIERRE CORRECTO | Registro posterior únicamente de cada operación completa y autorizada. |

Los comentarios heredados de RechazoAntesDeEfectos en el manejador mencionan
recuperación contractual. El adaptador no implementa reenvíos; bajo P8 esa marca
solo acredita rechazo previo a negocio, sin permiso de repetir la escritura.
Actualizar ese comentario en una futura tarea de código no requiere ni implica
modificar la política o activar rutas.

### Excepción de logout inactivo: implementación acotada

No reutilizar el DTO AuthUser como permiso. Identificar la sesión por una única
credencial canónica, cargar cuenta/sesión/contexto bajo locks coherentes,
verificar existencia, revocación, ocho horas, treinta minutos, rol admitido y
token CSRF todavía válido ligado a esa sesión. Revalidar después de esperas.
La inactividad de cuenta es la única condición exceptuada para **revocar**;
no exceptuar el vencimiento, la posesión o CSRF de una sesión revocable.

Token inexistente/vencido/ajeno no permite revocación de esa sesión: 403 según
la regla CSRF aplicable. No emitir un token autenticado nuevo para salvar ese
caso. Sesión inexistente/vencida/revocada confirmada conserva 204 idempotente,
sin evento ficticio. No reactivar cuenta ni actividad, no otorgar permisos ni
crear sesión/contexto/login. Cuenta inactiva sigue rechazada por me, bootstrap
autenticado, login y administración. Revocación/contexto/auditoría deben ser
atómicos; error de BD no se transforma en ausencia. Las regresiones de
[operaciones de sesión](../../backend/pruebas/integracion/test_operaciones_sesion.py)
y [HTTP local](../../backend/pruebas/integracion/test_ingreso_local_http.py)
verifican P4 con PostgreSQL real: ambos roles, CSRF previo válido o rechazado,
ausencia de emisión, otra sesión intacta, auditoría atómica y concurrencia con
desactivación en ambos órdenes. Esta evidencia no acredita staging ni Render.

## 4. Decisiones adicionales que siguen pendientes

| ID | Estado | Decisión exacta / recomendación | Impacto y prueba requerida |
| --- | --- | --- | --- |
| C01 | PROPUESTA | Ratificar 200 para csrf/login/me, campos csrfToken/expiresAt y cuerpo logout {}. Coinciden con DTO candidatos. | Backend/Next alineados; 204 logout y AuthUser ya aprobados no se reabren. Prueba de esquema exacto. |
| C02 | PROPUESTA | Ratificar los cuatro nombres candidatos de cookies y mapeo explícito local/production. Atributos estrictos ya formalizados; no elegir default local silencioso. | Configuración común y búsqueda; emisión, borrado, mezcla y perfiles incompletos. |
| C03 | PROPUESTA | Clasificación del rechazo de CookieAmbigua. Recomendar 422 VALIDATION_ERROR existente con details saneado, sujeto a decisión; hoy se sanea como 500. | No introducir un código nuevo. Rechazar siempre antes de efectos, cualquiera sea la clasificación aprobada. |
| C04 | PROPUESTA | Ratificar INVALID_CREDENTIALS/401 uniforme y RATE_LIMITED/429 con espera real; cerrar mensajes/casos del catálogo HTTP. | Cuentas ausente/inactiva/clave incorrecta indistinguibles; no confundir Argon2/BD con credenciales. |
| C05 | PROPUESTA / PENDING_MEASUREMENT | Parámetros productivos bootstrap/cuenta/IP, emisión autenticada, saturación, Argon2 por worker, cuerpo máximo y admisión. | Medir memoria/latencia/NAT/concurrencia; no adoptar cuotas de ensayo. |
| C06 | PROPUESTA / PENDING_MEASUREMENT | Cifras de timeout por endpoint y tramo; cancelación, lectura inicial y márgenes. | Reproducir cuerpo lento, locks, Argon2 y acuse perdido; ninguna escritura automática se reintenta. |
| C07 | PROPUESTA OPERATIVA | Nombre de variable privada SEC-01B en Next, distribución, vigencia/retiro, CA/hostname, orígenes y host local explícitos. | El mecanismo ya está aprobado. No generar nuevos nombres como si existieran ni distribuir secretos. |
| C08 | PENDIENTE_DE_EVIDENCIA | Fuente IP y terminación TLS/red efectivas en Render. | Requiere pruebas reales de la sección 6, no nueva aprobación abstracta de P9. |
| C09 | PROPUESTA OPERATIVA | GET csrf sin Origin solo con Sec-Fetch-Site same-origin y GET me sin Origin en SSR; prioridad exacta frente a DTO inválido y operación de correlación entre capas. | Reglas candidatas implementadas; no equivalen a identidad de servicio. Ratificar detalles interoperables antes de registro. |

Las responsabilidades de custodia, verificación y rechazo son definitivas en
el alcance aprobado; los valores y representaciones pendientes no quedan
aprobados por aparecer en un ejemplo. No hay decisión pendiente sobre P1–P10.

## 5. Cuotas y presupuestos: inventario, sin cifras productivas nuevas

| Control | Implementación actual | Condición productiva |
| --- | --- | --- |
| Bootstrap anónimo SEC-01A | Cuotas separadas contextos IP/global, intentos IP/global, emisiones por contexto; capacidades y limpieza acotadas; reserva durable antes de emisión | Política explícita aprobada y configurada. Ensayo solo testing. No mezclar con login ni eludir quitando cookie. |
| Login cuenta | Reservas persistentes por cuenta normalizada, incluso ausente; consolidación según resultado | Seis campos obligatorios de cuenta/IP en Configuracion; valores medidos y aprobados. No cambiar consumo por P7. |
| Login IP | IpVerificada y clave HMAC; reserva conjunta con cuenta | Procedencia acreditada, NAT y IPv6 medidos; sin IP sintética/global como sustituto. |
| Argon2 / saturación global | BoundedSemaphore por instancia ServicioLogin, sin cola; explícita capacidad por worker; no límite distribuido global demostrado | Medir total de workers y memoria. Rechazo de infraestructura no se convierte en 429 con espera inventada. |
| Tokens autenticados | ServicioCsrf limita tokens vigentes por contexto; no los expulsa para renovar | Definir admisión/saturación HTTP y espera verificable. No asumir cuota anónima aplicada aquí. |
| Recuperación | No existe recuperación automática aprobada/operativa | Sin cuota ni endpoint nuevo de recuperación en este incremento. |

Consumo SEC-01A existente: admisión durable de intentos global/IP y, sin
contexto presentado, reservas de creación global/IP; después se valida y
reserva el contexto existente en otra transacción y finalmente se emite.
Reservas de admisión sobreviven a contexto inválido/fallo posterior. P7 no
autoriza cambiar ese orden ni devolver capacidad ya consumida. Login conserva
su validación preliminar y reserva con nueva comprobación CSRF antes de Argon2;
no trasladar reglas de un coordinador al otro.

| Tramo | Tiempo observado en fuentes | Presupuesto recomendado / decisión pendiente |
| --- | --- | --- |
| Cliente→Next | PR30 lee request.arrayBuffer antes del try/deadline, sin límite propio. PR32 limita 8192 bytes, sin deadline total de ingreso | Definir máximo y plazo de admisión, procesamiento y lectura de respuesta por operación; no copiar 8 KiB como nuevo contrato login. |
| Next→FastAPI | PR30 BACKEND_TIMEOUT_MS=30000 para fetch y cuerpo; SSR mismo plazo. PR32 AbortSignal.timeout(30000) | Separar conexión/TLS, espera backend y lectura completa, todos dentro del plazo total Next. Son valores observados, no aprobación productiva. |
| FastAPI | No hay deadline total por operación auth; trabajo síncrono/Argon2 y varias transacciones | Medir y acotar suma de admisión, reservas, Argon2, confirmación, auditoría y serialización. Cancelar fetch no prueba rollback backend. |
| PostgreSQL | crear_motor_bd: connect_timeout=5 s, pool_timeout=5 s, statement_timeout=5000 ms; bootstrap aplica lock/statement de política | Límite por sentencia no equivale a límite de transacción/operación. Revisar conexión y suma de consultas, locks y commit. No cambiar parámetros aquí. |
| csrf | Admisión + IP + reservas + emisión + commit + respuesta | T_canal > T_backend_csrf + margen de respuesta; T_cliente > admisión Next + T_canal + margen. Valores C06 pendientes. |
| login | Varias transacciones + Argon2 fuera de locks + confirmación + reloj para cookie | Presupuesto propio mayor que coste medido completo; no sumar solo un statement_timeout. Margen exterior evita expirar sistemáticamente antes del backend. |
| me | Consulta persistente sin actividad, sin Argon2 | Presupuesto corto medido, independiente del LLM; no fijar milisegundos ficticios. |
| logout | Identificación + CSRF + revocación/contexto/auditoría + commit | Incluir esperas y variante inactiva; no reintentar automáticamente aunque el cierre sea idempotente. |

Los márgenes son relaciones de diseño, no garantías de cancelación distribuida.
Timeout, corte, 500/503 o fallo posterior al commit dejan resultado potencialmente
incierto: no afirmar rollback ni reintentar escritura. Conciliar mediante lectura
autorizada y estado observable sin recuperar secretos desde digests ni crear otra
sesión silenciosamente. Los reintentos internos acotados de control de versión de
cuotas existentes no son reenvíos HTTP ni autorización para repetir negocio.

## 6. Matriz de acreditación IP

| Escenario | Fuente | Actor que la controla | Cadena de confianza | Evidencia requerida | Estado | Pruebas |
| --- | --- | --- | --- | --- | --- | --- |
| Harness local | Socket del listener local; fixtures internos separados | Runner y SO de prueba | Node cliente→Next→TLS FastAPI, sin propagar socket como identidad | D.2 demuestra transporte, no IP original autenticada | OBSERVACIÓN LOCAL; IP HTTP NO ACREDITADA | Cabeceras falsas no crean IpVerificada; servicio válido sigue cerrado. |
| Next real en Render | Fuente de ingreso todavía por identificar | Plataforma y operador, por confirmar | Navegador→ingreso→Next | Documentar productor, saneamiento, todos los caminos y límites; captura saneada desde clientes conocidos | PENDIENTE_DE_EVIDENCIA | IP conocida, duplicados, listas y spoofing en cada entrada. |
| FastAPI privado Render | Peer inmediato puede ser Next/proxy | Plataforma/operador | Next autenticado→salto privado→listener | TLS efectivo, CA/hostname, peer no reescrito, regla de metadato autenticado si se propone | PENDIENTE_DE_EVIDENCIA | Acceso permitido/denegado y ausencia de reinterpretación X-Forwarded-Proto. |
| Acceso directo backend | Socket o cabeceras aportadas por solicitante | Solicitante / red | Falta intermediario admitido | Inventario de puertos/rutas públicas/internas y ACL | DEBE RECHAZAR | Sin SEC-01B: 503; bearer robado no acredita IP ni usuario. |
| Cabeceras falsificadas | Forwarded, X-Real-IP, X-Forwarded-For y variantes | Cliente atacante | Ninguna cadena acreditada | Filtro ingreso y prueba de rechazo backend | RECHAZO LOCAL VERIFICADO; Render pendiente | Duplicados idénticos/distintos, casing, valores vacíos/listas. |
| Múltiples proxies | Lista de saltos | Varios operadores | No aprobada; no elegir primer/último valor arbitrariamente | Topología, orden, emisor y saneamiento en cada salto; prevenir caminos cortos | PENDIENTE_DE_EVIDENCIA | Saltos adicionales/omitidos, reordenamiento y acceso alternativo. |
| IPv4 | Fuente acreditada futura, no cabecera libre | Operador de ingreso | Misma prueba de procedencia | Normalización y rechazo de sintaxis ambigua antes de HMAC | PRIMITIVAS INTERNAS; Render pendiente | Canonicalización y misma clave entre representaciones admitidas. |
| IPv6 | Fuente acreditada futura | Operador de ingreso | Misma prueba de procedencia | IPv6 y IPv4 mapeadas, corchetes/puerto/zonas según política del parser existente | PRIMITIVAS INTERNAS; Render pendiente | Variantes equivalentes/ambiguas, no fragmentar cuota mediante formato. |
| NAT compartido | IP pública común, no individuo | Red del cliente | IP acreditada no identifica persona | Medir efectos de cuotas conjuntas y privacidad; cuenta/sesión siguen independientes | PENDIENTE_DE_MEDICIÓN | Dos cuentas/IP común, abuso y bloqueo sin enumeración. |
| Sin IP verificable | Fuente ausente/ambigua | Desconocido | Incompleta | Registrar condición saneada, sin inventar dato | CIERRE OBLIGATORIO | csrf/login 503 sin token/cookie/negocio; me/logout no adquieren requisito IP por analogía. |

No existe cabecera IP interna aprobada ni adaptador Render productivo. La red
privada no autentica Next. Si la plataforma termina TLS antes del listener, la
topología debe revisarse con evidencia: SEC-01B actual requiere TLS directo y
proxy_headers=False; X-Forwarded-Proto no sustituye esa condición.

## 7. Matriz de aceptación reproducible

Ejecución histórica reproducible del arnés, desde backend con intérprete del
proyecto y POSTGRES_TEST_* apuntando exclusivamente a localhost:5433:

```powershell
./.venv/Scripts/python.exe -m herramientas.arnes_http_seguro.ejecutar --reporte auth07d2-arnes-repeticion.json
```

Elegir un nombre nuevo si ya existe. El runner usa fuentes PR30 fijadas: repetirlo
**no valida automáticamente un nuevo HEAD**. Un incremento posterior debe fijar
y registrar los blobs nuevos y convertir las caracterizaciones de defecto en
aceptaciones del comportamiento corregido, conservando ambas evidencias. No
modificar sus expectativas para llamar conforme al defecto original.

| ID | Caso y procedimiento | Resultado exigido | Evidencia D.2 / estado | Responsable |
| --- | --- | --- | --- | --- |
| A01 | Node TLS a Uvicorn y SELECT en base temporal 0006 | CA/hostname válidos, esquema correcto; inválidos no conectan | TLS_CA_HOSTNAME_Y_POSTGRESQL, TLS_CA_NO_CONFIADA, TLS_HOSTNAME_INCORRECTO: VERIFICADO LOCAL | Valentina/backend |
| A02 | SEC correcta, ausente, inválida, vencida, duplicada, otro entorno y rotación | Solo credenciales vigentes del entorno admitidas; sin usuario/IP inventados | SEC01B_*: VERIFICADO LOCAL con fixtures de política | Valentina/backend |
| A03 | Proxy y SSR reales #30 contra sonda SEC | Inyección servidor en ambos caminos | PR30_SIN_CREDENCIAL_SERVICIO, PR30_SSR_SEC01B_AUSENTE: INCOMPATIBILIDAD REPRODUCIDA | Valentina |
| A04 | Cookie sesión sin '=' junto a contexto anónimo válido | Rechazo, nunca ocultar sesión presentada | PR30_PIERDE_COOKIE_MALFORMADA: INCOMPATIBILIDAD REPRODUCIDA | Valentina |
| A05 | Cookies reservadas local+production, incluso sesión de un perfil y contexto del otro | Rechazo antes de filtro; no identidad anónima | PR30_OCULTA_MEZCLA_PERFILES: INCOMPATIBILIDAD REPRODUCIDA | Valentina |
| A06 | Duplicada idéntica/distinta, vacía, comillas, %codificación, múltiples Cookie | Sin primer/último valor ni decodificación reparadora; rechazo saneado | COOKIE_BACKEND_RECHAZA_* y PR30_COOKIE_RECHAZADA_*: VERIFICADO en casos locales; cabeceras múltiples deben cubrir Node/SSR futuro | Valentina/backend |
| A07 | Emisión/borrado local/production y dos Set-Cookie | Cabeceras separadas, HttpOnly/Lax/Path=/, Secure HTTPS, sin Domain __Host- | PR30_SET_COOKIE_* / PR30_BORRADO_COOKIE_*: VERIFICADO con marcadores, navegador PENDIENTE | Valentina |
| A08 | Origin permitido, ausente, inválido, duplicado; Sec-Fetch-Site bootstrap | 403 sin efectos según tabla por endpoint, no Origin fabricado SSR | ORIGIN_*, BOOTSTRAP_* y PR30_ORIGIN_*: VERIFICADO en sondas; composición de rutas PENDIENTE | Backend/Valentina |
| A09 | CSRF válido, ausente, inválido, duplicado, ajeno y vencido | Ligado a contexto/sesión persistente; 403 previo a negocio | CSRF_*, NEXT_SUSTITUTO_*: VERIFICADO parcial local; éxito Next es sustituto | Backend/Valentina |
| A10 | Bearer válido más IP falsificada y GET csrf real | Sin IpVerificada ni emisión/cookie; login/me/logout 404 actuales | IP_NO_ACREDITADA_*, CSRF_PRODUCTIVO_CERRADO_CON_SEC01B, RUTA_PRODUCTIVA_AUSENTE_*: VERIFICADO LOCAL | Backend |
| A11 | BD real falla, serialización falla, UUID cliente arbitrario | ApiErrorBody saneado, no-store, requestId servidor; sin cookie de éxito | ERROR_BD_REAL, ERROR_SERIALIZACION, REQUEST_ID_NO_CLIENTE y PR30_ERROR_*: VERIFICADO LOCAL | Backend/Valentina |
| A12 | Backend ausente, CA/hostname falsos, 307 y respuesta >30 s | 503 saneado, sin seguir redirección ni retry | PR30_CANAL_RECHAZADO_*, PR30_REDIRECCION_RECHAZADA, PR30_TIMEOUT_REAL_30S: VERIFICADO LOCAL | Valentina |
| A13 | Cuerpo lento/excesivo y presupuesto completo | Lectura inicial acotada, error sin entrada/secreto, plazo total por operación | Brecha estática en PR30; NO PROBADO como corrección | Valentina/PO |
| A14 | PostgreSQL: commit visible desde otra conexión, fallo auditoría/constraint diferida | Sin respuesta/cookie de éxito antes del commit ni alta parcial | Suite D.1 incluida en 351 D.2: VERIFICADO INTERNO; HTTP real futuro pendiente | Backend |
| A15 | /me repetido/SSR y reloj al límite de inactividad | No cambia actividad ni ocho horas, 401 al vencer | Servicio interno cumple P3; prueba futura del recorrido HTTP PENDIENTE | Backend |
| A16 | Cuenta desactivada: token previo vigente vs inválido, revocación/locks/auditoría | Solo cierre verificado atómico; me/admin siguen rechazados, sin token nuevo | P4 implementada; regresiones PostgreSQL y HTTP local, sin acreditación productiva | Backend |
| A17 | Cookie vencida/revocada con contexto anónimo coexistente | Rechazo csrf/login; logout explícito puede limpiar tras confirmación; luego nuevo flujo explícito | P2 presente en candidato; navegador y carreras PENDIENTES | Backend/Valentina |
| A18 | Ruta específica search: servicio+usuario+CSRF y respuesta de dominio | Canal común, mismos controles, contrato de búsqueda preservado | PR32 inspección ESTÁTICA; ejecución PENDIENTE | América |
| A19 | Dos usuarios SSR y pestañas login/logout simultáneas | Sin cookies globales/cache cruzada/borrado tardío; ningún retry de escritura | PR30_SSR_REAL_AISLADO local parcial; navegador/carreras PENDIENTES | Valentina/backend |
| A20 | Render con clientes conocidos y cabeceras hostiles | Fuente IP demostrada para cada salto; TLS/red/secretos verificables | NO EJECUTADO / PENDIENTE_DE_EVIDENCIA | Infraestructura/equipo |

Para pruebas persistentes futuras: crear base única, verificar servidor/base en
localhost:5433 antes de migrar/eliminar, aplicar 0006, limpiar solo recursos
propios y comprobar ausencia. Nunca usar localhost:5432. El arnés no emite
credenciales productivas ni certifica cuotas de producción.

## 8. Secuencia exacta de incrementos

Este plan es preparación; no autoriza comenzar el siguiente incremento. La
evidencia requerida se obtiene sin abrir rutas incompletas. El orden distingue
acreditación previa de IP de la validación integral final del despliegue.

| Orden / incremento | Dependencias y condición de inicio | Archivos previstos / responsable | Pruebas obligatorias y criterio de término | Qué permanece cerrado |
| --- | --- | --- | --- | --- |
| 1. Contratos formalizados | Encargo D.3, P1–P10 y arquitectura/servicio aprobados | Contratos de esta carpeta / backend+PO+equipo | Coherencia, enlaces, estados y brechas trazables; C01–C09 visibles | Todas las rutas auth conservan su estado actual. |
| 2. Ajustes PR30 | Encargo separado y decisiones de representación necesarias, sin exigir IP inventada | backend-proxy.ts, transport/server.ts, Route Handler y entorno/tests del PR30 / Valentina | A01–A08, A11–A13, A19; SEC/TLS en proxy y SSR; no ocultar cookies; HEAD/blob nuevos registrados | csrf cerrado; login/me/logout sin registrar. |
| 3. Validación canal Node/FastAPI | Canal común corregido, arnés adaptado explícitamente al nuevo HEAD | herramientas/arnes_http_seguro y pruebas de transporte / Valentina+backend | TLS real y PostgreSQL; positivos dejan de usar sustituto SEC para validar PR30; limpieza y pruebas negativas | Sin rutas auth productivas ni IP sintética HTTP. |
| 4. Ajustes PR32 | Canal común validado, contrato búsqueda preservado | search-proxy.ts, ruta search, recuperacion/acceso.py y tests / América+backend | A18, sesión/CSRF/servicio separados, Origin antes de efectos y no-store, resultados de dominio iguales | Auth cerrado; búsqueda no tiene excepción ML. |
| 5. Procedencia IP | Acceso a infraestructura autorizado en otra tarea y topología documentada | Evidencia de ingreso/TLS/ACL; futuro adaptador solo tras acreditación / infraestructura+backend | Matriz sección 6, spoofing/caminos alternativos/IPv4/IPv6 y ausencia; fuente y contrato aprobados | csrf/login cerrados si falta prueba; no basta un voto. |
| 6. Habilitación CSRF | C01–C09 aplicables resueltas, cuotas productivas y canal/IP completos, encargo de activación | api/csrf_auth.py, composición worker y pruebas / backend | A08–A11/A14/A17, admisión anónima/autenticada, commit antes de token/cookie, pruebas negativas completas | Login/me/logout todavía sin registrar. |
| 7. Habilitación login | Bootstrap operativo seguro, IP/cuotas/Argon2 medidos, DTO/catálogo y proxy listos | api/adaptadores_auth.py y futuro registro/composición; consumidor posterior / backend+Valentina | Reemplazo, CSRF, cuotas, rollback/commit incierto, sin secretos ni retry; sesiones de otros dispositivos intactas | Me/logout sin registrar hasta su aceptación. |
| 8. Habilitación me | Contrato lectura completo, P3, servicio/TLS, perfil y SSR listos; no agrega IP | Futuro registro de consulta y consumidor AuthUser / backend+Valentina | A15/A19, ausente/vencida/revocada/inactiva 401, sin actividad/cookies ni cache cruzada | Logout pendiente; ningún bypass si login falla. |
| 9. Habilitación logout | P4 implementada internamente y validada antes de registro; DTO/catálogo, CSRF y carreras completos | seguridad/operaciones_sesion.py, sesiones.py/csrf.py solo cambios estrechos necesarios; adaptador/registro y tests / backend+Valentina | A14/A16/A17/A19: idempotencia, inactivo, locks, auditoría, sin borrar por 403 ni éxito ante BD caída | Administración HTTP excluida. |
| 10. Navegador | Entorno de ensayo completo autorizado y canal anterior aceptado | Tests E2E de navegador y frontend auth en tarea propia / equipo | Secure/HttpOnly/Lax/__Host-, memoria CSRF, expiración, SSR y pestañas; sin secretos en HTML/bundle/logs | No producción si falta aceptación integral. |
| 11. Validación integral Render | Evidencia IP previa, red/TLS/rotación y aplicación completa en entorno autorizado | Configuración/evidencias operativas, sin valores secretos en Git / infraestructura+equipo | A20 más recorrido real navegador/Next/FastAPI/PostgreSQL; controles de ingreso y acceso directo; mediciones aprobadas | Tráfico productivo cerrado ante cualquier control ausente. |
| 12. Administración HTTP | Solo si se aprueba contrato separado de rutas/DTO/errores y existe encargo | Adaptador futuro ServicioCreacionUsuarios / backend+PO | Admin vigente transaccional, CSRF, cuotas, Argon2, user_created atómico y entrega externa | Registro público y capacidades administrativas no aprobadas. |

El backend puede desarrollar y probar **antes de Render**, bajo un encargo
separado, la excepción P4, la composición/catálogo/DTO acordados, los deadlines y
la configuración por worker, siempre mediante servicios/adaptadores internos y
PostgreSQL temporal, sin registrar rutas. El siguiente incremento recomendado
es corregir y validar el canal común PR30 con los casos de incompatibilidad
reproducidos; si se elige trabajo exclusivamente backend, P4 es una unidad
implementable sin esperar IP Render. No se inicia ninguno desde D.3.
