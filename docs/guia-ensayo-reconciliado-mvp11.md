# Ensayo MVP11 sobre main actualizado

> Registro histórico del ensayo MVP11. Para la rama que conserva el historial de
> PR #52 usar el [procedimiento MVP12](integracion/mvp12-actualizacion-pr52.md).

Rama local `correccion/mvp11-reconciliar-crud-logout`, base
`ca1d572c35472af525e4a2d85bf38881265e5818`. Incorpora selectivamente PR #52
`ba2422fadff2cab93ab842a6ecdd3990f1434471` y logout MVP10
`c81367aae9a7213581afb02f69976e91ba39a5a0` sin modificar esas ramas.
La [reconciliación](integracion/mvp11-reconciliacion.md) registra las decisiones.

## Requisitos y alcance

Se usa el [arnés existente](../backend/herramientas/ingreso_local/README.md),
Python 3.12 con las dependencias backend, Node del lockfile, OpenSSL, Edge instalado,
playwright-core disponible y PostgreSQL 17 con pgvector 0.8.6 exclusivo de testing.
El archivo privado explícito se lee en memoria; no se copia ni se versiona.
No hay despliegue, bootstrap operativo ni acreditación de Render.

La fábrica exige APP_ENV=testing y base aleatoria propia. Conserva TLS y CA entre
Next y FastAPI, Origin, CSRF, cookies estrictas, SEC-01B, evidencia de socket firmada
y antirreplay, sesiones persistentes, cuenta activa y autorización admin/agent.
Edge accede por HTTP loopback con perfil local: no acredita cookies Secure públicas.
No ejecutar el seed de cuentas efímeras en desarrollo o producción.

## Inicio reproducible en este equipo

Desde PowerShell, con las dependencias ya preparadas en este equipo:

```powershell
$raizDemo = 'C:/Users/Felipe/Desktop/SynapDesk'
$copiaDemo = Join-Path $raizDemo 'artifacts/mvp11-reconciliation-20261118'
$pythonDemo = Join-Path $raizDemo 'artifacts/repair-main-ci-worktree-20261118/backend/.venv/Scripts/python.exe'
$privadoDemo = Join-Path $raizDemo '.env'
$playwrightDemo = Join-Path $raizDemo 'artifacts/mvp09-browser-tools/node_modules/playwright-core'
Set-Location (Join-Path $copiaDemo 'backend')
& $pythonDemo -B -m herramientas.ingreso_local.verificar --modo navegador --env-file $privadoDemo --playwright-module $playwrightDemo
```

El verificador crea una salida nueva, base temporal, cuentas ficticias y claves
efímeras. Hace login real por formulario; no fabrica sesiones ni intercepta
respuestas. Guarda reportes saneados y capturas fuera de Git.

Para la presentación manual usar el mismo lanzador, sin un segundo arranque:

```powershell
$env:PYTHONUTF8 = '1'
$env:SYNAPDESK_DEMO_ENV_FILE = $privadoDemo
$reporteDemo = '../artifacts/demo-manual-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json'
$inicioDemo = @'
from dotenv import dotenv_values
import os, runpy
os.environ.update({k: v for k, v in dotenv_values(os.environ['SYNAPDESK_DEMO_ENV_FILE']).items() if v is not None})
runpy.run_module('herramientas.ingreso_local.demo', run_name='__main__')
'@
& $pythonDemo -B -c $inicioDemo --frontend ../frontend --reporte $reporteDemo
```

Esperar la URL loopback y la ruta privada de credenciales. Mantener la consola
abierta. Consultar las cuentas efímeras sólo localmente; no mostrarlas en evidencia.

## Recorrido y cierre

1. Admin: formulario de login, CSRF y /me; crear ticket sintético.
2. Listado paginado, detalle, cambio de estado y recarga. Mostrar evidencia SQL
   saneada de inserción y persistencia.
3. Cerrar sesión: 204, vuelta al login, revocación SQL y cookie anterior rechazada.
4. Agent: repetir login, creación, listado, detalle, estado, recarga y logout.
5. Mostrar los rechazos acreditados de anónimo, sesión revocada, cuenta inactiva,
   Origin/CSRF/cookie/estado/campos inválidos y procedencia/SEC-01B inválida.
6. En modo manual pulsar Enter en la consola. Esperar database_deleted,
   next_stopped, fastapi_stopped y temporary_deleted en true. El modo automático
   cierra solo. No cerrar contenedores o procesos ajenos.

La UI conserva #47/#48/#49: las cargas opcionales de métricas/recomendaciones
usan Suspense y su ausencia no bloquea el CRUD; filtros y búsqueda de tickets
permanecen deshabilitados. La página administrativa sigue siendo un placeholder.
No afirmar soporte de filtros, PATCH ampliado o administración que no existe.

La recuperación semántica de main se conserva; el lanzador CRUD no habilita su
API. No se demuestra inferencia con modelo real ni clasificación sin artefactos
validados. El RAG separado usa respuestas simuladas, no generación real.
Las dependencias y artefactos pendientes se describen en el
[registro histórico MVP10](guia-entrega-academica-mvp10.md#búsqueda-modelos-y-rag).

Antes del jueves 19-11-2026, 23:59 America/Santiago: repetir el verificador en el
SHA seleccionado, revisar reporte y limpieza, comprobar herramientas y testing,
y ensayar el recorrido. La publicación, CI remota y revisión formal de PR #52 son
pasos posteriores con autorización; no hay push ni merge en esta preparación.
