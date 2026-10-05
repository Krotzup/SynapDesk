Backend
API de SynapDesk basada en FastAPI y Pydantic, con prefijo /api/v1.
Estado actual
- Aplicación ejecutable con Uvicorn.
- Endpoint GET /api/v1/health para comprobar que la API responde.
- Documentación OpenAPI en /docs y esquema en /openapi.json.
- Configuración mediante variables de entorno y el .env de la raíz.
- CORS con orígenes explícitos para el frontend local.
- Pruebas automatizadas de salud y CORS.
La conexión con PostgreSQL, migraciones, autenticación, tickets e integración ML todavía no están implementadas. El endpoint de salud no comprueba la base de datos ni el modelo ML.
Requisitos
- Python 3.12 de 64 bits y pip.
- CMD para los comandos de ejecución en Windows.
- Git Bash para el flujo de Git.
Las dependencias principales tienen versiones explícitas en requirements.txt y las de pruebas en requirements-dev.txt. Estos archivos no constituyen un bloqueo completo de dependencias transitivas.
Preparación local en Windows
Desde la raíz de SynapDesk, en CMD:
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
cd backend
python -m pip install -r requirements-dev.txt
python -m pip check
Si el entorno ya existe, basta con activarlo e instalar las dependencias. .venv no se versiona.
Configuración
El backend lee el archivo .env de la raíz del repositorio, independientemente del directorio desde el que se ejecute. Las variables del proceso tienen precedencia sobre ese archivo.
Si todavía no existe .env, desde la raíz en CMD:
if not exist .env copy .env.example .env
Conserva la configuración local existente y agrega las variables que falten:
APP_ENV=development
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
Variable	Formato	Comportamiento
APP_ENV	development, testing, staging o production	Se valida; valor por defecto development
BACKEND_CORS_ORIGINS	Lista JSON de orígenes	Lista vacía si no se configura


APP_ENV no configura por sí sola un despliegue ni habilita funcionalidades pendientes. Las demás variables del .env compartido se ignoran en este bloque de configuración.
La configuración se carga al iniciar cada proceso. Reinicia Uvicorn cuando modifiques .env.
Ejecutar la API
Con el entorno activo y ubicado en backend/:
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
- API: http://127.0.0.1:8000/api/v1/health
- Documentación: http://127.0.0.1:8000/docs
- Esquema OpenAPI: http://127.0.0.1:8000/openapi.json
Respuesta de salud:
{
  "status": "ok",
  "service": "synapdesk-backend"
}
--reload se utiliza para desarrollo local. Detén el servidor con Ctrl+C. Docker no es necesario para este endpoint, ya que todavía no consulta PostgreSQL.
CORS inicial
Los orígenes permitidos se configuran mediante BACKEND_CORS_ORIGINS. localhost y 127.0.0.1 son orígenes diferentes.
Se permiten los métodos GET, POST, PATCH y DELETE, y las cabeceras Content-Type y Authorization. El middleware gestiona las solicitudes de preflight OPTIONS.
Las credenciales CORS están deshabilitadas mientras el mecanismo de autenticación siga pendiente. Esta configuración es inicial para desarrollo; no define la política definitiva de staging o autenticación.
CORS regula el acceso desde navegadores y no sustituye autenticación ni permisos. Un cliente de consola puede realizar solicitudes aunque su origen no figure en la lista.
Ejecutar pruebas
Desde backend/, con el entorno activo y dependencias de desarrollo instaladas:
python -m pytest pruebas -q
Las pruebas verifican la respuesta de salud y el preflight CORS para un origen autorizado y otro no autorizado. Utilizan configuración explícita de testing, sin cargar el .env local para esa configuración ni conectarse a la base de datos.
El servidor Uvicorn no necesita estar iniciado para ejecutar estas pruebas. Las futuras pruebas de persistencia deberán utilizar exclusivamente db_test.
Organización
Ruta	Responsabilidad
app/main.py	Creación de la aplicación y middleware
app/configuracion.py	Configuración validada por entorno
app/api/salud.py	Ruta y respuesta de salud
pruebas/	Pruebas automatizadas
requirements.txt	Dependencias de ejecución
requirements-dev.txt	Dependencias adicionales de pruebas


Documentación relacionada
- [Contrato frontend–backend](../docs/contratos/frontend-backend.md)
- [Modelo inicial del dominio](../docs/arquitectura/modelo-dominio.md)
- [Infraestructura y PostgreSQL](../infra/README.md)