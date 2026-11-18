# Reproducir el CRUD local sobre main — MVP09

Alcance: navegador real → Next.js → HTTPS/SEC-01B → FastAPI → PostgreSQL.
Base del candidato: 5a73f024d6a3ef2476120b18042592cc017bb539, con #38, #30,
#32, #39 y #50 integrados. Solo testing aislado. No acredita Render ni habilita rutas en la
aplicación habitual. La [reconciliación](integracion/mvp09-reconciliacion.md)
explica la selección de los 44 archivos originales.
La [preparación de publicación](integracion/mvp09-publicacion.md) distingue
los resultados actuales de los históricos y documenta los solapamientos abiertos.

## 1. Preparar herramientas y variables privadas

Usar Python 3.12 y las [dependencias backend](../backend/requirements-dev.txt),
Node compatible con el [package.json](../frontend/package.json), dependencias del
lockfile frontend, OpenSSL y Microsoft Edge instalado. El driver usa
playwright-core 1.58.2 como herramienta de pruebas, no como dependencia productiva.
No se instala software al ejecutar el arnés. La instalación manual de dependencias
en una copia nueva debe realizarla el operador por el procedimiento del proyecto:

```powershell
# Desde backend, una vez creado y elegido su entorno virtual:
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
# Desde frontend:
npm ci
```

Si playwright-core no existe, preparar por separado una carpeta de herramientas
de prueba autorizada y fijar esa versión; no descargar otro navegador:

```powershell
npm install --prefix RUTA_HERRAMIENTAS_PRIVADA --no-save --ignore-scripts --package-lock=false playwright-core@1.58.2
```

El ejecutable predeterminado es la instalación Windows de Edge bajo Program
Files (x86). Si ya está instalado en otra ruta, definir EDGE_EXECUTABLE_PATH con
esa ruta; no apuntarlo a Chromium ni instalar un navegador desde el runner.

Variables BD requeridas en el entorno del proceso o en el archivo privado raíz:
POSTGRES_TEST_HOST (loopback), POSTGRES_TEST_PORT (5433), POSTGRES_TEST_DB,
POSTGRES_TEST_USER y POSTGRES_TEST_PASSWORD. La base de control de testing debe
existir y el operador debe poder crear/eliminar sus bases temporales. Mantener
POSTGRES_DB distinto de POSTGRES_TEST_DB, sin conectarse a desarrollo.
No poner contraseñas en argumentos, URL, Markdown, logs ni commits. El runner
acepta `--env-file RUTA_PRIVADA` para cargarlo en memoria sin copiarlo.

El arnés genera sólo para sus procesos: APP_ENV=testing, AUTH_BOOTSTRAP de ensayo,
AUTH_HMAC_CLAVE/ID, cuotas existentes de testing, AUTH_INTERMEDIARIO, claves de
evidencia/audiencia, AUTH_ORIGENES_PERMITIDOS y AUTH_PROXIES_AUTORIZADOS. No son
defaults productivos. Next recibe NEXT_PUBLIC_USE_MOCKS=false,
NEXT_PUBLIC_TRUSTED_LOCAL_INGRESS=true, AUTH_COOKIE_PROFILE=local,
BACKEND_INTERNAL_URL HTTPS, BACKEND_SERVICE_CREDENTIAL y NODE_EXTRA_CA_CERTS.
El flag público por sí solo no habilita el puente privado; sin él el BFF cierra.
Nunca usar NODE_TLS_REJECT_UNAUTHORIZED=0 o verify=False.

## 2. PostgreSQL de pruebas

Se necesita una instancia PostgreSQL de testing saludable en loopback:5433.
El runner no inicia, reinicia, configura ni detiene contenedores. No ejecutar
compose down, prune, limpieza de volúmenes ni iniciar el servicio db.
La imagen del [servicio testing](../compose.yaml) está fijada a
pgvector/pgvector:0.8.6-pg17-bookworm. La instancia testing
no contiene datos operativos. El arnés crea otra base exclusiva por ejecución
con nombre synapdesk_auth07_sec01a_ más un UUID aleatorio; nunca usa la base de
control para las operaciones de negocio.

## 3. Alembic y procesos seguros

Desde backend, con el intérprete del entorno elegido:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.verificar --modo todo --env-file RUTA_PRIVADA --playwright-module RUTA_PLAYWRIGHT_CORE
```

El runner ejecuta en su base nueva: Alembic `upgrade head`, `current`, `heads` y
`check` con `-x base=testing`; exige 0006_user_created y PostgreSQL 17/pgvector
0.8.6. Después ejecuta las 91 pruebas de tickets y rutas locales PostgreSQL.
El runner general `python -m herramientas.ci_backend postgresql` conserva las
demás regresiones de infraestructura, autenticación y sesiones (requiere las
variables de testing en el proceso). Para repetir sólo el
navegador usar `--modo navegador`; para sólo PostgreSQL, `--modo postgresql`.

No levantar app.main como sustituto: su cierre productivo es deliberado. El
runner compone [FastAPI local](../backend/herramientas/ingreso_local/aplicacion.py)
y lo sirve con Uvicorn TLS directo, CA/hostname localhost y proxy_headers=False.
Luego inicia el [servidor Next](../backend/herramientas/ingreso_local/servidor_next.mjs)
en un puerto loopback libre; observa el socket original y sella la petición.
No hay secretos permanentes ni cambios de confianza global. Next puede necesitar
acceso a Google Fonts; no cambiar TLS para eludir un error de red.

## 4. Cuentas: ensayo frente a bootstrap autorizado

La demo acreditada crea cuentas efímeras admin/agent con Argon2id **únicamente en
su base testing**, y ninguna sesión previa a login. Es una fixture documentada,
no bootstrap operativo verificado. No afirmar que estas cuentas provienen del
CLI ni reutilizarlas fuera del ensayo.

Para cuentas obtenidas mediante bootstrap autorizado se debe usar el
[CLI existente](../backend/herramientas/bootstrap_admin.py), no un seed SQL:

```powershell
# Sólo después de configurar y acreditar el destino testing real:
./.venv/Scripts/python.exe herramientas/bootstrap_admin.py --base testing
```

Ese CLI exige terminal protegido, propietario/identidad SQL, clúster esperado,
esquema 0006, POSTGRES_SSLMODE=verify-full y CA/hostname válidos. Solicita por
getpass contraseña/confirmación y exige confirmar el destino exacto; crea el
primer admin y su auditoría atómicamente. `--ensayar` hace rollback y **no crea
una cuenta**. Sin PostgreSQL TLS acreditado permanece cerrado: no se añade una
excepción local. Crear agent requiere después una sesión admin vigente y el
[servicio administrativo existente](../backend/app/seguridad/creacion_usuarios.py),
con captura/entrega privada autorizadas; no existe formulario administrativo en
este incremento. La provisión operativa queda pendiente de revisión del equipo,
sin bloquear la reproducción testing ni habilitar nuevas rutas.

## 5. Recorrido y evidencia

El driver arranca el ejecutable instalado de Edge (channel msedge, headless),
sin interceptar respuestas ni usar sesiones prefabricadas. Lee credenciales
efímeras de un archivo privado temporal y completa para cada rol:

1. CSRF → login → /me.
2. Formulario /tickets/nuevo → POST 201 → UUID comprobado en SQL.
3. Listado real → siguiente/anterior → abrir el ticket → detalle concordante.
4. Selector/botón de estado → PATCH 200 → SQL independiente.
5. Recarga real → estado conservado en interfaz y SQL.
6. Página 10^80 con tamaño 100: HTTP 200, items vacío y totales correctos.
7. Rechazos de anónimo, revocación, inactividad, Origin/CSRF, NBSP y estado inválido.
8. Consulta con filtros pendientes: aviso explícito, sin fingir resultados filtrados.

El supervisor comprueba además el rechazo de SEC-01B inválido mediante HTTPS
real con la CA del ensayo. Las pruebas de unidad verifican firma, audiencia,
binding, replay y agotamiento conservador; no se confunden con acciones de Edge.
Las lecturas SSR se delegan sólo desde navegación GET admitida hacia recursos
de lectura permitidos, conservando socket y credenciales originales. Un flag
público no instala esa capacidad ni permite emitir sellos.

Para una demo manual desde backend, elegir un reporte nuevo dentro de artifacts:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.demo --frontend ../frontend --reporte ../artifacts/demo-manual.json
```

Crear primero la carpeta artifacts si no existe. El runner imprime la URL y
ruta del archivo privado; consultarlo localmente, sin pegar credenciales al chat
ni registrar contenido. Al terminar pulsar Enter para cerrar recursos propios.
La ruta /tickets/nuevo se puede abrir desde la barra del navegador; no se añade
otro flujo de producto durante la consolidación.

Los reportes, capturas y credenciales no se versionan. Al cerrar se eliminan sólo
los recursos de esa ejecución; se conserva la evidencia saneada. La persistencia
acreditada abarca navegación, conexiones y recargas durante el ensayo; la base
se elimina intencionalmente al cerrar. No se afirma durabilidad de una demo ya
eliminada ni persistencia productiva entre despliegues.
