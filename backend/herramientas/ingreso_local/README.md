# Ensayo local de navegador y PostgreSQL

Composición explícita de **testing**, independiente de la fábrica productiva.
MVP11 conserva las páginas de main `ca1d572` (#47/#48/#49), incorpora selectivamente
el candidato MVP09 `ba2422f` y el logout de MVP10 `c81367a`. No valida
Render, HTTPS público, cookies Secure en Edge ni un bootstrap operativo.

El [procedimiento MVP12](../../../docs/integracion/mvp12-actualizacion-pr52.md)
contiene el candidato vigente con historia de PR #52 preservada, inicio y cierre.
La [guía MVP11 histórica](../../../docs/guia-ensayo-reconciliado-mvp11.md) describe
el ensayo anterior sobre main actualizado. La
[guía local histórica](../../../docs/guia-recorrido-local-mvp.md) contiene los pasos de
preparación y los requisitos de provisión administrativa. El
[procedimiento de entrega MVP10](../../../docs/guia-entrega-academica-mvp10.md)
incluye inicio, cierre y limitaciones acreditadas. El
[verificador portable](verificar.py) no conoce rutas de otros worktrees ni carga
automáticamente sus archivos privados; se ejecuta desde backend:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.verificar --modo todo --playwright-module RUTA_PRIVADA_PLAYWRIGHT_CORE
```

Usar el intérprete ya preparado en la copia. `--env-file` permite leer en memoria
un archivo privado explícito; no lo copia, imprime ni lo versiona. La salida por
defecto es un directorio nuevo bajo artifacts/ de **esta** copia. Se rechazan
directorios existentes o externos. No instala Python, Node, Docker, Edge ni módulos.

## Componentes y límites

- [aplicacion.py](aplicacion.py): compone CSRF/login/me/logout y POST/GET/PATCH de tickets
  con adaptadores existentes. No agrega rutas a app.aplicacion ni administración.
- [evidencia.py](evidencia.py), [protocolo.mjs](protocolo.mjs) y
  [servidor_next.mjs](servidor_next.mjs): IP observada en socket, HMAC independiente,
  audiencia, controles originales, nonce único y SEC-01B/TLS. Rechazan IP declarada,
  replay y manipulación. Solo un worker local y claves nuevas por ejecución.
- [demo.py](demo.py): base propia aleatoria en 5433, Alembic, cuentas efímeras,
  backend TLS y Next real. Edge obtiene sesiones sólo por login. Los checkpoints
  SQL usan una conexión independiente antes y después del cambio de estado.
- [browser-crud.mjs](../../../frontend/tests/proxy/browser-crud.mjs): formulario
  real, creación, listado, detalle, cambio de estado y recarga para admin/agent.
  Los negativos de HTTP crudo se distinguen de las interacciones de interfaz.

No usa respuestas mock, no fabrica sesiones, no desactiva TLS/Origin/CSRF,
no reintenta escrituras y no necesita ML. Las dos cuentas y doce tickets iniciales son
fixtures explícitas de una base testing desechable, **no** una vía de bootstrap
operativo. No copiar este seed a desarrollo o producción. Los tickets comprobados
como creación de navegador tienen UUID nuevos, distintos de esos seeds.

Al terminar elimina únicamente la base aleatoria y los procesos, certificados y
archivos privados que creó. Los contenedores existentes siguen ejecutándose.
Los reportes saneados permanecen fuera de Git. Un fallo de cierre/limpieza no se
considera éxito; Windows requiere permiso para cerrar los procesos propios.

La UI es la actual de main: listado paginado, formulario y TicketStatusControl.
Los filtros pendientes se anuncian explícitamente en este ensayo y una URL con
filtros no se interpreta como un listado filtrado. Las recomendaciones ausentes
no impiden leer ni cambiar el estado del ticket. El transporte conserva la política
de cookies de #30; no se importa la variante antigua de MVP07.

## Ensayo RAG del MVP

La opción `--rag` incorpora en **esta composición de testing** las rutas de generar,
listar, consultar y revisar recomendaciones. Conserva el mismo ingreso verificado,
sesión, Origin, CSRF, TLS y credencial de servicio. Requiere la migración `0007`,
recuperación V2 preparada, `GEMINI_API_KEY` y aprobación explícita mediante
`RAG_EXTERNAL_DATA_APPROVED=true`. Sin `--rag` el ensayo CRUD no genera contenido.

Desde `backend/`, con Python y Node ya instalados, la base semántica preparada y
una instancia **exclusiva de testing** en `127.0.0.1:5433` con credenciales
`POSTGRES_TEST_*` independientes de la base principal:

```powershell
New-Item -ItemType Directory -Force ../artifacts | Out-Null
$env:RAG_EXTERNAL_DATA_APPROVED = 'true' # Solo si el proyecto Gemini está autorizado para esos tickets.
python -B -m herramientas.ingreso_local.demo `
  --frontend ../frontend --reporte ../artifacts/rag-mvp-local.json `
  --env-file ../.env --rag
```

El servicio `db_test` de `compose.yaml` puede proporcionar esa instancia. Si
PostgreSQL está en otro equipo, ejecutar allí el ensayo junto a `db_test` o
conectar el PC mediante un túnel seguro que exponga **solo `db_test`** en
`127.0.0.1:5433`. No conectar el puerto de la base principal ni reutilizar
`POSTGRES_USER` o `POSTGRES_PASSWORD` para `POSTGRES_TEST_*`. La cuenta de testing
debe poder crear y eliminar bases temporales en su propia instancia. El arnés
rechaza otro host o puerto; crea una base aleatoria y la elimina al cerrar.
El reporte debe tener un nombre nuevo en cada ejecución; no se sobrescribe evidencia.

Abrir la URL impresa, obtener las credenciales efímeras del archivo privado
indicado por el lanzador, iniciar sesión, crear un ticket relacionado con el
corpus y abrir su Asistente IA. Generar, revisar fuentes y aceptar, modificar o
descartar. El estado del ticket se cambia aparte. Al terminar, pulsar Enter en
la consola del lanzador para cerrar sus procesos y eliminar su base temporal.
El reporte identifica el cierre. Este ensayo no acredita Render ni calidad de
recomendaciones sin revisión humana.

Para repetir automáticamente el recorrido en Edge, configurar
`PLAYWRIGHT_MODULE` con la ruta local de `playwright-core` ya instalado y añadir
`--browser-driver ../frontend/tests/proxy/browser-crud.mjs`. El driver usa un
ticket sintético de DNS con título y descripción constantes: el UUID del ticket
ya permite identificarlo dentro de su base aislada. Un UUID aleatorio en el título
alteraba la consulta semántica entre ejecuciones.

### Recorrido reproducible sin proveedor externo

Desde `backend/`, con `PLAYWRIGHT_MODULE` configurado, ejecutar cada escenario con
un nombre de reporte nuevo:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.demo `
  --frontend ../frontend --reporte ../artifacts/rag-fixture-draft.json `
  --browser-driver ../frontend/tests/proxy/browser-crud.mjs `
  --env-file ../.env --rag --rag-fixture draft

./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.demo `
  --frontend ../frontend --reporte ../artifacts/rag-fixture-abstention.json `
  --browser-driver ../frontend/tests/proxy/browser-crud.mjs `
  --env-file ../.env --rag --rag-fixture abstention
```

Estos modos requieren solo `db_test`, Python, Next, Edge y Playwright preparados.
Sustituyen la recuperación y la respuesta del proveedor por datos sintéticos
constantes; no usan la base semántica ni llaman a Gemini. La orquestación, el
validador de citas, la API, el ingreso TLS, la sesión, CSRF, la interfaz y SQL
siguen siendo reales. Solo se admiten dentro de la composición aislada de testing.

`draft` exige HTTP 201 con fuentes, revisión HTTP 204 y persistencia de la aceptación
en SQL y después de recargar la interfaz. `abstention` entrega `steps: []` al
validador real y exige `422 INSUFFICIENT_INFORMATION`, `Cache-Control: no-store`,
el mensaje de abstención y ausencia de recomendaciones tanto en API como en SQL
y después de recargar. La abstención no modifica el estado del ticket. Ambos
escenarios continúan los controles CRUD, logout, revocación e inactividad.

Los informes identifican `rag_mode: fixture` y el escenario. Un resultado correcto
de este modo acredita el recorrido, **no** al proveedor externo ni la calidad de
una recomendación real.

### Recorrido con recuperación V2 y Gemini reales

Usar `--rag` sin `--rag-fixture`, con las opciones de recuperación y la aprobación
externa explícitamente configuradas. `SEARCH_ENABLED`, `SEARCH_RELEVANCE_PROFILE`,
la conexión semántica, `GEMINI_API_KEY` y `RAG_EXTERNAL_DATA_APPROVED` deben estar
preparados; los fixtures no los habilitan para ejecuciones posteriores.

Por defecto se exige un borrador y su revisión. `--rag-expect abstention` permite
exigir una abstención; `--rag-expect either` acepta ambas respuestas válidas y
continúa CRUD. En ese último modo, consultar `browser.rag.reviewVerified`: `false`
significa que no se cubrió la revisión. No se reintenta la generación para forzar
un HTTP 201. Otros errores 422 y los 5xx siguen haciendo fallar el recorrido.

`browser.rag` conserva estado HTTP, código de error conocido, resultado esperado,
resultado observado y cobertura de revisión, sin copiar cuerpos de error.
`responseJsonValid` indica si se pudo interpretar el cuerpo; una respuesta no
JSON conserva su estado HTTP y hace fallar el ensayo sin copiar el cuerpo.
`rag_events` distingue abstención en recuperación o en generación usando únicamente
resultado, etapa, número de fuentes y duración. Del proveedor conserva únicamente
resultado, estado HTTP si falla, modelo fijo, duración y contadores de tokens
permitidos si existen. No registra entradas, fragmentos,
respuestas del proveedor ni claves. Los reportes y capturas quedan en la ruta
indicada, bajo `artifacts/` o `ml/artifacts/`, excluidos de Git. Cada ejecución
elimina únicamente su base y sus recursos temporales al cerrar.

Cada solicitud y confirmación SQL usa un archivo nuevo por secuencia, publicado
de forma atómica. Así Edge no lee JSON parcial ni se reemplaza un archivo que
el otro proceso pueda tener abierto en Windows. Un bloqueo transitorio al
publicar la respuesta se tolera hasta dos segundos, sin repetir operaciones SQL.

## Búsqueda sin Gemini

El [recorrido HU07](../../../docs/gestion/busqueda-ensayo-protegido.md) agrega `--search` y `--search-fixture`, con sesión/CSRF reales y una base de testing exclusiva. No cambia la política de relevancia.
