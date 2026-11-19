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

Desde `backend/`, con Python y Node ya instalados y la base semántica preparada:

```powershell
New-Item -ItemType Directory -Force ../artifacts | Out-Null
$env:RAG_EXTERNAL_DATA_APPROVED = 'true' # Solo si el proyecto Gemini está autorizado para esos tickets.
& 'D:/Visual Code Amemin/Recursos/SynapDesk/envs/backend-ml/Scripts/python.exe' -B -m herramientas.ingreso_local.demo `
  --frontend ../frontend --reporte ../artifacts/rag-mvp-local.json `
  --env-file ../.env --rag --remote-test-db
```

`--remote-test-db` se usa cuando PostgreSQL está en el notebook: abre solo
`127.0.0.1:5433` en este PC, lo conecta durante el ensayo a la IPv4 privada
`POSTGRES_HOST` del `.env`, crea una base aleatoria propia y la elimina al cerrar.
Exige que el usuario de PostgreSQL pueda crear bases; la base principal y la
semántica no se borran ni migran. Si la base de testing ya corre localmente en
`127.0.0.1:5433`, omitir esa opción y configurar `POSTGRES_TEST_*`. El reporte
debe tener un nombre nuevo en cada ejecución; no se sobrescribe evidencia.

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
ticket sintético de DNS, comprueba respuesta HTTP 201 con fuentes, revisión HTTP
204, persistencia en SQL y recarga de la interfaz. La ejecución local del
19-11-2026 completó 99 comprobaciones y eliminó su base temporal. Los informes
quedan bajo `ml/artifacts/`, excluidos de Git.
