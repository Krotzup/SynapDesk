# Fundamentos HTTP de autenticación — AUTH-07A

Esta fase prepara utilidades, sin registrar rutas de autenticación, emitir cookies desde endpoints ni crear seeds. Reutiliza [AUTH-06](../seguridad/README.md), sus modelos y sus transacciones. Salud y disponibilidad conservan su comportamiento.

## Esquemas y errores

[esquemas_auth.py](esquemas_auth.py) define AuthUser exclusivamente con `id`, `email` y `role`, su envoltura `user`, solicitud de login, respuesta CSRF propuesta y la envoltura de errores. `ApiErrorBody` corresponde al objeto dentro de `error`, igual que el tipo frontend. Solo se admiten detalles de validación saneados o null en los errores construidos aquí. Los DTO no serializan modelos ORM.

El correo de login comparte la normalización de Usuario y una comprobación sintáctica mínima (un separador @, partes no vacías y ausencia de espacios internos); no introduce reglas de proveedores ni certifica validación internacional completa. La política definitiva de direcciones especiales y límites de entrada requiere coordinación antes de AUTH-07B. La contraseña debe ser texto no vacío UTF-8 y se conserva intacta como SecretStr, sin restricciones nuevas de longitud. El token CSRF permanece oculto en repr; su serialización JSON expone exclusivamente la prueba prevista para el cliente. No registrar ese JSON.

[errores_auth.py](errores_auth.py) registra manejadores en la fábrica existente. Traduce sesión ausente/vencida/revocada a `401 AUTHENTICATION_REQUIRED` en consultas de identidad, Origin a `403 ORIGIN_INVALID`, y persistencia/conflictos o IP no verificable a `503 SERVICE_UNAVAILABLE`. No proporciona aún la política de credenciales de login. Argon2 y configuración inválida son errores internos `500 INTERNAL_ERROR`, nunca `INVALID_CREDENTIALS`. `LIMITE_TOKENS` tampoco se convierte automáticamente en 429 sin una política/espera verificable.

CSRF inválido/vencido/contexto inválido solo produce `403 CSRF_INVALID` mediante `RechazoAntesDeEfectos`: el adaptador debe acreditar que no comenzó la mutación. Un error CSRF sin esa garantía produce error interno, sin habilitar el reintento contractual. No envolver fallos posteriores a efectos ni resultados desconocidos. La futura orquestación debe preservar esta distinción.

La validación FastAPI devuelve `422 VALIDATION_ERROR`, los cuatro campos contractuales y una lista de `{field, message}`. Solo se seleccionan nombres declarados en el esquema/ruta, con mensajes fijos en español; nunca input, contexto, mensajes de validadores, índices arbitrarios ni nombres extra del cliente. JSON inválido usa la misma envoltura con lista vacía. **Discrepancia documental:** el contrato general acordó este código el 03-11-2026, mientras la tabla de autenticación aún marca su catálogo de validación pendiente. Se aplica el acuerdo general más reciente; no se modifican contratos.

[respuestas_auth.py](respuestas_auth.py) genera UUID por petición en servidor, sin adoptar X-Request-ID. Las respuestas preparadas aquí llevan `Cache-Control: no-store`; no se agrega caché ni cookies a salud/disponibilidad. `respuesta_limite` exige una decisión negativa con tiempos conscientes de zona y espera positiva calculada por AUTH-06; nunca fabrica Retry-After.

## Cookies: perfiles propuestos, explícitos

[cookies_auth.py](cookies_auth.py) exige entorno, origen público y nombres distintos de sesión/contexto. No hay nombres ni duraciones por defecto. Usar `preparar_perfil` con la configuración para exigir pertenencia al Origin permitido. Ejemplos **PROPOSED** del contrato: `__Host-synapdesk_session` y `__Host-synapdesk_csrf_context` para HTTPS; `synapdesk_session_dev` y `synapdesk_csrf_context_dev` para HTTP local. No quedan aprobados definitivamente por estas utilidades.

Los perfiles usan HttpOnly, SameSite=Lax, Path=/ y ausencia de Domain. Todo origen HTTPS implica Secure, también en desarrollo. HTTP solo se admite en development/testing para hosts locales explícitos; staging/production exigen HTTPS. El nombre __Host-/__Secure- no puede usarse con HTTP. La emisión recibe credencial canónica de AUTH-06 y vencimiento confirmado, calcula Max-Age como el tiempo restante redondeado hacia abajo, sin fijar nuevas duraciones. El borrado conserva ámbito y atributos con Max-Age=0.

La lectura inspecciona todas las cabeceras Cookie originales, rechaza duplicados incluso idénticos y representaciones ambiguas. Nunca elige silenciosamente el primer/último valor de Request.cookies. La respuesta tampoco puede emitir/borrar dos veces el mismo nombre; diferentes Set-Cookie permanecen separados. `CookieAmbigua` no tiene todavía un código público específico aprobado: falla cerrada como error saneado y su clasificación queda para AUTH-07B.

## Transacciones e infraestructura

[dependencias_auth.py](dependencias_auth.py) obtiene una Session SQLAlchemy por petición desde el motor del ciclo de vida existente. `SesionHttp` usa `scope="function"` para cerrar y revertir trabajo pendiente antes de enviar la respuesta. Nunca hace commit automático. No compartir sesiones entre peticiones, tareas o streaming.

La futura operación debe abrir explícitamente [transaccion_seguridad](../seguridad/transacciones.py), componer efectos y auditoría dentro de ella, y construir credenciales/cookies de éxito **después** de salir correctamente del bloque. El commit puede fallar; no capturar el fallo para reutilizar resultados provisionales. Las pruebas PostgreSQL demuestran commit visible desde otra conexión antes de emitir cookie, rollback, fallo real de una restricción diferida al commit y sesiones/conexiones concurrentes distintas.

## Origin y frontera de confianza

El adaptador `exigir_origin` pasa todas las ocurrencias originales al servicio AUTH-06. No combina Origin ni lo infiere de Host, Referer o forwarded headers. El ejemplo local sigue siendo `AUTH_ORIGENES_PERMITIDOS=["http://localhost:3000"]`. No modifica CORS ni las reglas de lecturas/bootstrap, que se conectarán en AUTH-07B.

`obtener_token_csrf` solo exige una cabecera X-CSRF-Token canónica y única, sin acreditar contexto o vigencia: el futuro endpoint debe llamar al servicio CSRF con la vinculación correcta. No sustituye su validación persistente.

**IP HTTP pendiente:** `obtener_ip_verificada` rechaza siempre mientras no exista un adaptador autenticado o aislado aprobado. No acepta X-Forwarded-For, X-Real-IP, Forwarded ni X-SynapDesk-Client-IP; tampoco confía en loopback o Request.client. AUTH-06 conserva su primitiva independiente, sin activar un bypass. La ausencia de procedencia verificable no autoriza omitir la cuota IP.

El comando local documentado utiliza `uvicorn ... --no-proxy-headers`: Uvicorn no debe reescribir el peer desde cabeceras del cliente. Esa opción no autentica Next.js ni resuelve despliegues de varios saltos; la app nunca considera confiable automáticamente el peer aunque el servidor se inicie con otras opciones. Se deben aprobar redes, aislamiento/autenticidad y metadatos reconstruidos antes de habilitar IP en AUTH-07B.

Siguen pendientes recuperación ante cookie vencida, actividad exacta de sesión, perfil operativo definitivo de cookies, cuotas/bootstrap, saturación CSRF, calibración y políticas administrativas. No se implementan AUTH-07B/C, proxy Next.js, SSR ni cambios de roles o migraciones.
