# Backend

API de SynapDesk basada en FastAPI y Pydantic, con prefijo /api/v1.

## Estado actual

- Aplicación ejecutable con Uvicorn.
- Endpoint GET /api/v1/health para comprobar que la API responde.
- Documentación OpenAPI en /docs y esquema en /openapi.json.
- Configuración mediante variables de entorno y el archivo .env de la raíz.
- CORS con orígenes explícitos para el frontend local.
- Pruebas automatizadas de salud, CORS y aislamiento de configuración.

La conexión con PostgreSQL, migraciones, autenticación, tickets e integración ML todavía no están implementadas. El endpoint de salud no comprueba la base de datos ni el modelo ML.

## Requisitos

- Python 3.12 de 64 bits y pip.
- CMD para los comandos de ejecución en Windows.
- Git Bash para el flujo de Git.

Las dependencias principales tienen versiones explícitas en [requirements.txt](requirements.txt) y las de pruebas en [requirements-dev.txt](requirements-dev.txt). Estos archivos no constituyen un bloqueo completo de dependencias transitivas.

## Preparación local en Windows

Desde la raíz de SynapDesk, en CMD:

~~~cmd
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
cd backend
python -m pip install -r requirements-dev.txt
python -m pip check
~~~

Si el entorno ya existe, basta con activarlo e instalar las dependencias. La carpeta .venv no se versiona.

## Configuración

El backend lee el archivo .env de la raíz del repositorio, independientemente del directorio desde el que se ejecute. Las variables del proceso tienen precedencia sobre ese archivo.

Si todavía no existe .env, desde la raíz en CMD:

~~~cmd
if not exist .env copy .env.example .env
~~~

Conserva la configuración local existente y agrega las variables que falten:

~~~env
APP_ENV=development
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
~~~

| Variable | Formato | Comportamiento |
| --- | --- | --- |
| APP_ENV | development, testing, staging o production | Se valida; valor por defecto development. |
| BACKEND_CORS_ORIGINS | Lista JSON de orígenes | Lista vacía si no se configura. |

APP_ENV no configura por sí sola un despliegue ni habilita funcionalidades pendientes. Las demás variables del archivo .env compartido se ignoran en este bloque de configuración.

La configuración se carga al crear la aplicación. El punto de entrada de Uvicorn crea la instancia al importarse; reinicia Uvicorn cuando modifiques .env. Importar la fábrica desde app.aplicacion no crea una instancia ni lee configuración local. Si se invoca sin configuración explícita, la fábrica sigue cargando la configuración habitual.

## Ejecutar la API

Con el entorno activo y ubicado en backend/:

~~~cmd
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

- API: <http://127.0.0.1:8000/api/v1/health>
- Documentación: <http://127.0.0.1:8000/docs>
- Esquema OpenAPI: <http://127.0.0.1:8000/openapi.json>

Respuesta de salud:

~~~json
{
  "status": "ok",
  "service": "synapdesk-backend"
}
~~~

La opción --reload se utiliza para desarrollo local. Detén el servidor con Ctrl+C. Docker no es necesario para este endpoint, ya que todavía no consulta PostgreSQL.

## CORS inicial

Los orígenes permitidos se configuran mediante BACKEND_CORS_ORIGINS. localhost y 127.0.0.1 son orígenes diferentes.

Se permiten los métodos GET, POST, PATCH y DELETE, y las cabeceras Content-Type y Authorization. El middleware gestiona las solicitudes de preflight OPTIONS.

Las credenciales CORS están deshabilitadas mientras el mecanismo de autenticación siga pendiente. Esta configuración es inicial para desarrollo; no define la política definitiva de staging o autenticación.

CORS regula el acceso desde navegadores y no sustituye autenticación ni permisos. Un cliente de consola puede realizar solicitudes aunque su origen no figure en la lista.

## Ejecutar pruebas

Desde backend/, con el entorno activo y dependencias de desarrollo instaladas:

~~~cmd
python -m pip check
python -m pytest pruebas -q
~~~

Se esperan siete pruebas aprobadas. Las pruebas de salud y CORS importan la fábrica desde app.aplicacion y utilizan configuración explícita con _env_file=None. El fixture automático de [conftest.py](pruebas/conftest.py) aísla APP_ENV y BACKEND_CORS_ORIGINS del proceso anfitrión.

Las regresiones de [test_configuracion.py](pruebas/test_configuracion.py) usan archivos .env ficticios en directorios temporales: verifican que importar la fábrica no lea configuración inválida, que se pueda probar salud con configuración explícita y que la fábrica conserve la carga y validación del entorno cuando se invoca sin parámetros. No leen ni modifican el archivo .env real.

El servidor Uvicorn no necesita estar iniciado para ejecutar estas pruebas. Las futuras pruebas de persistencia deberán utilizar exclusivamente db_test.

### Evidencia local de revisión del PR #15

Validado el 29 de octubre de 2026 en Windows con Python 3.12.10, utilizando el entorno virtual existente y sin instalar ni actualizar dependencias:

- python -m pip check: sin dependencias rotas.
- python -m pytest pruebas -q: 7 pruebas aprobadas.

Los comandos anteriores permiten repetir la comprobación; no se necesita Docker ni un servidor en ejecución.

## Organización

| Ruta | Responsabilidad |
| --- | --- |
| [app/aplicacion.py](app/aplicacion.py) | Fábrica crear_aplicacion y middleware; importar el módulo no crea la aplicación. |
| [app/main.py](app/main.py) | Punto de entrada de Uvicorn y creación de la instancia app. |
| [app/configuracion.py](app/configuracion.py) | Configuración validada por entorno. |
| [app/api/salud.py](app/api/salud.py) | Ruta y respuesta de salud. |
| [pruebas/](pruebas/) | Pruebas automatizadas y aislamiento del entorno. |
| [requirements.txt](requirements.txt) | Dependencias de ejecución. |
| [requirements-dev.txt](requirements-dev.txt) | Dependencias adicionales de pruebas. |

## Documentación relacionada

- [Contrato frontend–backend](../docs/contratos/frontend-backend.md)
- [Modelo inicial del dominio](../docs/arquitectura/modelo-dominio.md)
- [Infraestructura y PostgreSQL](../infra/README.md)
