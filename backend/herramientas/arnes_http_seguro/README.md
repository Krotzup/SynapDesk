# Arnés local seguro — AUTH-07D.2

Herramienta de ensayo explícita, separada de [app](../../app/), sin importación
desde la fábrica, registro de rutas productivas o modo de IP sintética. No
modifica frontend/ML ni las ramas de PR #30/#32. No aprueba contratos DRAFT.

## Ejecución reproducible

Requiere el entorno Python del backend con sus dependencias, PostgreSQL de
pruebas local en 5433 y POSTGRES_TEST_* ya configuradas, Node.js y dependencias
frontend ya instaladas, TypeScript y OpenSSL (sirve el de Git for Windows).
No instala paquetes, usa datos de desarrollo ni modifica archivos privados.

Desde backend, con el intérprete configurado del proyecto:

```powershell
./.venv/Scripts/python.exe -m herramientas.arnes_http_seguro.ejecutar
```

Una repetición debe elegir otro nombre de evidencia, sin sobrescribir anteriores:

```powershell
./.venv/Scripts/python.exe -m herramientas.arnes_http_seguro.ejecutar --reporte auth07d2-arnes-repeticion.json
```

El nombre está restringido y solo se escribe bajo docs/auditorias. No se reciben
credenciales por argumentos. En ejecución automatizada Windows se necesitan
permisos para iniciar y terminar los procesos propios; el sandbox de Codex puede
requerir ejecución autorizada fuera del sandbox. No desactivar los controles para
sortear esa limitación. Si falla una fase, revisar el reporte y la limpieza antes
de repetir; no ignorar un error de recursos.

La ejecución histórica D.2 fue validada en Windows. Las versiones verificadas fueron Node 24.22.1, Next 16.3.4,
TypeScript 5.9.3, Python 3.12.10 y PostgreSQL 17.11. No se certifican otras
combinaciones mediante esta ejecución. El salto privado usa TLS real y una CA
efímera. El ingreso Next del ensayo es HTTP sobre loopback: **no certifica HTTPS
público ni el comportamiento de un navegador con cookies Secure**.

## Recorridos y componentes

1. Cliente Node HTTPS → Uvicorn TLS → dependencias/sondas → PostgreSQL temporal.
2. Cliente HTTP Node → Next real → proxy/SSR real de PR #30 → Uvicorn TLS.
3. Cliente HTTP Node → ruta sustituta de ensayo Next → SEC-01B/TLS → FastAPI →
   PostgreSQL, para éxito de servicio y validación CSRF persistente sin efectos.

Se obtienen copias exactas con git show de PR #30, HEAD
`0f0105e5a14ec095f538bf1079a6439b3ccf9d40`:

- frontend/src/lib/backend-proxy.ts.
- frontend/src/lib/transport/server.ts.
- frontend/src/app/api/v1/[...path]/route.ts.

Se registran SHA-256 y blobs Git; TypeScript solo compila esas copias a JavaScript.
No se altera su algoritmo, tiempo de espera ni filtros. Next real resuelve
server-only, next/headers y el alias de imports. La aplicación mínima temporal,
layout, páginas SSR y sondas de disponibilidad son del arnés. Se usan webpack y
NODE_PATH del proceso para leer dependencias instaladas; no hay junctions ni
escrituras en frontend/node_modules. Las cachés viven en el directorio propio.
Next se ejecuta con dev --webpack: no se certifica un build de producción.
El escenario production comprueba el perfil de cookies, no un despliegue productivo.

La ruta **/ensayo-canal/** es un sustituto explícito, no una corrección del proxy
de Valentina. Añade credencial de servidor desde un archivo privado temporal y
solo admite destinos fijos de servicio, CSRF cerrado y control CSRF sin efectos.
No acepta IP, usuario, rol o destino elegidos por el navegador como autoridad.
No registra login/me/logout, ni con nombres alternativos para emitir sesiones.

Las sondas FastAPI /api/v1/ensayo/* pertenecen a una aplicación aislada del runner:
observan representación de cookies/cabeceras, consultan esquema, validan contextos
CSRF precreados y producen fallos controlados. Eco no autentica usuarios; las
cookies de emisión/borrado son marcadores aleatorios, **no sesiones creadas**.
La sonda de cookie comprueba transporte/atributos, no un login. El recorrido
persistente real de adaptadores/login/logout y cookies tras commit se conserva
en las ocho pruebas PostgreSQL D.1 de la suite general.

Las sondas de clave vencida/otro entorno primero validan el canal normal y luego
ejercitan el mismo verificador con política caducada/entorno incompatible; no
permiten seleccionar una política productiva. Los contextos CSRF válido/vencido
se crean internamente en la base exclusiva mediante ServicioCsrf. Ninguna ruta
genera un token de producción o construye IpVerificada.

## Aislamiento y limpieza

- Base aleatoria propia, prefijo synapdesk_auth07_sec01a_, host loopback y cliente
  5433 exigidos; identidad verificada antes de migración o eliminación. Alembic
  upgrade/current/heads/check, cabeza 0006 y catálogo user_created comprobados.
- Directorio backend/.arnes-auth07d2-UUID, ignorado por Git. CA/clave raíz,
  certificado/clave de servidor, credenciales y proyectos Next temporales.
- CA confiada mediante opción ca del cliente HTTPS y NODE_EXTRA_CA_CERTS solo
  del proceso Next de ensayo. No se modifica almacén del equipo o entorno global;
  se eliminan opciones Node inseguras heredadas. Nunca se desactiva verificación.
- Credenciales SEC-01B/HMAC/contextos nuevas en cada ejecución. Las claves de
  servicio se guardan solo temporalmente; backend usa sus digests por entorno.
  No se usa ninguna credencial real de usuario o intermediario.
- Listeners sobre 127.0.0.1 en puertos efímeros. Uvicorn termina TLS con
  proxy_headers=False y acceso sin logs. Se detienen hilo y procesos/subárboles
  propios, sin matar por nombre o puerto global.
- Logs Next y salida Node se revisan contra secretos del fixture antes de
  conservar resultados saneados. Se retiran carpetas propias verificadas sin
  seguir enlaces, y se comprueba ausencia de la base y recursos.

Los procesos tienen plazos y se terminan también ante fallos. En Windows se usa
taskkill /PID del hijo creado /T /F; el permiso de proceso no implica permiso para
recursos ajenos. Un fallo de limpieza queda registrado y hace fallar la ejecución.

## Matriz de requisitos y diferencias observadas

Los estados describen el ensayo histórico contra el SHA de PR30 fijado arriba,
incompatibilidad o evidencia pendiente; no aprobación ni validación de cambios
posteriores de PR30. Resultado histórico D.2: 75 casos aprobados, cero fallos y
cero omitidos. La validación backend separada registró 660 pruebas unitarias y
351 de integración (incluidas cuatro TLS): total histórico 1086. Estos números
no representan una nueva ejecución por consolidar esta documentación.

La tabla conserva IDs verificables en [casos Node](casos_node.mjs). Los informes
detallados generados bajo docs/auditorias son auxiliares locales excluidos de
este entregable; no se requieren para comprender o repetir los casos. Los
aciertos que caracterizan defectos confirman su reproducción, no su corrección.

| REQUISITO | COMPORTAMIENTO ESPERADO | COMPORTAMIENTO OBSERVADO | EVIDENCIA | COMPONENTE RESPONSABLE | ESTADO | CORRECCIÓN REQUERIDA |
| --- | --- | --- | --- | --- | --- | --- |
| TLS | CA/hostname válidos; rechazo de identidad incorrecta | Node directo y Next real aceptan CA propia y rechazan CA desconocida/hostname; sin degradación | TLS_CA_HOSTNAME_Y_POSTGRESQL, TLS_CA_NO_CONFIADA, TLS_HOSTNAME_INCORRECTO, PR30_CANAL_RECHAZADO_* | Canal Node/FastAPI | VERIFICADO_LOCAL | Acreditar TLS privado real en Render; mantener verificación. |
| SEC-01B | Servicio privado presenta una credencial válida | Cliente y sustituto Next validan; ausente/incorrecta/vencida/duplicada/esquema/entorno rechazados; dos claves admitidas | SEC01B_*, NEXT_SUSTITUTO_SEC01B_TLS_POSTGRESQL | Next servidor / FastAPI | VERIFICADO_LOCAL; proxy pendiente | Añadir inyección en PR30/SSR y PR32. |
| Servicio vs usuario/IP | Bearer no acredita otras identidades | Sonda devuelve user_identity=false/ip_verified=false; CSRF real continúa 503 | CSRF_PRODUCTIVO_CERRADO_CON_SEC01B, IP_NO_ACREDITADA_* | FastAPI / infraestructura | CIERRE_VERIFICADO | No añadir cabecera IP supuesta. |
| Proxy PR30 autenticado | Eliminar Authorization cliente y añadir la propia | Elimina cliente pero no genera credencial; sonda protegida recibe 503 | PR30_SIN_CREDENCIAL_SERVICIO | Valentina | INCOMPATIBILIDAD_REPRODUCIDA | Secreto privado de servidor, emisión única en proxy/SSR. |
| Cookies duplicadas | No elegir valor | Proxy conserva duplicados con '=', FastAPI rechaza | PR30_COOKIE_RECHAZADA_DUPLICADA, COOKIE_BACKEND_RECHAZA_DUPLICADA | Proxy / FastAPI | VERIFICADO_LOCAL | Conservar representación; conciliar código de rechazo. |
| Cookie malformada | Rechazar sin convertir en anónimo | Backend rechaza nombre sin '='; filtro PR30 lo descarta y conserva contexto anónimo | COOKIE_BACKEND_RECHAZA_SIN_IGUAL frente a PR30_PIERDE_COOKIE_MALFORMADA | Valentina | INCOMPATIBILIDAD_REPRODUCIDA | Rechazar o preservar evidencia antes de filtrar, sin recuperación implícita. |
| Mezcla de perfiles | Rechazo inequívoco | Backend detecta perfil ajeno; proxy elimina ese nombre y oculta mezcla | COOKIE_BACKEND_RECHAZA_PERFIL_AJENO frente a PR30_OCULTA_MEZCLA_PERFILES | Valentina / contrato cookies | INCOMPATIBILIDAD_REPRODUCIDA | Acordar detección previa al filtro y rechazo compatible. |
| Otras cookies inválidas | No aceptar una representación ambigua | Vacía/codificación inválida y comillas rechazadas en backend; vacía/codificación atraviesan proxy y se rechazan | COOKIE_BACKEND_RECHAZA_*, PR30_COOKIE_RECHAZADA_* | FastAPI / proxy | VERIFICADO_LOCAL | Clasificación CookieAmbigua continúa candidata 500; conciliar antes de abrir. |
| Set-Cookie | Separados, solo perfil permitido, también borrado | Dos permitidos conservados, desconocida/otro perfil descartados; atributos y Max-Age=0 correctos | PR30_SET_COOKIE_LOCAL/PRODUCTION, PR30_BORRADO_COOKIE_* | Proxy / AUTH-07A | VERIFICADO_LOCAL | Validar navegador y flujo de sesión real posteriormente. |
| Origin y CSRF | Rechazo antes de efectos y vínculo persistente | Validación positiva/negativa directa y por sustituto; Origin ausente/inválido precede servicio | ORIGIN_*, CSRF_*, NEXT_SUSTITUTO_*, PR30_ORIGIN_* | FastAPI / canal | VERIFICADO_LOCAL | Conciliar precedencia DTO y políticas de recuperación pendientes. |
| Errores y no-store | ApiErrorBody saneado, UUID servidor y sin secretos | BD real fallida, serialización, servicio/TLS/timeout/redirección conservan rechazo; cabecera cliente ignorada | ERROR_*, REQUEST_ID_NO_CLIENTE, PR30_ERROR_*, PR30_REDIRECCION_RECHAZADA | FastAPI / Next | VERIFICADO_LOCAL | Mantener catálogos compatibles; no interpretar resultado incierto como falta de efectos. |
| Timeout | Limitar backend y recepción del cliente | Timeout real 30 s del proxy comprobado; código lee request.arrayBuffer antes del plazo/try | PR30_TIMEOUT_REAL_30S y fuente PR30 | Valentina | PARCIAL; recepción pendiente | Definir límites y plazo de admisión, con errores acordados. |
| SSR | Identidad por petición y canal seguro | Server Component real usa transporte PR30 y aísla cookies; no envía Origin; no inyecta servicio | PR30_SSR_REAL_AISLADO, PR30_SSR_SEC01B_AUSENTE | Valentina | AISLAMIENTO_VERIFICADO; SEC01B_PENDIENTE | Usar mismo canal privado, sin mutaciones o Origin fabricado en SSR. |
| Persistencia | Esquema/catálogo reales y atomicidad | Migración 0006, lectura por canal, CSRF en PostgreSQL; suite D.1 conserva pruebas reales de commits/rollback | schema_head, user_created_catalog_present; suite PostgreSQL | FastAPI / PostgreSQL | VERIFICADO_LOCAL | Medición/operación futuras; sin migración nueva. |
| IP local/Render | Distinguir ingreso observado y procedencia | Socket local visible para Node, no propagado como autoridad; Render no probado | client_ip_local/client_ip_render | Infraestructura | PENDIENTE_DE_EVIDENCIA | Probar generador, saneamiento, pares/caminos y TLS efectivo en Render. |
| Rutas productivas | No habilitar incompletas | Login/me/logout 404; CSRF 503 aun con servicio válido | RUTA_PRODUCTIVA_AUSENTE_*, CSRF_PRODUCTIVO_CERRADO_CON_SEC01B | FastAPI | CIERRE_VERIFICADO | Otra tarea explícita con condiciones completas. |

## Instrucciones para Valentina — PR #30

Imprescindible antes de usar auth real:

1. frontend/src/lib/backend-proxy.ts: inyección de credencial privada; HTTPS
   y destino fijo estricto; no copiar Authorization/IP del navegador; corregir
   cookies malformadas y mezcla antes de filtrar. Conservar Set-Cookie separados.
2. frontend/src/lib/transport/server.ts: misma credencial/TLS en cada petición,
   cookies aisladas y lectura SSR sin Origin fabricado, sin mutaciones.
3. frontend/.env.example: nombres/operación acordados sin valores secretos y sin
   perfil local implícito productivo. BACKEND_INTERNAL_URL solo servidor;
   rechazar credenciales/ruta/query/hash inesperados en configuración del destino.
4. Verificar frontend/src/app/api/v1/[...path]/route.ts usando el helper común;
   aplicar admisión del cuerpo/plazo total con errores saneados y acuerdo previo.
5. Mantener Origin/CSRF original permitido, requestId backend, Retry-After,
   no-store, rechazo de redirecciones y ausencia de reintentos de mutación.
6. Repetir casos SEC01B, TLS, cookies defectuosas, SSR y límites con su canal
   actualizado. Un éxito del sustituto no valida una modificación todavía ausente.

Mejoras posteriores: medir presupuestos por operación, observabilidad sin
secretos, coordinación multitab y pruebas de navegador. No añadir acreditación
IP hasta disponer de evidencia: bearer no la proporciona.

## Instrucciones para América — PR #32

El HEAD inspeccionado es `ac9f02516becb8f1c4a02c149131835b8e8a6b2e`; no se ejecutó
ni modificó su recuperación/ML. La ruta específica precede al comodín #30.

- frontend/src/lib/server/search-proxy.ts y frontend/src/app/api/v1/search/route.ts:
  adoptar construcción común del canal SEC-01B/TLS, reduciendo duplicación;
  conservar límites, parseo y respuestas propios de búsqueda.
- backend/app/recuperacion/acceso.py: verificar intermediario aparte de sesión
  persistente, cuenta/rol/autorización y CSRF actuales. No delegar confianza a ML.
- Alinear AUTH_COOKIE_PROFILE y SEARCH_SESSION_COOKIE_NAME en ambos extremos,
  SEARCH_PUBLIC_ORIGIN con los orígenes backend; revisar precedencia Origin/cookie
  y errores. BACKEND_ALLOW_HTTP_LOCAL no permite bearer en claro.
- Preservar requestId/Retry-After y saneamiento; su reconstrucción de respuesta
  sin Set-Cookie no sirve para auth sin una política específica. No renovar
  actividad o cambiar el contrato de búsqueda incidentalmente.
- Aceptación: cookie/CSRF ajenos y duplicados rechazados, sesión revocada/inactiva,
  servicio ausente/incorrecto, TLS inválido, respuesta y errores de búsqueda,
  aislamiento concurrente, no-store y cierre si una futura cuota exige IP.

## Contratos y siguiente incremento

La [formalización D.3](../../../docs/contratos/auth07d3-compatibilidad-y-plan-integracion.md)
sustituye las decisiones candidatas de la
[matriz D.1/D.2](../../../docs/contratos/auth07d2-matriz-decisiones-y-plan.md):
P1–P10 están aprobadas, incluyendo rechazo de cookies ambiguas, ausencia de
recuperación automática, /me sin renovación y logout de cuenta inactiva. Esta
última política P4 todavía no está implementada. C01–C09 permanecen pendientes:
representaciones DTO/cookies/errores, cuotas/admisión, presupuestos, operación
SEC-01B, evidencia Render y detalles Origin/correlación. La prueba local no
ratifica esas propuestas ni mide valores productivos de Argon2/cuotas.

Incremento separado propuesto: resolver los detalles aplicables y adaptar el canal
común de PR30/PR32 con las pruebas reproducidas. Puede hacerse con rutas auth aún
cerradas. Me/logout no requieren IP por analogía, pero sí su contrato/canal
completo; csrf/login necesitan además procedencia IP y cuotas verificables.

Render debe aportar evidencia del generador de IP, saneamiento de entradas y
duplicados, pares/caminos alternativos y acceso directo, TLS privado/CA/hostname,
red y rotación. HTTPS público, red privada o cabeceras sin cadena demostrada no
bastan. Esta herramienta no inicia implementaciones ni habilita rutas.
