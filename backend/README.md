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
- Modelos de usuarios y tickets y revisión `0001_usuarios_tickets`.
- Pruebas unitarias de salud, CORS, configuración y disponibilidad.
- Pruebas de integración optativas de conexión, persistencia y migraciones contra `db_test`.

Las tablas de usuarios y tickets se crean al aplicar las migraciones. Sus endpoints, autenticación e integración ML siguen pendientes. El endpoint `/health` no comprueba la base de datos ni el modelo ML. `/ready` verifica acceso a PostgreSQL mediante `SELECT 1`; no verifica tablas, migraciones, pgvector ni ML.

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

La configuración se carga al iniciar cada proceso. Reinicia Uvicorn cuando modifiques `.env`.

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

Se esperan **10 pruebas aprobadas y 12 omitidas**. Las pruebas unitarias utilizan configuración explícita y sustituyen el acceso a PostgreSQL cuando corresponde. Comprueban también que un fallo no publique información interna y que la selección de testing use sus propias credenciales. No necesitan una base funcionando.

Las doce pruebas de integración se omiten salvo que `EJECUTAR_PRUEBAS_BD=1`. Utilizan exclusivamente las variables `POSTGRES_TEST_*`. Verifican PostgreSQL 17, pgvector 0.8.6, disponibilidad, persistencia, restricciones y correspondencia entre modelos y migración.

Las pruebas de persistencia insertan datos ficticios y ejecutan las migraciones dentro de transacciones que se revierten al terminar. La prueba de migración revierte y reaplica la revisión dentro de esa transacción, sin realizar una reversión permanente de las tablas. Uvicorn no necesita estar iniciado para ejecutar pruebas.

### Integración con PostgreSQL real

En el `.env` de la raíz conserva las variables de testing existentes y agrega `POSTGRES_TEST_HOST=127.0.0.1` si falta. Se requieren `POSTGRES_TEST_DB`, `POSTGRES_TEST_USER` y `POSTGRES_TEST_PASSWORD`; el puerto por defecto es `5433`.

Desde la raíz, en CMD:

```cmd
docker compose --profile testing up -d db_test
docker compose --profile testing ps
```

Espera a que `db_test` figure como saludable. Luego, con el entorno virtual activo y dentro de `backend/`:

```cmd
set EJECUTAR_PRUEBAS_BD=1
python -m pytest pruebas/integracion -q
set EJECUTAR_PRUEBAS_BD=
```

Se esperan **12 pruebas aprobadas**. El último comando elimina la variable en esa ventana. Si quieres ejecutar todas las pruebas con integración habilitada, utiliza `python -m pytest pruebas -q` antes de eliminarla: se esperan **22 pruebas aprobadas**.

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

La revisión actual es `0001_usuarios_tickets`; `heads` debe mostrarla como `(head)`.

Para aplicar primero la revisión en `db_test`, con Docker funcionando:

```cmd
python -m alembic -x base=testing upgrade head
python -m alembic -x base=testing current
```

Este paso crea `usuarios` y `tickets`, y registra la revisión en `alembic_version`. Después de comprobar las pruebas de integración, aplica la misma revisión en desarrollo:

```cmd
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

`current` debe mostrar `0001_usuarios_tickets (head)`. `check` debe informar que no se detectaron nuevas operaciones de actualización: compara modelos registrados y estructura de la base, sin generar revisiones.

La revisión no inserta usuarios ni tickets. La autenticación y las rutas de estos módulos siguen pendientes. Los campos físicos se documentan en [Persistencia relacional inicial](../docs/arquitectura/persistencia-inicial.md).

Las credenciales se obtienen del `.env` y no se almacenan en `alembic.ini`. `APP_ENV=testing` no sustituye la selección explícita `-x base=testing`. FastAPI no aplica migraciones ni crea tablas automáticamente al iniciar.

Consulta el [procedimiento de migraciones](migraciones/README.md) antes de incorporar modelos y generar revisiones.

## Organización

| Ruta | Responsabilidad |
| --- | --- |
| `app/main.py` | Creación de la aplicación y middleware |
| `app/configuracion.py` | Configuración validada por entorno |
| `app/api/salud.py` | Ruta y respuesta de salud |
| `app/persistencia/conexion.py` | URL, motor PostgreSQL y dependencia de acceso |
| `app/persistencia/base.py` | Base declarativa y nombres de restricciones |
| `app/persistencia/entornos.py` | Selección de base principal o testing |
| `app/persistencia/modelos/` | Modelos ORM de usuarios y tickets |
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
