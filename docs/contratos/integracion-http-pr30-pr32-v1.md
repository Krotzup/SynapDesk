# Integración HTTP entre Next.js y FastAPI — AUTH-07D.1

**Estado: DRAFT / pendiente de conciliación y aprobación para habilitar tráfico.**
Este documento prepara la colaboración; no cambia contratos aprobados, registra
rutas ni acredita infraestructura Render. Complementa el
[contrato candidato de autenticación](autenticacion-http-adaptadores-v1.md), el
[contrato general](frontend-backend.md) y
[SEC-01B](comunicacion-interna-segura-v1.md).

## Fuentes inspeccionadas

Referencias remotas consultadas mediante `git ls-remote origin` y objetos Git
leídos sin cambiar de rama ni modificar las implementaciones de sus autoras:

| PR | HEAD revisado | Transporte relevante |
| --- | --- | --- |
| #30, Valentina | `0f0105e5a14ec095f538bf1079a6439b3ccf9d40` | `frontend/src/lib/backend-proxy.ts`, Route Handler comodín `/api/v1/[...path]`, transportes SSR y cliente |
| #32, América | `ac9f02516becb8f1c4a02c149131835b8e8a6b2e` | `frontend/src/lib/server/search-proxy.ts`, ruta específica `/api/v1/search`, autorización persistente en `backend/app/recuperacion/acceso.py` |

Los nombres anteriores corresponden a esos árboles de PR, no a funcionalidad
integrada en esta rama. No se revisó ni modificó el trabajo ML de #32.

## Responsabilidades y separación de identidades

Navegador → Next.js público → FastAPI privado → PostgreSQL es el objetivo B.
La sesión acredita al usuario mediante PostgreSQL; el bearer SEC-01B acredita al
intermediario; la IP requiere evidencia independiente. Ninguno sustituye a otro.

Next.js debe seleccionar un destino fijo del servidor, conservar el método y la
ruta permitidos, transmitir únicamente cabeceras/cookies autorizadas e inyectar
su propia credencial desde configuración privada del servidor. El navegador no
elige destino, credencial, usuario ni rol.

FastAPI valida SEC-01B en el canal TLS conforme al contrato, Origin/CSRF según la
operación, sesión vigente, estado de cuenta y las cuotas persistentes existentes.
Genera el `requestId` de backend, sanea errores y confirma transacciones antes de
construir cookies de éxito. La configuración de FastAPI no acepta un bearer del
intermediario como autorización de usuario.

## Acuerdo propuesto para Valentina — PR #30

| Aspecto | Comportamiento observado | Cambio o comprobación requerida |
| --- | --- | --- |
| Destino | URL interna fija y conservación de `/api/v1` | Mantener lista cerrada de destinos y TLS con CA y hostname verificados. El perfil HTTP local no puede transportar SEC-01B en claro, ni siquiera en desarrollo. |
| Credencial | El proxy descarta Authorization del navegador; no inyecta bearer propio | Incorporar la credencial exclusivamente del servidor tanto en Route Handler como en SSR. No publicarla mediante `NEXT_PUBLIC_*`, HTML, errores, bundles o logs. Rotación/expiración conforme a SEC-01B. |
| Cabeceras | Lista permitida para Accept, Content-Type, Origin, Sec-Fetch-Site y X-CSRF-Token | Conservar la lista cerrada. Descartar credenciales y cabeceras IP aportadas por navegador; no reenviar Forwarded, X-Real-IP ni X-Forwarded-*. No añadir un supuesto origen IP aún sin acreditar. |
| Cookies | Lista por perfil local/production; Set-Cookie filtrado | Conciliar nombres explícitos con FastAPI. Mantener Set-Cookie separados, incluidas eliminaciones, sin concatenarlos. Rechazar configuración incompleta antes de atender tráfico. |
| SSR | Cookies aisladas por petición; acceso directo al backend | Usar la misma política SEC-01B/TLS y perfil que el proxy público. `/me` admite lectura SSR sin Origin según contrato; no fabricar un Origin para eludir el rechazo de mutaciones. No compartir cookies entre usuarios. |
| Origin/CSRF | Reenvío de cabeceras permitido | Conservar el Origin real permitido y X-CSRF-Token único. No crear un token, omitirlo ni reintentar automáticamente efectos ante fallos. |
| Cache y redirecciones | No-store y rechazo de redirecciones | Mantenerlos en respuestas de éxito y error. No seguir una redirección con bearer o cookies. |
| Timeout | Plazo de 30 s incluye lectura de cuerpo | Conciliar presupuesto con Argon2/DB y cancelación. Un timeout tras commit es resultado incierto; nunca repetir automáticamente login/logout. |
| requestId | Proxy genera identificador en sus errores | Preservar el requestId generado por FastAPI cuando existe respuesta. Los errores propios de Next llevan su identificador sin afirmar que hubo auditoría backend. No confiar en un identificador arbitrario del navegador. |
| Admisión | Proxy genérico lee el cuerpo completo | Fijar límites y presupuesto de admisión antes de habilitar login. No introducir unilateralmente códigos públicos nuevos para estos límites. |

El transporte puede prepararse y revisarse con las rutas de auth aún cerradas.
Antes de habilitarlas se requiere el acuerdo de contrato, pruebas de ambos
transportes y resolver la dependencia IP. No se exige aceptar una cabecera de
Render todavía no acreditada.

## Acuerdo propuesto para América — PR #32

La ruta específica `/api/v1/search` precede al comodín de #30; integrar #30 no
cambia automáticamente el transporte de búsqueda. Hay dos canales que deben
compartir las mismas garantías.

El proxy de búsqueda ya comprueba Origin, una cookie de sesión, token CSRF no
vacío/ambiguo, JSON de búsqueda, tamaño de cuerpo, timeout, redirecciones y
no-store. Su backend consulta sesión persistente y valida CSRF dentro de la
transacción de búsqueda. Estos controles deben conservarse.

Acciones concretas antes de activar el canal común:

1. Compartir la construcción segura del transporte con #30 o demostrar mediante
   pruebas equivalencia en ambos caminos. Inyectar SEC-01B en Next y validarlo en
   FastAPI también para búsqueda; mantener aparte sesión, rol y CSRF del usuario.
2. Conciliar `SEARCH_SESSION_COOKIE_NAME`, `AUTH_COOKIE_PROFILE` y la configuración
   de cookie del backend de búsqueda. Usar el mismo perfil de sesión explícito,
   sin asumir que el nombre actualmente propuesto está aprobado.
3. Mantener `SEARCH_PUBLIC_ORIGIN` coherente con los orígenes permitidos del
   backend y conciliar precedencia de rechazos: el acceso de búsqueda inspecciona
   cookie antes de Origin, mientras las mutaciones auth requieren Origin primero.
   No aprobar unilateralmente un cambio de precedencia observable.
4. Conservar el POST de búsqueda con CSRF vinculado a la sesión. No sustituirlo
   por bearer de servicio ni por contexto anónimo. Mantener su contrato de
   respuesta y saneamiento de errores específicos de búsqueda y conciliarlo con
   el sobre general, requestId y Retry-After.
5. El proxy reconstruye la respuesta y no reenvía Set-Cookie. Esto no debe usarse
   para transportar login/logout sin una política explícita; búsqueda no debe
   renovar o recuperar sesiones automáticamente. El canal auth requiere su
   propio tratamiento comprobado de Set-Cookie.
6. `BACKEND_ALLOW_HTTP_LOCAL` no autoriza enviar SEC-01B en claro. Aplicar TLS
   verificado en cualquier entorno donde se presente la credencial.
7. No añadir IP acreditada a partir de cabeceras recibidas del navegador. Si una
   cuota exige IP, mantener ese camino cerrado hasta resolver su procedencia.

No se solicitan cambios ML ni modificaciones de los resultados de búsqueda en
AUTH-07D.1. Estas observaciones se entregan para revisión; no se enviaron mensajes
ni se modificó la rama de América.

## Configuración a conciliar

| Propietario | Configuración existente / decisión | Requisito |
| --- | --- | --- |
| Next #30/#32 | `BACKEND_INTERNAL_URL` | Servidor privado fijo con HTTPS y verificación de certificado/hostname; sin destino derivado del cliente. |
| Next | `AUTH_COOKIE_PROFILE` | Perfil explícito alineado con FastAPI; evitar depender de un default local en producción. |
| Next #32 | `SEARCH_PUBLIC_ORIGIN`, `SEARCH_SESSION_COOKIE_NAME`, `BACKEND_ALLOW_HTTP_LOCAL` | Alinear Origin/cookie; ninguna opción local desactiva TLS con bearer. |
| Next | Variable privada para la credencial SEC-01B, nombre por acordar | No existe aún inyección en los HEAD revisados. No declarar una variable nueva operativa ni distribuir su valor en documentación. |
| FastAPI | `AUTH_INTERMEDIARIO` y `APP_ENV` | Configuración cerrada SEC-01B, digests/identificadores/vigencias y requisitos TLS; no guardar el bearer en texto plano en repositorio. |
| FastAPI | `AUTH_ORIGENES_PERMITIDOS` | Lista exacta compatible con el Origin público real y los perfiles de cookies. |
| FastAPI | Configuración existente HMAC, contraseñas, bootstrap y límites | Completa antes de preparar el worker; secretos privados, capacidad Argon2 por worker y PostgreSQL disponible. No introducir nombres alternativos o defaults permisivos. |
| Infraestructura | Certificados/CA, red y terminación TLS | Definir provisión y verificación por separado. No desactivar validación ni presentar HTTP detrás de terminación TLS como evidencia suficiente para SEC-01B actual. |

Cabeceras internas actuales admisibles: Authorization generado por Next para
SEC-01B y las cabeceras de la lista permitida del contrato. Cookies y tokens son
secretos por petición. No existe todavía una cabecera IP interna aprobada.

## Evidencia necesaria de Render

Documentar con pruebas reproducibles el camino completo del navegador al backend:

- Qué componente observa la IP original y qué dato produce, en qué salto y con
  qué garantía de integridad. La IP del socket de FastAPI puede ser la de Next.
- Cómo el ingreso público elimina o sobrescribe valores aportados por el
  navegador, incluidos duplicados, listas y variantes de nombres de cabeceras.
- Qué pares y rutas pueden alcanzar cada servicio y cómo se autentican. Probar
  intentos directos a FastAPI y entradas alternativas que eviten el ingreso.
- Dónde termina TLS, certificado/hostname/CA observados desde Next y si el canal
  efectivo cumple SEC-01B. Registrar configuración de proxy de ASGI; no habilitar
  `proxy_headers` sin una cadena de confianza verificable.
- Demostrar extremo a extremo, con clientes de IP conocida y solicitudes
  falsificadas, la extracción y normalización inequívocas de la IP, y el rechazo
  cuando falta o es ambigua. Un diagrama, un bearer válido o una prueba mock no
  acreditan esta propiedad.

Hasta contar con esa evidencia y contrato, `obtener_ip_verificada` sigue cerrado.
No se añade aquí un adaptador Render supuesto ni una excepción de entorno.

## Pruebas mínimas y orden de integración

1. Product Owner/equipo concilian el borrador de endpoints, perfiles de cookies,
   recuperación de cookie inválida, clasificación de cookie ambigua/logout
   inactivo, admisión de CSRF autenticado y los códigos/estados pendientes.
2. Con Valentina, preparar transporte común y SSR con TLS real, secreto de
   servicio privado, filtros, requestId, no-store, timeout y Set-Cookie separados.
   Se puede probar localmente contra un arnés aislado sin registrar rutas reales.
3. Con América, aplicar/verificar el mismo canal en la ruta específica de
   búsqueda y su backend, conservando autorización persistente y CSRF propios.
4. Pruebas Node.js → FastAPI → PostgreSQL: bearer válido/ausente/incorrecto,
   certificado no confiable/hostname incorrecto, redirecciones, Origin ausente o
   inválido, cookies múltiples/entre perfiles, CSRF duplicado/ajeno/vencido,
   DTO/errores generales, sesión activa/revocada, cuotas y commit fallido sin
   Set-Cookie de éxito. Simular pérdida de acuse sin reintento automático.
5. Pruebas de navegador en entorno de ensayo aprobado: HttpOnly/Secure/SameSite/
   Path/Domain, prefijos __Host-, expiración/eliminación, bootstrap inicial,
   sustitución de sesión, logout, aislamiento SSR entre usuarios, cachés y
   ausencia de secretos en JavaScript/HTML/logs. Esto exige habilitación explícita
   en otra tarea y no está acreditado por los tests actuales.
6. Validar el ingreso y TLS/IP en Render con la evidencia anterior. Solo entonces
   decidir el adaptador productivo de IP, sus pruebas negativas y el registro
   posterior de cada endpoint completo.

En esta rama se validan Python, PostgreSQL y las regresiones TLS existentes.
No se han ejecutado las pruebas Node/navegador ni desplegado Render. El arnés de
pruebas usa evidencia IP controlada exclusivamente en tests; no ofrece un modo de
producción alternativo. AUTH-07D.2 y la administración HTTP no se inician aquí.
