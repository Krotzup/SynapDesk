# Comunicación interna segura V1 — SEC-01B

**Mecanismo y responsabilidades APPROVED en AUTH-07D.3 (13-11-2026).**
Credencial opaca dedicada por entorno, solo servidor, SEC-01B en FastAPI, TLS
verificando CA/hostname, backend privado, rotación controlada, configuración
cerrada y separación de servicio/usuario/IP están aprobados expresamente.
La implementación existente se describe por separado de operación y evidencia.
No acredita Render, aprueba cifras de cuotas/tiempos ni habilita CSRF/rutas.
Conciliado con [autenticación](autenticacion-v1.md),
[frontend/backend](frontend-backend.md) y
[HTTP V1](autenticacion-http-adaptadores-v1.md). Detalles adicionales pendientes
C01–C09 en la [matriz D.3](auth07d3-compatibilidad-y-plan-integracion.md).

## 1. Alcance y arquitectura B

Navegador → ingreso público Render → Next.js público → FastAPI privado →
PostgreSQL/pgvector. Es la arquitectura objetivo autorizada por el encargo;
no representa recursos desplegados. No se contrató ni configuró producción.
La autenticidad del intermediario no sustituye usuario, sesión, rol, Origin,
CSRF ni cuotas. Los servicios internos existen; login, /me, logout y administración HTTP no están registrados.

### Relación con los contratos vigentes y decisiones A–G

AUTH-07D.3 formaliza el objetivo B en Render y TLS verificado para la
credencial de servicio, también localmente. La anterior referencia a Next.js
en Vercel y salto local HTTP queda sustituida para autenticación: no permite
bearer en claro. La política aprobada no certifica la topología real, la fuente
IP ni las condiciones operativas de Render. No se cambia frontend o backend
en esta formalización.

| Decisión | Contrato de esta implementación |
| --- | --- |
| A. Presentación | Next.js elimina Authorization del navegador y genera una única cabecera de servicio en servidor, conforme a la sección 3. |
| B. Identificación | FastAPI exige política habilitada del mismo APP_ENV, formato canónico, TLS directo y coincidencia con un digest vigente; compara todas las claves. |
| C. Metadatos internos | Authorization de servicio es exclusivamente servidor a servidor. No hay cabecera IP interna aceptada ni selector de credencial del cliente. Origin, cookies y X-CSRF-Token conservan sus autoridades independientes. |
| D. Identidades | IdentidadIntermediario acredita posesión de servicio; IpVerificada requiere procedencia acreditada; la sesión de usuario exige validación persistente separada. Ninguna sustituye otra. |
| E. Rechazo | Configuración ausente/deshabilitada, entorno distinto, vencimiento, credencial ausente/incorrecta/ambigua/malformada, canal inadecuado o procedencia insuficiente impiden continuar. |
| F. Estados | Fallos de canal/IP se traducen al 503 genérico existente con no-store; Origin inválido conserva 403. Los errores estructurales de configuración fallan al cargar, sin entradas sensibles. |
| G. Proxy #30 | Se preservan los filtros y contratos públicos; su transporte necesita incorporar bearer solo servidor y HTTPS verificado. Hasta entonces las operaciones protegidas rechazan y CSRF sigue cerrado. |

## 2. Frontera de confianza

Son pruebas independientes: identidad del servicio, protección del canal,
procedencia IP y sesión del usuario. Conocer un bearer solo acredita posesión
de una credencial admitida. No acredita la IP original ni integridad de un
intermediario comprometido. La red privada y loopback no autentican al emisor.

El backend confía en que su listener termina TLS directamente y no reescribe
scheme desde cabeceras. Debe utilizar Uvicorn con proxy_headers=False
(`--no-proxy-headers`), sin middleware que altere esa evidencia. Si una futura
topología termina TLS fuera del backend, requiere otra acreditación revisada;
no basta con X-Forwarded-Proto ni con configurar una red privada.

## 3. Presentación y verificación de servicio

Next.js descarta Authorization del navegador y construye en servidor exactamente
una cabecera `Authorization: Bearer <credencial>`. No reutiliza autorización de
usuario. La identidad de usuario sigue en su cookie de sesión. La credencial
no aparece en NEXT_PUBLIC_*, HTML, URL, JSON público, logs ni mensajes de error.

Credencial: exactamente 32 bytes generados por CSPRNG, codificados como base64url
canónico sin padding (43 caracteres). No se usan contraseñas humanas. La
validación de formato no prueba entropía: la generación y custodia son deber
operativo. No hay valor predeterminado ni secreto almacenado en el repositorio.

FastAPI recibe exclusivamente digests en configuración de servidor. El digest es
SHA-256 de `b"synapdesk:intermediario:v1\0" + entorno_ascii + b"\0" + secreto_bytes`.
Esto separa dominio y entorno de sesiones/HMAC. No es un hash de contraseña ni
anonimización de IP. El helper interno `digest_credencial_servicio` prepara el
digest sin imprimir el bearer. SecretStr oculta el digest en repr/JSON ordinario;
no autoriza registrar las entradas crudas de configuración.

La dependencia lee todas las ocurrencias originales de Authorization y rechaza
ausencia, duplicados incluso idénticos, listas, padding, Unicode y espacios
ambiguos. Compara los 32 bytes de todos los digests configurados con
`hmac.compare_digest`, también los vencidos. No promete tiempo constante de
toda la solicitud ni oculta el tamaño público del conjunto de rotación.

## 4. Configuración y rotación implementadas

Una variable opcional `AUTH_INTERMEDIARIO` contiene JSON de esta estructura
documental; los marcadores siguientes no son configuración ejecutable:

```text
habilitado: booleano estricto (ausente = false)
entorno: development | testing | staging | production
transporte: tls_directo
politica_ip: no_acreditada
credenciales: una o dos entradas
  identificador: 1..32 caracteres ASCII alfanuméricos, guion o guion bajo
  digest: 64 caracteres hexadecimales minúsculos, exclusivos de entorno/destino
  vence_en: instante con zona horaria, normalizado a UTC
```

Ausencia, deshabilitación, entorno distinto de APP_ENV o todas las claves
vencidas cierran las operaciones protegidas. Configuración estructural inválida
se rechaza al cargar Settings, sin incluir valores en el mensaje de validación;
puede impedir el arranque. Sin esta configuración, salud sigue operativa.
No se imprime ValidationError.errors() con valores de entrada.

Rotación: distribuir nuevo digest con vencimiento explícito, conservar como
máximo dos credenciales distintas, actualizar emisores y retirar la anterior.
El vencimiento se comprueba por petición (igualdad ya vencida). No hay plazo de
gracia predeterminado, selector de clave aportado por cliente ni recarga de
configuración entre procesos. Deben reiniciarse/actualizarse coordinadamente los
workers; mantener relojes sincronizados. El plazo y procedimiento operativo
requieren aprobación. Los secretos de cada entorno/destino deben ser distintos;
el backend no puede detectar una reutilización intencionada fuera de su entorno.

## 5. Transporte

Se exige TLS directo para enviar bearer, incluso localmente. Next.js deberá
verificar CA, hostname y destino fijo de BACKEND_INTERNAL_URL. No desactivar
validación de certificados, seguir redirecciones ni degradar a HTTP.
El backend exige scheme ASGI https y rechaza Forwarded, X-Real-IP y cualquier
X-Forwarded-*. No infiere TLS de esos campos. ASGI por sí solo no certifica la
configuración del servidor ni permite comprobar la validación TLS del cliente.

El bearer es reutilizable, sin firma de cuerpo, nonce ni protección antirreplay
de aplicación. TLS protege el tránsito; quien robe el secreto puede impersonar
al servicio. No se afirma mTLS ni identidad de plataforma. Estos riesgos se mantienen explícitos bajo el mecanismo aprobado; el procedimiento
operativo de revocación/retirada y las vigencias concretas requieren definición
y pruebas, sin prometer antirreplay o identidad de plataforma.

## 6. IP acreditada

La única política implementada es `no_acreditada`. No se aceptan como fuente IP
Authorization, Request.client, X-Forwarded-For, Forwarded, X-Real-IP,
X-SynapDesk-Client-IP, X-SynapDesk-IP-Source, UUID cliente ni loopback. No se
inventa una dirección ni se sustituye por una cuota global.

`obtener_ip_verificada` autentica primero al intermediario y después rechaza por
procedencia insuficiente. No construye IpVerificada desde HTTP. Las pruebas
internas reutilizan ServicioIpConfiable y ServicioIdentificadores con evidencia
controlada del fixture, fuera de cabeceras y configuración de la aplicación.
La aplicación normal no incluye adaptador local HTTP ni un interruptor de bypass para desarrollo.

**Actualización acotada MVP04:** existe una [composición local de ensayo](ingreso-local-mvp04.md)
fuera de la fábrica productiva, limitada a testing y base propia del arnés. El
ingreso Node observa el socket original y entrega evidencia firmada, ligada a
la petición y de un uso, además de SEC-01B/TLS. No habilita esta política en
producción ni acepta una IP arbitraria; las prohibiciones anteriores siguen
vigentes para la aplicación normal. Render conserva procedencia no acreditada.

Un futuro adaptador productivo requerirá evidencia del ingreso, identidad de servicio,
canal, peer real no reescrito y perfil autorizado, antes de construir IpVerificada.
El digest de IP sigue usando la clave HMAC de privacidad existente, diferente
de credenciales de servicio. IPv4/IPv6/mapeadas y NAT conservan AUTH-06.

## 7. Origin, CSRF, cookies y cuotas

Origin y la condición específica de bootstrap permanecen en AUTH-07B.1, antes
del control del canal. Un Origin inválido conserva 403 ORIGIN_INVALID. El servicio
autenticado no omite Origin, CSRF ni validación persistente de sesión/contexto.

GET /api/v1/auth/csrf sigue en 503 con bootstrap válido, incluso con servicio
autenticado. No abre transacciones, consume cuotas, emite tokens/contextos ni
altera cookies. El rechazo final permanece aunque un test sustituya el adaptador
de IP. No se conectó la emisión de SEC-01A.

Se conservan las cuotas persistentes independientes por IP/global/contexto de
SEC-01A, su límite de tokens y sus reservas confirmadas antes de la emisión.
No se cambian parámetros ni cuotas de login. No se activa el perfil de ensayo
en producción, no se expulsan tokens válidos ni se crean contextos de reemplazo.

P1/P2 formalizan rechazo de cookies malformadas/duplicadas/perfiles mezclados y
sin recuperación automática. Los atributos estrictos están en HTTP V1; nombres
C02 pendientes. El proxy no debe ocultar una cookie inválida antes del rechazo,
aunque conserve la lista permitida. Set-Cookie separados, Origin real,
X-CSRF-Token, no-store y P8 sin reintentos automáticos de escrituras. Las cifras
de timeout y cuotas siguen pendientes; no adoptar valores de ensayo en producción.

## 8. Errores implementados

Falta/fallo del canal y procedencia insuficiente usan el catálogo existente:
503 SERVICE_UNAVAILABLE, ApiErrorBody con code/message/details/requestId,
Cache-Control no-store, sin Retry-After inventado ni cookies nuevas.
No se revela clave fallida, IP, digest, certificado, SQL ni motivo interno.
El error interno de configuración de Origin conserva su comportamiento previo.
No se inventan nuevos códigos públicos ni se alteran contratos aprobados.

## 9. Responsabilidades Next.js y PR #30

El proxy actual elimina Authorization del cliente pero no genera el bearer de
servicio. Su HTTP local actual será rechazado por el backend protegido. Valentina
deberá añadir credencial solo servidor y TLS verificado al transporte común de
proxy/SSR, sin copiar cabeceras internas del navegador. La autenticación de canal
puede desarrollarse sin aprobar IP Render; no habilita bootstrap por sí sola.

La fuente IP local anterior de la PoC era el socket observado por un listener
Node directo; Route Handlers no aportan por sí mismos esa evidencia. Ese listener
no se incorpora aquí. Antes de un adaptador local hay que revisar todos los
caminos de entrada; no se considera localhost autenticación de servicio.

## 10. Responsabilidades FastAPI y PR #32

Las rutas futuras podrán usar IntermediarioHttp para autenticar servicio, junto
con sus propias dependencias de sesión/roles/Origin/CSRF. El control de servicio
no consulta PostgreSQL ni autentica usuarios. Las rutas de salud quedan públicas.

América deberá adaptar la ruta específica de búsqueda y su proxy servidor al
mismo canal; el PR #32 no se fusiona ni modifica aquí. El backend de búsqueda
necesitará además usuario/alcance autorizados, sin trasladar confianza a ML.
No basta añadir el bearer al proxy genérico si la búsqueda utiliza otro camino.

## 11. Pruebas de aceptación y límites locales

Unitarias: credenciales válidas/ausentes/incorrectas/malformadas/duplicadas,
rotación/vencimientos, entornos, configuración, comparaciones de todas las claves,
errores saneados, separación de IP/usuario, Origin/CSRF y concurrencia.

TLS real: Uvicorn en puerto efímero, certificado/clave generados y eliminados,
CA y hostname verificados; rechazo de CA/hostname incorrectos, HTTP directo,
loopback, X-Forwarded-Proto incluso con proxy_headers=True y duplicados crudos.
Los listeners de ensayo no se registran en la aplicación principal.

PostgreSQL real: bases temporales exclusivas en localhost:5433; D.2 verifica migración 0006,
rechazo sin efectos, servicio más IP del fixture, cuotas concurrentes y fallo
real de conexión. La suite previa conserva rollback/commit, constraints y locks.
La prueba controlada de IP no acredita la procedencia en Next.js ni Render.
El [arnés D.2 reproducible](../../backend/herramientas/arnes_http_seguro/README.md)
añade Node/Next reales y TLS CA/hostname;
el éxito de servicio en Next usa sustituto identificado porque PR30 aún no inyecta bearer.
Las pruebas locales no certifican navegador/build productivo o infraestructura.

## 12. Requisitos pendientes de Render y activación CSRF

Verificar posteriormente servicio privado, región/workspace y acceso entre
servicios, aislamiento de entornos, terminación TLS interna, CA/hostname y
rotación. El TLS del ingreso público no demuestra TLS del salto privado.
No se afirma ninguna de esas garantías por los ensayos locales.

IP Render: falta evidencia verificable del generador y saneamiento de metadatos,
todos los caminos públicos/internos, cabeceras falsas/duplicadas y múltiples
proxies. Mantener deshabilitado el adaptador hasta aprobar y probar la frontera.

Para emitir CSRF: aprobar procedencia, integrar proxy/TLS, configurar política
bootstrap explícita, conectar coordinador SEC-01A con commit antes de respuesta,
resolver nombres de cookies y clasificación de rechazo (P1/P2 ya aprobadas), admisión autenticada y saturación/esperas,
y superar pruebas de extremo a extremo. Esta tarea no realiza esos pasos.

## 13. Aprobación, decisiones y riesgos operativos pendientes

Mecanismo SEC-01B y arquitectura B aprobados expresamente en AUTH-07D.3.
El formato y las restricciones de esta implementación son la interfaz técnica
existente; no significan despliegue acreditado. Bearer reutilizable no prueba
IP original ni usuario, no firma cuerpo y no proporciona antirreplay de aplicación.

Pendientes C07/C08: variable privada Next (nombre todavía por acordar), custodia,
distribución, vigencias/retirada de rotación y reinicios, CA/hostname y
terminación efectiva, red privada/ACL/caminos alternativos y evidencia de fuente
IP Render. Credenciales nuevas por entorno/destino, sin valores reales en Git.
No sustituir esas pruebas por diagramas, red privada o cabeceras arbitrarias.
Cuotas/cifras/esperas y representaciones adicionales conservan sus decisiones
C01–C06/C09; no se reabren P1–P10 o las políticas administrativas.

La [matriz IP](auth07d3-compatibilidad-y-plan-integracion.md#6-matriz-de-acreditación-ip)
y las [especificaciones PR30/PR32](integracion-http-pr30-pr32-v1.md) definen
responsables, aceptación y límites sin modificar los PR ni iniciar integración.
