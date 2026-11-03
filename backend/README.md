# Backend

API de SynapDesk basada en FastAPI y Pydantic, con prefijo `/api/v1`.

## Estado actual

- Aplicación ejecutable con Uvicorn.
- Endpoint `GET /api/v1/health` para comprobar que la API responde.
- Documentación OpenAPI en `/docs` y esquema en `/openapi.json`.
- Configuración mediante variables de entorno y el `.env` de la raíz.
- CORS con orígenes explícitos para el frontend local.
- Conexión a PostgreSQL con SQLAlchemy y Psycopg 3.
- Endpoint `GET /api/v1/ready` para comprobar acceso a PostgreSQL.
- Entorno Alembic preparado para versionar cambios de estructura.
- Modelos de usuarios y tickets y revisiones `0001_usuarios_tickets` y `0002_autenticacion_persistencia`.
- Persistencia V1 de sesiones opacas, contextos/tokens CSRF, límites de autenticación y eventos de auditoría; no agrega endpoints.
- Pruebas unitarias de salud, CORS, configuración y disponibilidad.
- Pruebas de integración optativas de conexión, persistencia y migraciones contra `db_test`.

Las tablas de usuarios, tickets y persistencia de autenticación se crean al aplicar las migraciones. Sus endpoints, autenticación efectiva e integración ML siguen pendientes. Los secretos de sesión, contextos y CSRF no se almacenan en texto plano: las tablas guardan únicamente digests de 32 bytes. La migración no fija cuotas de rate limiting, retención de auditoría ni la política de emisión/rotación de tokens.

La sesión conserva creación, última actividad, expiración absoluta y revocación; el modelo permite aplicar posteriormente los límites aprobados de ocho horas y treinta minutos. Los contextos anónimos y autenticados son identidades separadas, y un contexto admite varios tokens CSRF vigentes. Los registros de límites usan claves seudonimizadas, ventana, contadores, reservas y bloqueo; el ORM incorpora versionado optimista para evitar pérdidas silenciosas en actualizaciones concurrentes. La auditoría conserva solo referencias y contexto mínimo seguro, sin contraseñas, cookies, tokens, secretos ni cabeceras completas.

Para identificadores de cuenta normalizada e IP verificada, los campos `clave_digest` e `ip_verificada_digest` deben recibir **HMAC-SHA-256 con una clave secreta exclusiva del servidor**, nunca SHA-256 simple de correo/IP. Son datos seudonimizados, no anónimos: SHA-256 sin clave permite comprobar candidatos de baja entropía. Los secretos aleatorios de sesión, contexto anónimo y token CSRF conservan SHA-256. Ambos resultados ocupan 32 bytes y son compatibles con el esquema. Los fundamentos siguientes implementan normalización y derivación HMAC; la obtención confiable de IP, gestión/rotación operativa de claves y orquestación HTTP de sesiones siguen pendientes. Las claves públicas ficticias de pruebas nunca son válidas para producción.

Los [servicios internos de seguridad](app/seguridad/README.md) reutilizan las tablas existentes, con transacciones del llamador, reloj PostgreSQL y bloqueos por fila. Incluyen sesiones, CSRF, Origin estricto, una primitiva de IP desde proxy autorizado, reservas persistentes por cuenta/IP y auditoría mínima. No agregan endpoints, cookies ni middleware; la conexión de solicitudes corresponde a AUTH-07. La configuración de Origin, la frontera de confianza Next.js/FastAPI, los parámetros provisionales de cuotas y los límites transaccionales se describen en esa guía. Las pruebas de concurrencia necesitan PostgreSQL real de pruebas en 5433 y una base temporal exclusiva; no utilizar desarrollo en 5432 ni ejecutar las pruebas de commit sobre una base compartida.

## Fundamentos de seguridad

[ServicioContrasenas](app/seguridad/contrasenas.py) utiliza `argon2-cffi==25.1.0` y Argon2id con sal aleatoria individual de 16 bytes y hash de 32 bytes. Genera hashes codificados, verifica y detecta necesidad de rehash; no consulta usuarios, cambia contraseñas ni inicia sesión. La contraseña no se recorta ni normaliza. Una verificación correcta devuelve true; `VerifyMismatchError` devuelve false. Un hash almacenado malformado/incompatible o `InvalidHashError` produce [ErrorContrasena](app/seguridad/contrasenas.py), al igual que un `VerificationError` interno (por ejemplo, fallo de asignación de memoria), con mensajes saneados distintos y sin detalles de Argon2. Estos errores no son credenciales incorrectas ni deben convertirse en ellas por el llamador; no se implementa su traducción HTTP aquí. `necesita_rehash` conserva su comportamiento y debe consultarse solo tras una verificación correcta. Solo se aceptan hashes del almacenamiento confiable, nunca hashes enviados por un cliente: sus parámetros controlan trabajo criptográfico. Los errores propios están saneados y el servicio no escribe logs.

Se reutiliza [Configuracion](app/configuracion.py), su carga de variables y su validación inicial:

| Variable | Valor inicial / requisito | Estado |
| --- | --- | --- |
| `AUTH_ARGON2_MEMORIA_KIB` | `65536` (64 MiB); al menos ocho veces el paralelismo | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| `AUTH_ARGON2_ITERACIONES` | `3`, entero positivo | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| `AUTH_ARGON2_PARALELISMO` | `1`, entero positivo | PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT |
| `AUTH_HMAC_CLAVE` | Base64 estándar canónico de al menos 32 bytes generados mediante CSPRNG; sin valor por defecto | Secreto obligatorio al construir el servicio HMAC |
| `AUTH_HMAC_ID_CLAVE` | Identificador no secreto de 1–32 letras ASCII, números, `_` o `-`; requerido junto con la clave | Etiqueta de gestión, sin rotación automática |

La clave y su identificador deben suministrarse juntos. El servicio HMAC falla al inicializarse sin clave en cualquier entorno; `/health` y las herramientas de persistencia pueden seguir funcionando sin crear ese servicio. La validación rechaza base64 inválido/no canónico, claves cortas o de un único byte repetido; no certifica entropía. La procedencia CSPRNG y la custodia del secreto son responsabilidad operativa. Suministrarlo mediante el mecanismo privado de configuración del servidor, sin publicarlo, imprimirlo ni incorporarlo a ejemplos, logs o variables NEXT_PUBLIC. No se añade una clave ficticia por defecto ni se comparte una clave de testing con otros entornos. Los errores de configuración ocultan entradas al representarse; no registrar `ValidationError.errors()` con sus entradas/contextos sin sanear (`include_input=False`, `include_context=False`).

[normalizar_cuenta](app/seguridad/cuentas.py) es compartida con Usuario: elimina espacios exteriores y usa `lower()`, sin reglas de proveedores ni normalización Unicode adicional. Rechaza tipos no textuales, vacío y texto no persistible en PostgreSQL (NUL o Unicode inválido). No valida por sí sola toda la sintaxis del correo; validación internacional y política de entrada siguen pendientes, sin redefinir usuarios existentes.

[ServicioIdentificadores](app/seguridad/identificadores.py) devuelve únicamente digests binarios de 32 bytes, separando dominios `cuenta` e `ip` con un prefijo versionado. No conserva entradas originales ni escribe en PostgreSQL. Canonicaliza IPv4/IPv6, equipara IPv4 mapeada en IPv6 con su IPv4 y rechaza puertos, redes, zone IDs y listas. `ip_verificada` presupone que el llamador ya verificó el origen de la IP: no consulta Request, X-Forwarded-For ni otras cabeceras. La etiqueta `id_clave` permite identificar la clave de una instancia, pero no se agrega al digest ni a las tablas. Cambiar la clave cambia los identificadores; debe acordarse cómo conservar cuotas/auditoría antes de rotarla. Cambiar solo la etiqueta no rota la clave. No hay búsqueda de claves anteriores ni rotación automática.

Los valores Argon2id son ajustables sin migración y no están calibrados para producción. Siguen pendientes mediciones, presupuesto de concurrencia, límites de entrada, política de rehash y operación de claves. Los futuros servicios de login deberán tratar cuentas inexistentes/inactivas y contraseñas incorrectas con respuesta pública uniforme y trabajo criptográfico comparable, además de controles de origen, CSRF y cuotas antes de Argon2id. Estas funciones no implementan esa orquestación ni garantizan tiempos indistinguibles.

Las pruebas de [test_fundamentos_seguridad.py](pruebas/test_fundamentos_seguridad.py) usan una clave ficticia explícita con `APP_ENV=testing` y parámetros reducidos exclusivos de sus fixtures para verificar comportamiento con rapidez. Incluyen también hash/verificación con los parámetros iniciales de 64 MiB; esa comprobación funcional no es un benchmark. Se ejecutan con la suite habitual, sin PostgreSQL para estos fundamentos.

## Requisitos

- Python 3.12 de 64 bits y pip.
- Docker Desktop y el servicio `db` iniciado para verificar PostgreSQL.
- CMD para los comandos de ejecución en Windows.
- Git Bash para el flujo de Git.

Las dependencias principales tienen versiones explícitas en `requirements.txt` y las de pruebas en `requirements-dev.txt`. Estos archivos no constituyen un bloqueo completo de dependencias transitivas.

## Preparación local en Windows

Desde la raíz de SynapDesk, en CMD:

```cmd
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
cd backend
python -m pip install -r requirements-dev.txt
python -m pip check
```

Si el entorno ya existe, basta con activarlo e instalar las dependencias. `.venv` no se versiona.

### Windows bloquea una extensión compilada de SQLAlchemy

Si la importación de `_util_cy` falla con el mensaje «Una directiva de Control de aplicaciones bloqueó este archivo», instala la misma versión de SQLAlchemy sin sus extensiones Cython. Es una modalidad admitida por SQLAlchemy y no requiere cambiar la seguridad de Windows.

Desde `backend/`, en CMD con el entorno virtual activo:

```cmd
set DISABLE_SQLALCHEMY_CEXT=1
python -m pip install --force-reinstall --no-cache-dir --no-deps --no-binary=sqlalchemy SQLAlchemy==2.1.3
set DISABLE_SQLALCHEMY_CEXT=
python -c "import sqlalchemy; from sqlalchemy.sql import _util_cy; print(sqlalchemy.__version__); print(_util_cy.__file__)"
python -m pip check
```

La ruta de `_util_cy` debe terminar en `.py`. La variable controla la construcción del paquete y no corrige una instalación binaria existente por sí sola; por eso se fuerza la reinstalación desde el código fuente. Si posteriormente se fuerza una reinstalación binaria, podría ser necesario repetir este procedimiento.

Esta modalidad conserva las funcionalidades del backend; prescinde de las optimizaciones de las extensiones compiladas. Véase la [guía oficial de instalación de SQLAlchemy](https://docs.sqlalchemy.org/en/21/intro.html#building-the-cython-extensions).

## Configuración

El backend lee el archivo `.env` de la raíz del repositorio, independientemente del directorio desde el que se ejecute. Las variables del proceso tienen precedencia sobre ese archivo.

Si todavía no existe `.env`, desde la raíz en CMD:

```cmd
if not exist .env copy .env.example .env
```

Conserva la configuración local existente y agrega las variables que falten:

El [ejemplo raíz](../.env.example) incluye las 18 variables AUTH-06 existentes. Antes de cargar una copia, reemplaza el marcador HMAC por una clave privada CSPRNG de al menos 32 bytes en base64 canónico y configura explícitamente las seis cuotas/ventanas/bloqueos como enteros positivos. Los marcadores son intencionalmente inválidos y no sirven como credenciales ni parámetros operativos. Las listas usan JSON, incluido `AUTH_ORIGENES_PERMITIDOS=["http://localhost:3000"]`; `AUTH_PROXIES_AUTORIZADOS=[]` mantiene cerrada la confianza de IP. Los valores Argon2/CSRF conservan su estado provisional y las duraciones de sesión existentes son constantes, sin variables nuevas. No reemplazar el `.env` real con la plantilla ni copiar claves ficticias de pruebas. Las [pruebas de configuración](pruebas/test_configuracion.py) cargan una copia temporal con clave ficticia y cifras explícitas del fixture, sin acceder a PostgreSQL ni modificar archivos locales.

```env
APP_ENV=development
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
POSTGRES_HOST=127.0.0.1
POSTGRES_SSLMODE=prefer
```

Reutiliza `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_PORT` del entorno Docker. No reemplaces la contraseña de una base existente con el valor de ejemplo: cambiar `.env` no cambia la contraseña guardada en el volumen de PostgreSQL.

| Variable | Formato | Comportamiento |
| --- | --- | --- |
| `APP_ENV` | `development`, `testing`, `staging` o `production` | Se valida; valor por defecto `development` |
| `BACKEND_CORS_ORIGINS` | Lista JSON de orígenes | Lista vacía si no se configura |
| `POSTGRES_HOST` | Hostname o IP | `127.0.0.1` por defecto; backend ejecutado en tu PC |
| `POSTGRES_PORT` | Entero de 1 a 65535 | `5432` por defecto; puerto publicado por Docker |
| `POSTGRES_DB` | Nombre de la base | Reutiliza el del servicio `db` |
| `POSTGRES_USER` | Usuario | Reutiliza el del servicio `db` |
| `POSTGRES_PASSWORD` | Contraseña local | Se representa como secreto en la configuración |
| `POSTGRES_SSLMODE` | Modo TLS de libpq | `prefer` por defecto para desarrollo; revisar en staging |

`APP_ENV` no selecciona automáticamente `db_test`. Las pruebas de integración construyen una configuración separada con las variables `POSTGRES_TEST_*`.

Si faltan la base, el usuario o la contraseña, la API puede responder `/health`, pero `/ready` devuelve `503`. El motor abre conexiones cuando se realizan consultas y libera sus recursos al detener la aplicación.

La URL se construye mediante `URL.create`, para conservar contraseñas con caracteres especiales sin concatenarlas manualmente. No se imprime la URL ni las excepciones del controlador. El tiempo de conexión, espera del pool y consulta se limita a cinco segundos por operación; no representa un plazo total de cinco segundos para cualquier solicitud.

Si el backend se ejecuta en un contenedor en el futuro, deberá utilizar el hostname del servicio (`db`) y su puerto interno (`5432`). La configuración actual corresponde al backend ejecutado desde CMD en tu PC.

La configuración se carga al crear la aplicación. El punto de entrada `app.main:app` crea la instancia al importarse; reinicia Uvicorn cuando modifiques `.env`. Importar la fábrica desde `app.aplicacion` no crea una instancia, no lee configuración local ni crea un motor PostgreSQL. Sin configuración explícita, la fábrica conserva la carga y validación habituales. El motor se crea durante el inicio del ciclo de vida y se libera al detener la aplicación; las conexiones se abren cuando se realizan consultas.

## Ejecutar la API

Con el entorno activo y ubicado en `backend/`:

```cmd
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: <http://127.0.0.1:8000/api/v1/health>
- Disponibilidad de PostgreSQL: <http://127.0.0.1:8000/api/v1/ready>
- Documentación: <http://127.0.0.1:8000/docs>
- Esquema OpenAPI: <http://127.0.0.1:8000/openapi.json>

Respuesta de salud:

```json
{
  "status": "ok",
  "service": "synapdesk-backend"
}
```

Respuesta de disponibilidad cuando PostgreSQL responde:

```json
{
  "status": "ready",
  "service": "synapdesk-backend",
  "database": "ok"
}
```

Si PostgreSQL no está disponible, `/ready` devuelve `503` y un error con `code`, `message`, `details` y `requestId`. No incluye credenciales, SQL ni trazas. `/health` sigue respondiendo.

Desde la raíz, en otra ventana de CMD:

```cmd
docker compose up -d db
docker compose ps
```

`--reload` se utiliza para desarrollo local. Detén el servidor con `Ctrl+C`. Docker es necesario para comprobar `/ready` contra la base local; no se necesita para `/health`.

## CORS inicial

Los orígenes permitidos se configuran mediante `BACKEND_CORS_ORIGINS`. `localhost` y `127.0.0.1` son orígenes diferentes.

Se permiten los métodos `GET`, `POST`, `PATCH` y `DELETE`, y las cabeceras `Content-Type` y `Authorization`. El middleware gestiona las solicitudes de preflight `OPTIONS`.

Las credenciales CORS están deshabilitadas mientras el mecanismo de autenticación siga pendiente. Esta configuración es inicial para desarrollo; no define la política definitiva de staging o autenticación.

CORS regula el acceso desde navegadores y no sustituye autenticación ni permisos. Un cliente de consola puede realizar solicitudes aunque su origen no figure en la lista.

## Ejecutar pruebas

Desde `backend/`, con el entorno activo y dependencias de desarrollo instaladas:

```cmd
python -m pytest pruebas -q
```

Las pruebas locales importan la fábrica desde `app.aplicacion`, utilizan configuración explícita y sustituyen el acceso a PostgreSQL cuando corresponde. El fixture de [conftest.py](pruebas/conftest.py) desactiva la lectura del `.env` real y aísla las variables de configuración del proceso para estas pruebas; las pruebas de integración conservan su selección explícita de `db_test`. No necesitan una base funcionando.

Las regresiones de [test_configuracion.py](pruebas/test_configuracion.py) utilizan archivos ficticios en directorios temporales. Comprueban importaciones frente a configuración inválida, carga y validación habituales al invocar la fábrica sin parámetros y el punto de entrada `app.main:app` sin creación de motor al importarse. También se comprueban CORS, salud, disponibilidad, errores públicos sin datos internos y liberación del motor al finalizar el ciclo de vida, incluso ante excepciones.

Validación local de la consolidación contra `main` en `098fed3`, el 30 de octubre de 2026 en Windows con Python 3.12.10: **21 pruebas aprobadas y 12 omitidas**, tanto con el entorno habitual como con variables ambientales inválidas; `python -m pip check` sin dependencias rotas. Se preservaron los cambios del frontend del PR #17 y el contrato de autenticación ya incorporado en `main`. No se instalaron dependencias ni se accedió a PostgreSQL real. `alembic heads` y `history` identificaron una única revisión inicial; el DDL de ambos modelos se contrastó en memoria, incluidos restricciones, valores iniciales e índices.

Validación posterior contra PostgreSQL real, el 30 de octubre de 2026: **33 pruebas aprobadas, 0 fallidas, 0 omitidas y 0 errores**, incluidas las **12 pruebas de integración**. Se utilizó PostgreSQL 17.11 con pgvector 0.8.6 en un contenedor exclusivo de Docker Desktop, con datos en `tmpfs`, red propia, puerto enlazado únicamente a `127.0.0.1` y credenciales temporales. La configuración se proporcionó al proceso y se deshabilitó la lectura del `.env` real durante esta ejecución. Las **21 pruebas unitarias** también aprobaron con variables ambientales inválidas; `python -m pip check` no encontró dependencias rotas.

Sobre la base temporal inicialmente vacía se aplicó `0001_usuarios_tickets`, se verificó `alembic_version` y `alembic check` no detectó diferencias con los modelos. Un segundo `upgrade head` conservó el esquema. Las pruebas comprobaron persistencia, restricciones y reversión/reaplicación de la migración; una comprobación adicional verificó commit y rollback entre sesiones independientes. Tras las pruebas, las tablas de usuarios y tickets quedaron vacías y no quedaron conexiones cliente abiertas. Con PostgreSQL disponible, `/health` y `/ready` respondieron `200`; al detener exclusivamente el contenedor temporal, `/health` mantuvo `200` y `/ready` devolvió `503` con el error público previsto, sin credenciales, SQL ni trazas. Esta validación no utilizó la base de desarrollo ni verificó un despliegue de producción.

Las pruebas de integración se omiten salvo que `EJECUTAR_PRUEBAS_BD=1`. Utilizan exclusivamente las variables `POSTGRES_TEST_*`. Verifican PostgreSQL 17, pgvector 0.8.6, disponibilidad, persistencia, restricciones y correspondencia entre modelos y migración.

Las pruebas de persistencia insertan datos ficticios y ejecutan las migraciones dentro de transacciones que se revierten al terminar. La prueba de migración revierte y reaplica la revisión dentro de esa transacción, sin realizar una reversión permanente de las tablas. Uvicorn no necesita estar iniciado para ejecutar pruebas.

### Integración con PostgreSQL real

Antes de habilitar estas pruebas, verifica que host, puerto y base correspondan a una instancia exclusiva para pruebas con datos descartables. Utiliza una base temporal nueva dentro de la instancia de pruebas del puerto 5433, sin sobrescribir bases existentes ni utilizar desarrollo en 5432. Habilita `vector` en esa base temporal y configura `POSTGRES_TEST_DB` con su nombre solo para el proceso. El nombre de la base por sí solo no demuestra ese aislamiento. Si no puedes comprobarlo, conserva las pruebas de integración omitidas.

En el `.env` de la raíz conserva las variables de testing existentes y agrega `POSTGRES_TEST_HOST=127.0.0.1` si falta. Se requieren `POSTGRES_TEST_DB`, `POSTGRES_TEST_USER` y `POSTGRES_TEST_PASSWORD`; el puerto por defecto es `5433`.

Desde la raíz, en CMD:

```cmd
docker compose --profile testing up -d db_test
docker compose --profile testing ps
```

Espera a que `db_test` figure como saludable. Luego, con el entorno virtual activo y dentro de `backend/`:

```cmd
set EJECUTAR_PRUEBAS_BD=1
python -m alembic -x base=testing upgrade head
python -m alembic -x base=testing check
python -m pytest pruebas/integracion -q
set EJECUTAR_PRUEBAS_BD=
```

Todas las pruebas PostgreSQL deben ejecutarse, no omitirse, en una validación de integración. El último comando elimina la variable en esa ventana. Si quieres ejecutar todas las pruebas con integración habilitada, utiliza `python -m pytest pruebas -q` antes de eliminarla. La prueba de versionado usa dos sesiones y conexiones independientes, confirma cambios y comprueba `StaleDataError` ante una versión obsoleta; elimina su fila al terminar. Requiere el esquema migrado previamente en la base temporal. El resto de pruebas de persistencia revierte sus transacciones. Al finalizar, elimina únicamente la base temporal identificada; no detengas contenedores existentes ni borres bases compartidas. La evidencia de ejecuciones se registra en el PR, no en este procedimiento.

Para detener solamente la base de pruebas, desde la raíz:

```cmd
docker compose --profile testing stop db_test
```

`db_test` utiliza almacenamiento temporal: sus datos se pierden al detenerla. La base de desarrollo conserva su volumen. No uses la base de desarrollo para las futuras pruebas que escriban datos.

## Migraciones con Alembic

Las migraciones permiten versionar la estructura de la base. El entorno está preparado en `migraciones/`, con configuración en `alembic.ini`. Los modelos de usuarios y tickets comparten `app.persistencia.base.Base`.

Desde `backend/`, con el entorno virtual activo:

```cmd
python -m alembic --version
python -m alembic heads
python -m alembic history
```

La revisión actual es `0002_autenticacion_persistencia`; `heads` debe mostrarla como `(head)`, con `0001_usuarios_tickets` como revisión anterior.

Para aplicar primero la revisión en `db_test`, con Docker funcionando:

```cmd
python -m alembic -x base=testing upgrade head
python -m alembic -x base=testing current
```

Este paso crea las tablas iniciales y las cinco tablas de persistencia de autenticación, y registra la revisión en `alembic_version`. Después de comprobar las pruebas de integración, aplica la misma revisión en desarrollo:

```cmd
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

`current` debe mostrar `0002_autenticacion_persistencia (head)`. `check` debe informar que no se detectaron nuevas operaciones de actualización: compara modelos registrados y estructura de la base, sin generar revisiones.

Las revisiones no insertan usuarios ni tickets. La autenticación y las rutas de estos módulos siguen pendientes. Los campos y relaciones se documentan en [Persistencia relacional inicial](../docs/arquitectura/persistencia-inicial.md); los [modelos de persistencia](app/persistencia/modelos/) comparten la misma base declarativa y la [revisión de autenticación](migraciones/versiones/0002_autenticacion_persistencia.py) depende de la revisión inicial.

Las credenciales se obtienen del `.env` y no se almacenan en `alembic.ini`. `APP_ENV=testing` no sustituye la selección explícita `-x base=testing`. FastAPI no aplica migraciones ni crea tablas automáticamente al iniciar.

Consulta el [procedimiento de migraciones](migraciones/README.md) antes de incorporar modelos y generar revisiones.

## Organización

| Ruta | Responsabilidad |
| --- | --- |
| `app/aplicacion.py` | Fábrica de aplicación, middleware y ciclo de vida PostgreSQL |
| `app/main.py` | Punto de entrada de Uvicorn y creación de la instancia `app` |
| `app/configuracion.py` | Configuración validada por entorno |
| `app/api/salud.py` | Rutas y respuestas de salud y disponibilidad |
| `app/persistencia/conexion.py` | URL, motor PostgreSQL y dependencia de acceso |
| `app/persistencia/base.py` | Base declarativa y nombres de restricciones |
| `app/persistencia/entornos.py` | Selección de base principal o testing |
| `app/persistencia/modelos/` | Modelos ORM de usuarios, tickets y persistencia de autenticación |
| `alembic.ini` | Configuración de Alembic sin credenciales |
| `migraciones/` | Entorno y revisiones de estructura |
| `pruebas/` | Pruebas automatizadas |
| `pruebas/integracion/` | Verificaciones optativas contra PostgreSQL real |
| `requirements.txt` | Dependencias de ejecución |
| `requirements-dev.txt` | Dependencias adicionales de pruebas |

## Documentación relacionada

- [Contrato frontend–backend](../docs/contratos/frontend-backend.md)
- [Modelo inicial del dominio](../docs/arquitectura/modelo-dominio.md)
- [Persistencia relacional inicial](../docs/arquitectura/persistencia-inicial.md)
- [Infraestructura y PostgreSQL](../infra/README.md)
