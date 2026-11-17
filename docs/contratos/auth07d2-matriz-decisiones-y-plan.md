# Antecedente histórico: matriz de decisiones y preparación de AUTH-07D.2

> **ARCHIVO HISTÓRICO, NO NORMATIVO PARA LA INTEGRACIÓN ACTUAL.** Conserva la
> revisión D.1 anterior al arnés D.2 y a la aprobación expresa P1–P10 de D.3.
> Sus estados y frases «no ejecutado/no iniciado» describen aquella revisión.
> Aplicar la [matriz vigente D.3](auth07d3-compatibilidad-y-plan-integracion.md),
> el [HTTP V1 formalizado](autenticacion-http-adaptadores-v1.md) y las
> [especificaciones actuales PR30/PR32](integracion-http-pr30-pr32-v1.md).
> D02: mecanismo/arquitectura aprobados ahora, operación por acreditar.
> D04–D05: atributos/rechazo estricto aprobados, nombres/clasificación pendientes.
> D06: P2 prohíbe recuperación automática. D07: P3 fija /me sin actividad.
> D08/D09: controles independientes y cierre sin cuotas productivas P5/P7/P10.
> D11: P4 permite solo revocación verificable de cuenta inactiva, aún sin código.
> D14: P8 sustituye el reenvío automático de escrituras; conserva renovación preventiva.
> IP Render, cifras, catálogo/DTO adicionales y operación no quedan aprobados
> por estas actualizaciones. La [guía versionable D.2](../../backend/herramientas/arnes_http_seguro/README.md)
> conserva el resumen histórico, los casos y las instrucciones reproducibles del arnés.

**DRAFT / REVIEW_REQUIRED para habilitar tráfico.** Entregable documental de
SYNAPDESK-AUTH07D1-REVIEW-CHECKPOINT-AND-INTEGRATION-READINESS. Las recomendaciones
no constituyen aprobación del Product Owner ni autorización de implementación.
Consolidar código candidato D.1 no habilita endpoints o infraestructura.

Fuentes: [autenticación V1](autenticacion-v1.md),
[frontend/backend y errores generales](frontend-backend.md),
[SEC-01B](comunicacion-interna-segura-v1.md),
[candidato HTTP D.1](autenticacion-http-adaptadores-v1.md) y
[acuerdo PR30/PR32](integracion-http-pr30-pr32-v1.md).
Los estados APROBADA se apoyan en decisiones explícitas de esas fuentes. Un
requisito de seguridad del encargo se conserva sin convertir propuestas vecinas
en aprobaciones. PENDIENTE_DE_EVIDENCIA no se resuelve con una decisión documental.

## Matriz para conciliación

### D01 — Identidades y autoridad

| Campo | Definición |
| --- | --- |
| DECISIÓN | Sesión de usuario distinta de servicio e IP; FastAPI como autoridad. |
| ESTADO | APROBADA: sesión opaca PostgreSQL, DTO AuthUser id/email/role dentro de user y separación exigida por los encargos SEC-01B/D.1. |
| COMPORTAMIENTO_ACTUAL | SEC-01B devuelve IdentidadIntermediario; consulta de sesión revalida PostgreSQL. La dependencia IP HTTP no acredita nada. |
| PROPUESTA_RECOMENDADA | Conservar las tres pruebas independientes; nunca aceptar rol, AuthUser o bearer de servicio como autorización de usuario. |
| IMPACTO_BACKEND | Componer dependencias existentes y revalidar dentro de transacciones que autorizan efectos. |
| IMPACTO_FRONTEND | Transmitir cookies, sin fabricar identidad; secreto de servicio solo en Next servidor. |
| PRUEBAS_DE_ACEPTACIÓN | Bearer válido sin sesión no obtiene usuario; sesión agent no concede permisos admin; IP en cabecera no crea IpVerificada. |
| RIESGO_SI_SE_APRUEBA | Decisión ya aprobada; el riesgo es omitir una autoridad al integrar, no una autorización nueva. |

### D02 — Credencial interna y TLS

| Campo | Definición |
| --- | --- |
| DECISIÓN | Formalizar operación SEC-01B, custodia/rotación y topología TLS. |
| ESTADO | PROPUESTA: candidato backend implementado/autorizado, contrato SEC-01B sigue DRAFT; TLS verificado es requisito obligatorio del encargo. |
| COMPORTAMIENTO_ACTUAL | Bearer opaco canónico de 32 bytes, digests por entorno, una/dos claves con vencimiento; TLS directo y rechazo de cabeceras de proxy. #30/#32 no inyectan credencial y permiten HTTP local. |
| PROPUESTA_RECOMENDADA | Adoptar operación documentada, secreto exclusivo de servidor y TLS verificado también en ensayo; acordar nombre de variable Next, distribución, vencimientos, retiro y CA. No degradar a HTTP. |
| IMPACTO_BACKEND | Configurar AUTH_INTERMEDIARIO/APP_ENV; listener TLS directo con proxy_headers=False. Otra terminación requiere revisión contractual y evidencia, sin aceptar X-Forwarded-Proto. |
| IMPACTO_FRONTEND | Transporte común y SSR inyectan Authorization propia, descartando la del navegador; verificar CA/hostname y destino fijo. |
| PRUEBAS_DE_ACEPTACIÓN | Rotación/vencimiento, configuración ausente, bearer duplicado, CA/hostname incorrectos, HTTP y redirecciones rechazados; secreto ausente de bundle/HTML/logs. |
| RIESGO_SI_SE_APRUEBA | Bearer robado permite impersonar servicio; no ofrece antirreplay de aplicación. Reinicios/rotación descoordinados pueden cerrar tráfico. |

### D03 — Procedencia IP

| Campo | Definición |
| --- | --- |
| DECISIÓN | Fuente que acredita IP original y cadena de confianza completa. |
| ESTADO | PENDIENTE_DE_EVIDENCIA. |
| COMPORTAMIENTO_ACTUAL | obtener_ip_verificada autentica servicio y rechaza. No lee Request.client, Forwarded, X-Real-IP ni X-Forwarded-For como evidencia. |
| PROPUESTA_RECOMENDADA | Mantener cierre hasta probar ingreso, saneamiento, pares y caminos alternativos reales. No elegir todavía una cabecera productiva ni sustituir cuota IP por global. |
| IMPACTO_BACKEND | Futuro adaptador solo después de acreditar fuente y normalización, con rechazo por ausencia/ambigüedad; preservar HMAC de privacidad existente. |
| IMPACTO_FRONTEND | Next no debe reenviar datos IP arbitrarios del navegador ni alegar que bearer los acredita. |
| PRUEBAS_DE_ACEPTACIÓN | Clientes de IP conocida, spoofing/duplicados/listas/IPv4/IPv6, acceso directo y caminos alternativos, evidencia del generador y del salto privado. |
| RIESGO_SI_SE_APRUEBA | Una fuente supuesta permite eludir cuotas o bloquear a terceros; NAT y privacidad requieren medición. La aprobación sin evidencia no satisface esta condición. |

### D04 — Perfiles y nombres de cookies

| Campo | Definición |
| --- | --- |
| DECISIÓN | Nombres, ámbito y duración de sesión/contexto local y production. |
| ESTADO | PROPUESTA para nombres/perfil concreto; HttpOnly y HTTPS productivo ya aprobados. |
| COMPORTAMIENTO_ACTUAL | AUTH-07A exige perfil explícito y origen permitido; emite HttpOnly, SameSite=Lax, Path=/, sin Domain, Secure en HTTPS y Max-Age restante. __Host- usa esos atributos. #30 usa default local si falta configuración. |
| PROPUESTA_RECOMENDADA | Adoptar nombres D.1 con configuración explícita por entorno y mismo host público; elegir si el ensayo de navegador local será HTTPS. Un perfil HTTP de cookie no autoriza HTTP del canal de servicio. |
| IMPACTO_BACKEND | Mantener constructor/lector común y borrar con el mismo ámbito tras commit; no extender expiración absoluta. |
| IMPACTO_FRONTEND | Alinear AUTH_COOKIE_PROFILE y cookie de búsqueda; conservar múltiples Set-Cookie separados sin Domain interno; fallar ante configuración incompleta. |
| PRUEBAS_DE_ACEPTACIÓN | Emisión/borrado local/production, __Host- con Secure y sin Domain, mezcla de perfiles rechazada, Max-Age sin extender vigencia, mismo host Next. |
| RIESGO_SI_SE_APRUEBA | Nombres o atributos divergentes causan pérdida de sesión, cookies paralelas o fijación accidental de ámbito. |

### D05 — Cookies ambiguas o malformadas

| Campo | Definición |
| --- | --- |
| DECISIÓN | Clasificación HTTP del rechazo y preservación de evidencia en el proxy. |
| ESTADO | PROPUESTA de clasificación; rechazar ambigüedad sin elegir credencial es requisito vigente. |
| COMPORTAMIENTO_ACTUAL | Backend conserva originales y rechaza duplicados/malformadas/mezcla reservada; CookieAmbigua se sanea como 500. #30 conserva duplicados con '=', pero filtra una cookie permitida sin '=' y elimina perfiles ajenos. |
| PROPUESTA_RECOMENDADA | Acordar un rechazo de representación compatible con el catálogo, sin recuperación implícita. Next debe rechazar o conservar la evidencia relevante antes de filtrar; no convertir una credencial malformada presentada en cookie ausente. |
| IMPACTO_BACKEND | No cambiar clasificación ni recuperación hasta acordarla; conservar lector estricto. |
| IMPACTO_FRONTEND | Corregir el filtro antes de canal auth real y probar el transporte completo; no elegir primer/último valor. |
| PRUEBAS_DE_ACEPTACIÓN | 'cookieDeSesion' sin '=', valor vacío/entre comillas, clave con espacios, duplicados incluso idénticos, perfiles mezclados y cabeceras múltiples. Con contexto anónimo coexistente no debe aparecer recuperación silenciosa. |
| RIESGO_SI_SE_APRUEBA | Normalizar o descartar antes del control puede esconder ambigüedad; un código nuevo no conciliado rompe consumidores. |

### D06 — Cookie vencida/inválida y recuperación anónima

| Campo | Definición |
| --- | --- |
| DECISIÓN | Mantener rechazo o permitir recuperación explícita tras confirmar invalidez persistente. |
| ESTADO | PROPUESTA. |
| COMPORTAMIENTO_ACTUAL | D.1 selecciona siempre rama de sesión presentada y rechaza si no es válida. V1 propone GET csrf anónimo después de 401 sin borrar cookie. Logout confirmado inexistente/vencido/revocado aplica 204 aprobado. |
| PROPUESTA_RECOMENDADA | Conservar rechazo hasta decidir. Si se aprueba recuperación, confirmar invalidez en BD, no borrar/renovar sesión desde GET y exigir contexto/CSRF anónimo correcto para nuevo login; diseñar carreras y revalidación por separado. |
| IMPACTO_BACKEND | Cambiar solo en incremento autorizado con transacciones/pruebas; no reinterpretar fallo BD como ausencia de sesión. |
| IMPACTO_FRONTEND | Descartar identidad local tras 401 y coordinar recuperación; ningún reintento de negocio automático por cambio de contexto. |
| PRUEBAS_DE_ACEPTACIÓN | Vencida/revocada/inexistente frente a BD caída, cookie preservada en lecturas, sesión que cambia durante espera y contexto ajeno rechazado. |
| RIESGO_SI_SE_APRUEBA | Recuperación demasiado permisiva oculta sesión presentada inválida y carreras; rechazo permanente puede impedir reingreso sin procedimiento explícito. |

### D07 — Actividad de /me

| Campo | Definición |
| --- | --- |
| DECISIÓN | Si una lectura /me válida renueva inactividad. |
| ESTADO | PROPUESTA; 8 h absolutas y 30 min de inactividad ya aprobados. |
| COMPORTAMIENTO_ACTUAL | ConsultaSesion y candidato me no llaman registrar_actividad. V1 propone contabilizar peticiones autorizadas incluido me y advierte sobre polling. |
| PROPUESTA_RECOMENDADA | Mantener /me como lectura sin renovación, salvo aceptación explícita del mantenimiento de actividad por polling. Precisar qué operaciones sí cuentan antes de cualquier cambio. |
| IMPACTO_BACKEND | Ninguno en este checkpoint. Si cambia, actualización monotónica y revalidación posterior a locks sin resucitar sesiones ni ampliar 8 h. |
| IMPACTO_FRONTEND | Definir polling, SSR y UX de caducidad sin usar CSRF como actividad. |
| PRUEBAS_DE_ACEPTACIÓN | Consultas repetidas/SSR no alteran actividad bajo política actual; expiración durante lock y concurrencia logout no reactivan sesión. |
| RIESGO_SI_SE_APRUEBA | Renovar por polling conserva sesiones desatendidas; excluir lecturas puede cerrar una sesión durante uso de solo lectura. |

### D08 — Orden de validaciones

| Campo | Definición |
| --- | --- |
| DECISIÓN | Precedencia observable de Origin, servicio, cookies, IP, DTO, sesión, CSRF y cuotas. |
| ESTADO | PROPUESTA para el orden global; Origin previo a efectos y precedencia idempotente de logout ya aprobados. |
| COMPORTAMIENTO_ACTUAL | Candidato: Origin/bootstrap → SEC-01B → cookies → IP en csrf/login → coordinadores. DTO FastAPI no está integrado a rutas reales; búsqueda #32 inspecciona cookie antes de Origin. |
| PROPUESTA_RECOMENDADA | Conservar Origin antes de mutación y del cierre sin sesión; servicio separado, representación estricta, IP donde se exige, contexto/CSRF antes de negocio, cuotas antes de Argon2 y revalidación transaccional antes del commit. Conciliar cuerpo inválido + Origin inválido y errores simultáneos. |
| IMPACTO_BACKEND | Diseñar dependencias reales y parseo con prioridad explícita; no asumir orden de DTO/dependencias FastAPI por su apariencia. |
| IMPACTO_FRONTEND | No fabricar Origin; alinear rechazo previo en búsqueda y tratar estados sin deducir efectos inciertos. |
| PRUEBAS_DE_ACEPTACIÓN | Pares de fallos simultáneos, Origin ausente sin cookie, sesión revocada sin CSRF y válida con token inválido, sin escrituras de negocio/cookies por rechazo. |
| RIESGO_SI_SE_APRUEBA | Precedencias incoherentes dificultan recuperación, filtran estados o convierten errores en falsos permisos. |

### D09 — Cuotas, saturación y Retry-After

| Campo | Definición |
| --- | --- |
| DECISIÓN | Configuración medida y admisión del canal HTTP, especialmente CSRF autenticado. |
| ESTADO | PROPUESTA / pendiente de medición; no se cambian cuotas actuales. |
| COMPORTAMIENTO_ACTUAL | Bootstrap anónimo reserva IP/global/contexto; login reserva cuotas persistentes antes de Argon2. Retry-After deriva de DecisionLimite/reloj. CSRF autenticado conserva máximo de tokens; LIMITE_TOKENS no se transforma en 429 inventado. |
| PROPUESTA_RECOMENDADA | Mantener reservas y parámetros hasta medir; acordar admisión/tamaño de cuerpo/capacidad por worker y rechazo de saturación con espera verificable sin expulsar tokens vigentes. |
| IMPACTO_BACKEND | Integrar únicamente decisiones de cuota reales; no añadir cuota de logout o actividad por analogía ni reintentos automáticos. |
| IMPACTO_FRONTEND | Preservar Retry-After y mostrar espera; coordinar emisión CSRF; cubrir recepción de cuerpo antes del timeout hacia backend. |
| PRUEBAS_DE_ACEPTACIÓN | Cuotas concurrentes/reinicio/rollback, reloj tras locks, espera positiva verificable, cuerpos lentos/excesivos y saturación sin expulsión. |
| RIESGO_SI_SE_APRUEBA | Umbrales sin medición permiten DoS o bloquean usuarios compartiendo NAT; esperas inventadas producen reintentos incorrectos. |

### D10 — Contrato general de errores e identidad

| Campo | Definición |
| --- | --- |
| DECISIÓN | ApiErrorBody general, 422 de validación y rechazo Origin/CSRF/indisponibilidad. |
| ESTADO | APROBADA en frontend/backend y autenticación V1. |
| COMPORTAMIENTO_ACTUAL | Sobre error:{code,message,details,requestId}; validación 422 VALIDATION_ERROR saneada; 403 ORIGIN_INVALID/CSRF_INVALID; 503 SERVICE_UNAVAILABLE. Ready mantiene DATABASE_UNAVAILABLE. AuthUser tiene solo id/email/role. |
| PROPUESTA_RECOMENDADA | Conservar contrato; no publicar errores Pydantic crudos, SQL, hashes, tokens o input. 503 por estado sin retry de mutación. |
| IMPACTO_BACKEND | Reutilizar manejadores/DTO existentes y distinguir credenciales de validación estructural. |
| IMPACTO_FRONTEND | Mostrar detalles por campo solo si cumplen esquema; fallback genérico y requestId backend conservado. |
| PRUEBAS_DE_ACEPTACIÓN | Extra role/name rechazados, detalles sin secretos/campos arbitrarios, 422 distinto de 401, 503 sin 204 ficticio. |
| RIESGO_SI_SE_APRUEBA | Ya aprobado; duplicar catálogos o reflejar input rompe saneamiento/interoperabilidad. |

### D11 — Estados y casos de autenticación pendientes

| Campo | Definición |
| --- | --- |
| DECISIÓN | 200 csrf/login/me, INVALID_CREDENTIALS/401, campos CSRF, cuerpo logout y cuenta inactiva en logout. |
| ESTADO | PROPUESTA; no reabre 204 idempotente ya aprobado para sesión inexistente/vencida/revocada. |
| COMPORTAMIENTO_ACTUAL | Candidatos usan 200, csrfToken/expiresAt, INVALID_CREDENTIALS y {} estricto. Logout con cuenta inactiva produce rechazo de servicio traducido a 401; V1 no concilia este caso con su regla general de ausencia de sesión válida. Ningún handler candidato está registrado. |
| PROPUESTA_RECOMENDADA | Ratificar 200/campos/código uniforme de login y cuerpo; conciliar cuenta inactiva con idempotencia antes de registrar, sin simular revocación ni ocultar fallo BD. |
| IMPACTO_BACKEND | Solo cambiar traducción/servicio afectado tras decisión y pruebas; conservar auditar rechazo y atomicidad. |
| IMPACTO_FRONTEND | Alinear consumidores y mensajes; nunca distinguir cuenta ausente, inactiva o contraseña incorrecta en login. |
| PRUEBAS_DE_ACEPTACIÓN | Matriz completa estado/código/cuerpo y Set-Cookie; cuenta inactiva explícita, representación malformada y BD caída. |
| RIESGO_SI_SE_APRUEBA | Una clasificación implícita crea diferencias observables o permite una respuesta de éxito sin confirmación. |

### D12 — requestId

| Campo | Definición |
| --- | --- |
| DECISIÓN | Procedencia y correlación del identificador entre proxy, backend y auditoría. |
| ESTADO | PROPUESTA operativa; presencia del campo en errores ya aprobada. |
| COMPORTAMIENTO_ACTUAL | Backend genera UUID servidor e ignora X-Request-ID cliente; D.1 lo propaga a login/logout internos. Proxy genera otro solo para sus errores; búsqueda valida formato antes de conservar uno recibido del backend. |
| PROPUESTA_RECOMENDADA | Adoptar esa separación; conservar requestId backend en su respuesta y marcar errores propios sin afirmar auditoría backend. No añadir campo a AuthUser o cabecera nueva sin acuerdo. |
| IMPACTO_BACKEND | Mantener UUID por petición y opcional request_id interno compatible con llamadores anteriores. |
| IMPACTO_FRONTEND | Preservar identificador de error backend; generar identificador solo en rechazos de Next y no confiar en navegador. |
| PRUEBAS_DE_ACEPTACIÓN | UUID cliente ignorado; auditoría de login/logout coincide con servidor; timeout de proxy no inventa evento backend. |
| RIESGO_SI_SE_APRUEBA | Atribución incorrecta mezcla incidentes; IDs pueden correlacionar actividad y requieren política de logs/retención. |

### D13 — Reemplazo de sesión y commit incierto

| Campo | Definición |
| --- | --- |
| DECISIÓN | Login exitoso sustituye solo sesión válida presentada; efectos antes de cookies. |
| ESTADO | APROBADA para reemplazo y sesiones independientes; detalles de conciliación operativa siguen propuestos. |
| COMPORTAMIENTO_ACTUAL | Servicio confirma sesión/contexto/eventos conjuntamente y retorna después; adaptador emite cookie después. Fallo diferido no produce cookie de éxito. Una lectura de reloj posterior al commit también puede fallar. |
| PROPUESTA_RECOMENDADA | Mantener atomicidad y documentar resultado incierto. No recuperar secretos desde digests ni revertir confirmaciones; coordinar login/logout entre pestañas sin transmitir secretos. |
| IMPACTO_BACKEND | Conservar transacciones y locks; no usar commit en teardown/streaming o tareas de fondo para este flujo. |
| IMPACTO_FRONTEND | No reintentar ciegamente ante red/503; evitar borrado tardío de logout sobre cookie de login posterior. |
| PRUEBAS_DE_ACEPTACIÓN | Otra conexión ve commit antes de Set-Cookie, fallo diferido sin cookie, sesiones de otros dispositivos intactas, pérdida de acuse/carreras de pestañas. |
| RIESGO_SI_SE_APRUEBA | Decisión ya aprobada; pueden quedar sesiones confirmadas sin cookie recibida, sujetas a caducidad/limpieza operativa. |

### D14 — Renovación CSRF y reintento cliente

| Campo | Definición |
| --- | --- |
| DECISIÓN | Renovación preventiva y único reintento condicionado previo a efectos. |
| ESTADO | APROBADA en V1; tiempos/capacidades siguen provisionales. |
| COMPORTAMIENTO_ACTUAL | Adaptadores no reintentan. Solo marcan CSRF_INVALID antes de efectos de negocio en controles conocidos; infraestructura/commit no se marcan recuperables. |
| PROPUESTA_RECOMENDADA | Cliente coordina obtención en memoria; solo un reintento tras 403 CSRF_INVALID con continuidad de contexto confirmada. Ninguno por otro 403, timeout, red o 500/503. |
| IMPACTO_BACKEND | Conservar prueba de rechazo previo sin ocultar resultado incierto; renovar token no renueva actividad. |
| IMPACTO_FRONTEND | Coordinación en memoria y entre operaciones; no persistir token CSRF en almacenamiento web ni crear segundo mecanismo. |
| PRUEBAS_DE_ACEPTACIÓN | Cambio de sesión/contexto corta retry, segundo rechazo corta retry, cuota de tokens preservada y sin reintento tras commit incierto. |
| RIESGO_SI_SE_APRUEBA | Ya aprobado; interpretación amplia de cualquier 403 puede duplicar efectos o reutilizar contexto ajeno. |

### D15 — Operaciones cerradas e infraestructura

| Campo | Definición |
| --- | --- |
| DECISIÓN | Condiciones independientes para habilitar cada endpoint completo. |
| ESTADO | PENDIENTE_DE_EVIDENCIA operativa y de las propuestas anteriores. |
| COMPORTAMIENTO_ACTUAL | CSRF real registrado y cerrado; login/me/logout 404. Ni fábrica ni router importan candidatos. |
| PROPUESTA_RECOMENDADA | Mantener así hasta tarea explícita. CSRF/login dependen de IP acreditada; me/logout no requieren IP por analogía, pero sí canal/contrato completo y pruebas. Separar evidencia local de despliegue Render. |
| IMPACTO_BACKEND | Registro posterior por endpoint solo cuando esté completo; ninguna bandera de bypass ni sustitución productiva del fixture. |
| IMPACTO_FRONTEND | Puede preparar transporte con rutas cerradas; no presentar login funcional o dependencia IP resuelta. |
| PRUEBAS_DE_ACEPTACIÓN | 404 persistentes, csrf 503 sin token/cookie incluso al sustituir dependencia; futuro arnés separado sin modificar la app principal. |
| RIESGO_SI_SE_APRUEBA | Abrir un handler parcial convierte una limitación conocida en superficie pública insegura. |

### D16 — Responsabilidades y transporte común

| Campo | Definición |
| --- | --- |
| DECISIÓN | Next público, FastAPI autoridad, PostgreSQL persistente; transporte por petición. |
| ESTADO | APROBADA para mismo origen, SSR por petición, fetch cliente en mutaciones V1, secretos servidor y no-store; operación B Render sigue por acreditar. |
| COMPORTAMIENTO_ACTUAL | #30 ofrece proxy comodín/SSR; #32 tiene ruta específica y otro transporte. El específico prevalece y no hereda automáticamente controles del comodín. |
| PROPUESTA_RECOMENDADA | Compartir construcción segura del canal manteniendo validación y respuestas de búsqueda. No usar Server Actions ni fabricar Origin. |
| IMPACTO_BACKEND | Servicio y usuario separados también en búsqueda; mantener CSRF/autorización transaccional y errores de dominio compatibles. |
| IMPACTO_FRONTEND | Valentina prepara canal común; América adapta camino específico; ambas verifican aislamiento de cookies entre peticiones. |
| PRUEBAS_DE_ACEPTACIÓN | Proxy y SSR, ruta search específica, dos usuarios concurrentes, cabeceras filtradas, Set-Cookie separados y no-store en éxitos/errores. |
| RIESGO_SI_SE_APRUEBA | Ya aprobado en su alcance; duplicación de transportes deja controles divergentes y fallos fuera de la ruta cubierta. |

## Estado y cambios concretos por PR

Consulta de API GitHub y refs remotas en esta revisión: ambos abiertos, no draft,
no fusionados; HEAD sin avance respecto a D.1. No se modificaron sus ramas.

| PR | HEAD verificado | Archivos del árbol revisado que requieren trabajo posterior |
| --- | --- | --- |
| [#30](https://github.com/Krotzup/SynapDesk/pull/30) | 0f0105e5a14ec095f538bf1079a6439b3ccf9d40 | `frontend/src/lib/backend-proxy.ts`, `frontend/src/lib/transport/server.ts`, `frontend/.env.example`; pruebas de transporte. Revisar el registro en `frontend/src/app/api/v1/[...path]/route.ts` para asegurar que usa el canal común, aunque puede bastar cambiar el helper. |
| [#32](https://github.com/Krotzup/SynapDesk/pull/32) | ac9f02516becb8f1c4a02c149131835b8e8a6b2e | `frontend/src/lib/server/search-proxy.ts`, `frontend/src/app/api/v1/search/route.ts`, `backend/app/recuperacion/acceso.py`; pruebas y documentación/configuración de búsqueda, sin ML. |

### Valentina

- Añadir secreto SEC-01B privado y generado externamente; variable de servidor
  cuyo nombre debe acordarse, sin NEXT_PUBLIC_*, valor de ejemplo ni logs.
  Backend recibe solo digest, identificador y vigencia en AUTH_INTERMEDIARIO.
- Centralizar inyección en proxy y SSR. No copiar Authorization del navegador.
  Mantener lista cerrada de cabeceras y descartar todas las IP no acreditadas.
- Exigir HTTPS para SEC-01B y verificación CA/hostname. No desactivar validación;
  rechazar destino con credenciales/ruta/query/hash en lugar de normalizar una
  configuración errónea silenciosamente. No seguir redirecciones.
- Hacer explícito el perfil y probar cookies malformadas además de duplicadas.
  Ejemplo observado: filterCookieHeader descarta 'synapdesk_session_dev' sin '=';
  no debe convertirse en anónimo al coexistir una cookie de contexto válida.
  Conciliar también detección de mezcla de perfiles antes de filtrarlos.
- Conservar Set-Cookie individuales y borrados, Retry-After, no-store y error
  requestId backend. Definir cuerpo/admisión y plazo desde recepción: hoy
  request.arrayBuffer se ejecuta fuera del try y antes del timeout de fetch;
  el plazo de 30 s cubre salto backend y respuesta, no esa lectura inicial.
- SSR sigue siendo solo lecturas, con cookies por petición y sin Origin fabricado.
  No puede obtener CSRF o efectuar mutaciones durante render.

### América

- Hacer que el transporte específico use la construcción común de SEC-01B/TLS;
  no basta integrar el comodín. Conservar validación query/limit y parseo de
  respuesta de búsqueda, tamaño de cuerpo y errores propios compatibles.
- Backend de búsqueda debe verificar intermediario además de sesión, cuenta,
  permisos y CSRF actuales. No sustituir usuario por servicio ni delegar permiso
  en ML. Conciliar precedencia Origin/cookie y errores saneados antes de efectos.
- Alinear SEARCH_PUBLIC_ORIGIN, SEARCH_SESSION_COOKIE_NAME y AUTH_COOKIE_PROFILE
  entre Next y el backend (search_cookie_name deriva del perfil y de
  search_session_cookie_name). El booleano BACKEND_ALLOW_HTTP_LOCAL no puede
  autorizar bearer en claro. Verificar nombres efectivos al integrar configuración.
- El proxy reconstruye respuestas sin Set-Cookie: no reutilizarlo como transporte
  auth sin tratamiento específico. Búsqueda no debe renovar sesión automáticamente.
- Preservar requestId de backend válido y Retry-After; no reinterpretar cualquier
  403 o excepción de infraestructura como CSRF recuperable. Mantener pruebas de
  POST con sesión/CSRF vinculado y aislamiento de sesiones simultáneas.

## Plan concreto propuesto de AUTH-07D.2

No iniciado. Cada paso requiere encargo posterior; no constituye autorización de
modificar frontend, registrar rutas o desplegar en esta revisión.

| Orden | Trabajo | Dependencias y salida verificable |
| --- | --- | --- |
| 1 | Conciliación PO/equipo | Resolver D02, D04–D09, D11–D12 y detalles operativos de D13; registrar responsables y aprobación por decisión. D03 requiere evidencia, no voto. No reabrir P1–P15 de altas. |
| 2 | Arnés local de transporte | Node de prueba → Uvicorn TLS real con proxy_headers=False → PostgreSQL temporal localhost:5433. Certificados efímeros con CA/hostname verificados y limpieza. Usar operaciones/handlers completos de ensayo en aplicación separada; no registrar rutas de la app principal. |
| 3 | Canal común con Valentina | Inyección de servicio, TLS, filtros estrictos, configuración privada, SSR, límites y Set-Cookie; probar con arnés y rutas productivas aún cerradas. |
| 4 | Camino específico con América | Búsqueda usa el canal, backend añade servicio separado de usuario/CSRF; conservar contrato de búsqueda y no modificar ML. |
| 5 | Adaptación FastAPI autorizada | Composición por worker, config explícita, DTO/dependencias y precedencia acordadas, respuestas posteriores al commit; probar candidatos sin registrar rutas incompletas. |
| 6 | Evidencia real de ingreso | Operación TLS/red/secretos y procedencia IP en la arquitectura elegida; si Render no permite acreditar el canal actual, documentar y revisar topología antes de habilitar, sin X-Forwarded-Proto como sustituto. |
| 7 | Activación explícita por endpoint | Registrar únicamente los completos y aceptados según tabla inferior, pruebas de navegador y revisión humana. No retirar un cierre para facilitar ensayos. |

### Pruebas locales Node/FastAPI/PostgreSQL

Se puede construir y ejecutar el arnés sin suponer IP de Render. Los HEAD #30/#32
todavía no ofrecen el canal SEC-01B integrado: las pruebas Node de interoperabilidad
no se declaran superadas por las cuatro TLS Python existentes.

Mínimos: bearer/rotación/ausencia/duplicados; CA no confiable y hostname incorrecto;
HTTP/redirecciones; Origin válido/ausente/múltiple; cookies malformadas, entre
perfiles y repetidas sin normalización; CSRF ajeno/vencido/duplicado; sesión
revocada/inactiva; cuotas y Retry-After; requestId/422; lectura de cuerpo lenta y
excesiva; timeout/corte de respuesta sin retry; dos usuarios SSR; Set-Cookie
separados solo después de commit visible en otra conexión; fallo de auditoría o
constraint diferida real sin cookies de éxito. Un fixture puede representar IP
controlada del ensayo, nunca configurarse como adaptador productivo.

Navegador en ensayo: atributos/ámbitos y eliminación __Host-, flujo inicial y
reemplazo de sesión, memoria CSRF y continuidad, carreras login/logout entre
pestañas, expiración, SSR sin fugas, secretos ausentes de bundle/HTML/logs.

### Condiciones para cada endpoint

Todas requieren contrato conciliado, encargo de implementación/activación,
configuración completa, SEC-01B/TLS verificados, pruebas de seguridad y cookies/
errores/no-store según corresponda. No se registran handlers parciales.

| Endpoint | Condiciones adicionales | Si faltan |
| --- | --- | --- |
| GET /api/v1/auth/csrf | IP acreditada y fuente aprobada; bootstrap Origin/Sec-Fetch-Site; cuotas anónimas y admisión autenticada/saturación acordadas; recuperación/contexto y cookie técnica definidos; commit antes de token/cookie. | Conservar handler real cerrado, sin token/contexto/cookie; cambiar solo la dependencia IP no elimina su rechazo final. |
| POST /api/v1/auth/login | Bootstrap CSRF operativo y aprobado; IP/cuotas verificables, Origin, DTO/catálogo, Argon2 con capacidad medida, reemplazo/revalidación/atomicidad y cookies tras commit; proxy integrado. | Seguir 404, sin alta de ruta parcial o bypass de IP. |
| GET /api/v1/auth/me | Sesión/cuenta/rol revalidados; decisión explícita sobre actividad; perfil y lectura SSR acordados; no requiere IP por analogía con login ni token CSRF para lectura según propuesta. | Seguir 404 hasta completar su contrato/canal/pruebas; puede ensayarse con sesiones generadas solo por fixture interno en BD temporal, sin habilitar login productivo. |
| POST /api/v1/auth/logout | Origin incluso sin cookie; representación acordada, sesión válida + CSRF, idempotencia confirmada y caso inactivo conciliado; revocación/auditoría antes de borrado y prueba de carreras. No requiere cuota/IP nueva por analogía. | Seguir 404; no simular 204 ante fallo BD ni borrar cookie por 403. |

### Qué exige infraestructura real

Render debe demostrar ingreso observador de IP, saneamiento de todas las entradas
incluidas duplicadas, identidad/pares y rutas que pueden alcanzar Next/FastAPI,
rechazo de acceso directo/alternativo y TLS efectivo en salto privado con CA y
hostname. Documentar el generador del metadato y probar spoofing con clientes de
IP conocida. Un Request sintético HTTPS, la IP del socket Next→FastAPI o un bearer
válido no satisfacen esa acreditación. Red privada sola tampoco autentica origen.

Siguiente tarea implementable propuesta: **arnés local Node/FastAPI/PostgreSQL
con TLS real y aceptación del canal SEC-01B**, conservando la app principal y las
rutas cerradas. Puede abordar pruebas negativas del canal sin resolver IP Render;
las pruebas del flujo completo con IP de fixture deben etiquetarse como ensayo.
No se comienza ese trabajo automáticamente.
