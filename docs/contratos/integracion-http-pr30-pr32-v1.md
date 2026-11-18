# Responsabilidades Next.js–FastAPI e integración PR30/PR32 — V1

**Acuerdo formalizado dentro del alcance aprobado AUTH-07D.3.** Arquitectura B,
SEC-01B y políticas HTTP P1–P10 aprobadas por Product Owner. Detalles C01–C09
continúan como propuestas/evidencia pendiente en la
[matriz de compatibilidad y plan](auth07d3-compatibilidad-y-plan-integracion.md).
No se aprueban por esta especificación cifras, DTO nuevos, nombres de variables
privadas o una fuente IP supuesta. No se modifican los PR ni se habilitan rutas.

Se coordina con [HTTP V1](autenticacion-http-adaptadores-v1.md),
[autenticación](autenticacion-v1.md), [contrato general](frontend-backend.md) y
[SEC-01B](comunicacion-interna-segura-v1.md).

## 1. Fuentes y vigencia de la inspección

Refs y API GitHub consultadas el 13-11-2026: ambos PR abiertos, no draft, sin
fusionar. Se leyeron objetos Git sin checkout ni modificaciones de sus ramas.
Si un HEAD avanza, repetir revisión y pruebas sobre el SHA nuevo antes de merge.

| PR | HEAD revisado | Fuentes exactas del PR |
| --- | --- | --- |
| [#30, Valentina](https://github.com/Krotzup/SynapDesk/pull/30) | 0f0105e5a14ec095f538bf1079a6439b3ccf9d40 | [backend-proxy.ts](https://github.com/Krotzup/SynapDesk/blob/0f0105e5a14ec095f538bf1079a6439b3ccf9d40/frontend/src/lib/backend-proxy.ts), [transport/server.ts](https://github.com/Krotzup/SynapDesk/blob/0f0105e5a14ec095f538bf1079a6439b3ccf9d40/frontend/src/lib/transport/server.ts), [Route Handler](https://github.com/Krotzup/SynapDesk/blob/0f0105e5a14ec095f538bf1079a6439b3ccf9d40/frontend/src/app/api/v1/%5B...path%5D/route.ts), [.env.example](https://github.com/Krotzup/SynapDesk/blob/0f0105e5a14ec095f538bf1079a6439b3ccf9d40/frontend/.env.example) |
| [#32, América](https://github.com/Krotzup/SynapDesk/pull/32) | ac9f02516becb8f1c4a02c149131835b8e8a6b2e | [search-proxy.ts](https://github.com/Krotzup/SynapDesk/blob/ac9f02516becb8f1c4a02c149131835b8e8a6b2e/frontend/src/lib/server/search-proxy.ts), [ruta search](https://github.com/Krotzup/SynapDesk/blob/ac9f02516becb8f1c4a02c149131835b8e8a6b2e/frontend/src/app/api/v1/search/route.ts), [acceso.py](https://github.com/Krotzup/SynapDesk/blob/ac9f02516becb8f1c4a02c149131835b8e8a6b2e/backend/app/recuperacion/acceso.py), [configuración](https://github.com/Krotzup/SynapDesk/blob/ac9f02516becb8f1c4a02c149131835b8e8a6b2e/backend/app/configuracion.py) |

Estas rutas pertenecen a los árboles de PR, no a funcionalidad integrada en la
rama actual. La [guía reproducible D.2](../../backend/herramientas/arnes_http_seguro/README.md)
documenta los recorridos del transporte, los casos y sus resultados históricos.
Los informes detallados se conservan como auxiliares locales excluidos de Git;
las limitaciones y diferencias necesarias para integrar están descritas aquí.
El éxito SEC-01B del sustituto Next no acredita inyección en PR30; PR32 solo tiene
inspección estática en ese ensayo.

## 2. Responsabilidades definitivas en el alcance aprobado

| Componente / responsable | Debe cumplir | Evidencia y frontera |
| --- | --- | --- |
| Navegador / integración frontend posterior | Rutas relativas /api/v1, cookies HttpOnly administradas por navegador; CSRF en memoria para mutaciones, Origin real; sin contraseñas/hash/tokens de sesión en almacenamiento web | No puede elegir backend, rol, identidad, credencial de servicio o IP acreditada. No retry automático de escrituras. |
| Next proxy / Valentina | Destino fijo privado de servidor, credencial SEC-01B propia, TLS CA/hostname, filtrado sin ocultar ambigüedad, Set-Cookie separados, no-store, errores/correlación y presupuesto de canal | No autoriza usuario ni fabrica Origin/IP. Debe cerrar ante configuración incompleta; no perfil local por omisión en producción. |
| Next SSR / Valentina | Mismo canal SEC-01B/TLS; cookies originales por petición; solo lecturas y sin caché compartida | No mutaciones ni bootstrap CSRF durante render; no Origin inventado, identidad global o propagación supuesta de Set-Cookie al navegador. |
| Next search / América | Reutilizar construcción común del canal; conservar DTO/validación y errores de búsqueda | Ruta específica precede al comodín: necesita adaptación propia y pruebas, no hereda seguridad por merge de PR30. |
| FastAPI / backend | Verificar SEC-01B, Origin, cookies, sesión/cuenta/rol y CSRF según endpoint; IP solo si acreditada y requerida; cuotas persistentes, auditoría y commit antes de cookies | El bearer no autoriza usuario, no prueba IP. No cambia consumo de cuotas o semántica de sesión por integrar transporte. |
| PostgreSQL / backend | Autoridad persistente, esquema 0006, restricciones/locks y atomicidad de efectos/auditoría | Error no se interpreta como ausencia o credenciales inválidas. Sin nuevas migraciones en D.3. |
| Infraestructura / equipo operador | Backend privado, TLS efectivo, secretos por entorno/rotación, fuente IP y caminos de ingreso demostrables | Render pendiente de evidencia; red privada sola no autentica emisor ni prueba IP. |
| Product Owner / equipo | Decisiones C01–C09 y valores operativos todavía pendientes, permisos de negocio que correspondan | No reabrir P1–P10; aprobación documental no sustituye evidencia Render o medición de recursos. |

No se exige a Valentina o América confiar en una cabecera IP aún no acreditada.
Las mutaciones V1 usan fetch cliente vía proxy, sin Server Actions/Functions de
negocio. Autorización y transacciones permanecen en FastAPI.

## 3. Implementación lista para asignar a Valentina — PR #30

### A. Canal de servicio y configuración

Cambiar `frontend/src/lib/backend-proxy.ts` (`getBackendOrigin`,
`getBackendConfig`, `proxyToBackend`) y `frontend/src/lib/transport/server.ts`
(`backendFetch`, `getTransport`) del HEAD indicado; revisar que el Route Handler
comodín siga delegando en el helper común. Centralizar política de canal para
proxy y SSR. No duplicar el secreto o divergencias de validación entre caminos.

1. Descartar Authorization del navegador y generar exactamente una
   Authorization: Bearer de servidor después de aplicar la lista de cabeceras.
   La credencial opaca es exclusiva de entorno/destino, no cookie ni sesión.
2. Cargar desde configuración privada solo servidor, con import server-only;
   el nombre de variable está pendiente C07, no existe aún variable operativa
   acordada. Nunca NEXT_PUBLIC_*, URL, HTML, bundle, respuesta, excepción o log.
   No valores predeterminados ni credenciales de ejemplo utilizables.
3. Backend conserva solo digests, identificador y vencimiento en
   AUTH_INTERMEDIARIO/APP_ENV. Rotación: desplegar digest nuevo, admitir como
   máximo dos entradas vigentes, actualizar emisores y retirar anterior según
   procedimiento/vigencias que se acuerden; no selector controlado por cliente.
4. Rechazar configuración incompleta antes de enviar: 503 saneado, no fallback
   al backend público o a una credencial de otro entorno. La ausencia de
   secreto no habilita modo anónimo de servicio.
5. Hacer AUTH_COOKIE_PROFILE explícito y alineado con FastAPI; el default local
   observado no debe decidir producción. Ratificar nombres C02 antes de fijarlos
   como interfaz definitiva.

### B. TLS y destino

`BACKEND_INTERNAL_URL` ya existe en el PR y es solo servidor. Rechazar URL con
usuario/contraseña, ruta distinta de /, query/hash, esquema no HTTPS o destino
no autorizado; no normalizar esos errores mediante url.origin. Mantener /api/v1
una sola vez, métodos/rutas permitidos y destino no controlado por entrada.

Verificar CA y hostname del certificado en toda llamada SEC-01B, incluida local.
Confianza de prueba limitada al proceso/cliente del arnés; no almacén global.
Nunca NODE_TLS_REJECT_UNAUTHORIZED=0, verify=False o equivalente. Rechazar
redirecciones sin seguirlas con bearer/cookies; no degradar a HTTP.
Actualizar `frontend/.env.example` del PR para describir requisitos sin secretos;
el HTTP local actual no sirve para el nuevo canal. El ingreso navegador/Next
local y el salto de servicio son perfiles distintos.

El cliente TLS concreto puede configurarse según la API Node admitida y medirse
con la versión instalada; esta especificación no impone una biblioteca nueva.
Si Render no admite el TLS directo requerido por SEC-01B actual, revisar
explícitamente topología/contrato antes de integrar, sin confiar en
X-Forwarded-Proto como parche.

### C. Cookies: corregir antes de filtrar

`filterCookieHeader` conserva duplicados con '=', pero borra una cookie de
sesión sin '=' y elimina nombres reservados de otro perfil. D.2 lo demuestra:

- PR30_PIERDE_COOKIE_MALFORMADA: sesión malformada + contexto válido llega a
  backend como si no se hubiera presentado la sesión.
- PR30_OCULTA_MEZCLA_PERFILES: desaparece evidencia del perfil ajeno.

Antes de la lista permitida, validar representación original, todas las
ocurrencias de cookies reservadas y mezcla de perfiles; rechazar en Next con
clasificación acordada o preservar evidencia suficiente para rechazo backend.
No enviar todas las cookies ajenas como solución. No elegir primer/último valor,
reparar por percent-decoding, suprimir cookie inválida ni pasar por un cookie jar
que deduplique. Si el runtime ya plegó cabeceras, tratar ambigüedad como rechazo;
demostrar con solicitudes crudas cómo llegan duplicados y múltiples Cookie.

El backend mantiene la comprobación propia. La clasificación de CookieAmbigua
C03 sigue pendiente (500 saneado actual; propuesta 422 VALIDATION_ERROR). No
inventar COOKIE_INVALID ni publicar un código nuevo sin acuerdo. Los rechazos
no emiten cookies de éxito ni cambian a usuario anónimo.

Conservar `headers.getSetCookie()` y append por cookie, incluidos Max-Age=0 y
cada borrado. Filtrar solo nombres autorizados de respuesta sin alterar
Secure/HttpOnly/SameSite=Lax/Path=/ ni introducir Domain para __Host-. Mismo perfil
para entrada, emisión y borrado. No registrar valores o cabeceras completas.
Revisar el warning actual de Set-Cookie desconocido: usa un nombre extraído del
backend sin acotar; sanear/limitar metadatos o registrar solo un conteo fijo.
Esto es observación estática adicional, no una filtración de secreto demostrada.

### D. Cabeceras, Origin, CSRF y SSR

Lista de petición común actual: Accept, Content-Type, Origin, Sec-Fetch-Site,
X-CSRF-Token y cookies autorizadas; Authorization se genera aparte en servidor.
Eliminar Host, Authorization cliente, Forwarded, X-Real-IP, X-Forwarded-* y
supuestas cabeceras internas IP. No reenviar X-Request-ID cliente como autoridad.
Una futura cabecera IP requerirá contrato/evidencia separados; hoy ninguna.

Conservar Origin original, no suplantarlo con configuración o Host. Un POST sin
Origin debe llegar al rechazo del contrato; Sec-Fetch-Site no es sustituto.
Conservar/rechazar ambigüedad de Origin y X-CSRF-Token, nunca elegir un valor.
FastAPI valida contexto/token/sesión; Next no crea otra protección CSRF.

SSR utiliza cookies originales de la petición actual y mismo canal privado;
no guardar cookies/identidad globalmente. No inventar Origin para lectura ni
hacer login/logout/obtención de CSRF durante render. Los Set-Cookie de un fetch
SSR no se propagan automáticamente: canalizar emisiones por respuesta proxy al
navegador. /me sin actividad P3 y sin recuperación P2.

### E. Respuestas, correlación y tiempos

Conservar ApiErrorBody backend con su requestId, sin reconstruir el error para
perder correlación. En errores propios de Next usar UUID nuevo, mensaje seguro
y details null; no afirmar que backend audita ese mismo UUID. No introducir una
cabecera de correlación hasta acordarla. Success AuthUser sigue dentro de user,
sin campos adicionales. No-store en éxito/error/204 y fetch de servidor.
Preservar Retry-After válido de backend, sin fabricar espera ni replay automático.

30 s es el plazo provisional actual para fetch y lectura de respuesta, no un
presupuesto productivo aprobado. `request.arrayBuffer()` se ejecuta antes del
try/deadline y sin límite propio: acotar recepción, tamaño y procesamiento según
C05/C06. Definir plazo total por operación y distinguir conexión/TLS, espera,
lectura/serialización y respuesta. El tramo exterior debe cubrir al interior con
margen medido, sin garantizar rollback por abortar fetch.

Timeout, red, TLS, redirección y serialización reciben error saneado sin éxito
parcial; no exponer error original/URL privada/certificado/secretos. No repetir
login/logout ni otra escritura ante 403, 429, 500/503, corte o resultado incierto.
La renovación preventiva CSRF no reenvía automáticamente la solicitud original.

### F. Aceptación y condición de merge

Aplicar A01–A14/A17/A19 de la [matriz](auth07d3-compatibilidad-y-plan-integracion.md#7-matriz-de-aceptación-reproducible).
Agregar pruebas unitarias de configuración, URL hostil, filtros estrictos antes
de normalizar, cabeceras duplicadas, dos perfiles y secreto ausente de salidas.
Ejecutar Node/Next reales con CA/hostname y PostgreSQL temporal, sobre el **nuevo
HEAD fijado**: proxy y SSR deben validar SEC-01B sin sustituto para reclamar
conformidad. Mantener pruebas del HEAD anterior como caracterización.

Probar backend ausente/TLS inválido, redirección, cuerpo lento/excesivo y timeout
completo; Set-Cookie múltiples/borrado; SSR dos usuarios y caché; errores,
requestId/no-store/Retry-After. El conjunto futuro debe convertir los cuatro
casos incompatibles en aceptación de la corrección, sin eliminar el rechazo
backend. Verificar build/bundle de producción y navegador en fase autorizada;
D.2 no los certificó.

Imprescindible para integrar auth: canal seguro en ambos caminos, cookies P1/P2,
configuración cerrada y contrato de errores/DTO acordado. Condiciones para merge
del transporte: revisión del diff, pruebas de su HEAD, sin rutas auth abiertas
ni disminución de controles; no bloquear esa corrección por no inventar IP.
Instrumentación adicional/optimización de pools son mejoras futuras. Todo merge
real queda fuera de este encargo.

## 4. Implementación lista para asignar a América — PR #32

### Canal específico y preservación del dominio

Cambiar `frontend/src/lib/server/search-proxy.ts` (`forwardSemanticSearch`) y
`frontend/src/app/api/v1/search/route.ts` del HEAD indicado para reutilizar la
construcción segura del canal de PR30. La ruta específica search prevalece al
comodín; un merge del proxy genérico no incorpora SEC-01B allí.

Extraer/reutilizar configuración de destino, credencial servidor, TLS, filtros
estrictos de cookies/cabeceras, errores de canal, no-store y presupuesto común,
sin duplicar otro bearer, cookie parser permisivo o fallback HTTP. Conservar
validación de dominio query/limit, cuerpo de hasta 8192 bytes actual, UTF-8
estricto y parseSearchResponse. No adoptar esos límites como contrato login ni
cambiar el contrato de búsqueda incidentalmente.

El transporte actual usa un solo Cookie seleccionado y omite nombres ajenos al
perfil antes de detectar mezcla; debe adoptar P1 sobre evidencia original.
También debe rechazar cookie de sesión malformada que coexista con otra válida.
No convertir el POST de búsqueda en anónimo ni permitirlo por bearer de servicio.
Conservar CSRF vinculado a sesión y Origin exacto; no usar contexto anónimo.

### Backend y autorización

En `backend/app/recuperacion/acceso.py` (`autorizar_busqueda`,
`session_credential`, `header_values`) reutilizar las primitivas comunes de
frontera y verificar intermediario aparte de sesión/cuenta/rol/CSRF. Mantener
transacción de autorización junto al trabajo que protege, revalidación tras
locks y permisos de búsqueda/alcance de corpus acordados. Si falta una política
de recurso, denegar por defecto; el rol admin/agent por sí solo no define todos
los permisos del producto. No delegar autorización al módulo ML.

Actualmente inspecciona cookie antes de Origin. Alinear Origin previo a efectos
y servicio separado conforme al canal común; probar pares de fallos para no
crear un oráculo. La precedencia exacta de búsqueda se concilia con su contrato,
no se impone el orden de login a todas las rutas. Reutilizar lector estricto
común sin relajar consulta general para implementar la excepción P4, que es
solo logout. Cuenta inactiva/revocada/vencida no busca ni renueva sesión.

No crear una exigencia IP por analogía: solo si una cuota/operación aprobada la
requiere; en ese caso cerrar hasta acreditarla. No leer Forwarded/X-Real-IP/
X-Forwarded-For para fabricarla. No alterar recuperación/ML.

### Configuración y respuestas

Alinear variables reales `BACKEND_INTERNAL_URL`, `SEARCH_PUBLIC_ORIGIN`,
`SEARCH_SESSION_COOKIE_NAME` y `AUTH_COOKIE_PROFILE` entre Next y backend.
En el backend del PR, `search_cookie_name` es propiedad derivada de
`search_session_cookie_name` y `auth_cookie_profile`; **no existe variable
SEARCH_COOKIE_NAME**. Perfil y nombre explícito incompatible deben cerrar.
`BACKEND_ALLOW_HTTP_LOCAL` no autoriza transportar SEC-01B sin TLS. Añadir
configuración privada común del servicio solo cuando C07 se concrete.

El proxy actual reconstruye errores propios de búsqueda y conserva requestId
backend si el formato es válido; mantiene Retry-After validado. Preservar el
sobre general y códigos del contrato de búsqueda sin inventar equivalencias;
DEPENDENCY_UNAVAILABLE/SEARCH_* no se renombran silenciosamente a códigos auth.
503 se maneja por estado, sin retry automático de POST. Respuesta exitosa sigue
items y su DTO existente; no agregar AuthUser al resultado de búsqueda.

No-store siempre y aislamiento por petición. El proxy search no transmite
Set-Cookie: eso es compatible con lectura sin renovación, pero no sirve como
transporte de login/logout/bootstrap sin política específica. Esos flujos deben
usar el canal auth que sí preserva cada Set-Cookie. No renovar actividad de
búsqueda por la aprobación P3 de /me: P3 no aprueba cambios de otras operaciones.

### Aceptación y condición de integración

Tests unitarios de configuración, validación query/limit y respuesta, errores de
dominio, perfil/duplicados/malformadas, Origin y CSRF; integración ruta específica
Next→TLS FastAPI→PostgreSQL con servicio correcto/ausente/incorrecto/otro entorno,
TLS inválido y usuario activo/revocado/vencido/inactivo. Bearer válido sin sesión
o CSRF no busca. Probar concurrencia/aislamiento, error BD, 429/Retry-After y
requestId/no-store, sin reintentos. Mantener respuestas search del contrato y
pruebas existentes de recuperación sin modificar ML.

Término: A18 y controles comunes pasan sobre nuevo HEAD fijado, con canal común
demostrado en la ruta específica y backend, revisión de permisos/corpus y cero
excepción por tratarse de búsqueda. PR32 no se declara ejecutado por las pruebas
D.2 de PR30. No modificar ni fusionar su rama desde D.3.

## 5. Requisitos operativos que no se resuelven en un PR de código

| Responsable | Configuración / evidencia necesaria | Estado |
| --- | --- | --- |
| Next / Valentina | URL fija HTTPS, perfil explícito y credencial privada de entorno; nombre de variable de secreto C07 | IMPLEMENTATION_PENDING; sin valores reales aquí. |
| FastAPI / backend | AUTH_INTERMEDIARIO, APP_ENV, AUTH_ORIGENES_PERMITIDOS, HMAC, límites, bootstrap y capacidad por worker | Componentes existen; política productiva completa pendiente. |
| Búsqueda / América | SEARCH_PUBLIC_ORIGIN, SEARCH_SESSION_COOKIE_NAME, AUTH_COOKIE_PROFILE y base/perfil de búsqueda según contrato existente | Alinear configuración de los dos árboles, sin inventar variables. |
| Infraestructura | Red privada efectiva, CA/hostname/terminación TLS, custodia/rotación, pares y caminos alternativos | Render no acreditado. TLS público no demuestra salto privado. |
| Infraestructura + backend | Productor/saneamiento verificables de IP, IPv4/IPv6 y pruebas con clientes conocidos | Sin cabecera IP interna aprobada ni adaptador productivo. |
| PO/equipo | C01–C09: representaciones/códigos adicionales, cifras y operación pendientes | No reabrir P1–P10 ni sustituir medición por aprobación. |

Ver [matriz IP y secuencia de doce incrementos](auth07d3-compatibilidad-y-plan-integracion.md).
Se puede corregir transporte y probar TLS/SEC/PG localmente con rutas cerradas;
backend puede preparar P4 y composición interna antes de Render. Habilitar csrf
y login exige además IP/cuotas acreditadas; me/logout necesitan contrato/canal
completos y P4 en logout, sin requisito IP añadido por analogía. No se inicia la
siguiente tarea ni se envían mensajes a las autoras desde este documento.
