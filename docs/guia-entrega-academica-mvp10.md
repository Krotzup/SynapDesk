# Demostración académica MVP10 — testing aislado

> Registro histórico del ensayo sobre MVP09. Para el candidato reconciliado con
> main y las mejoras #47/#48/#49 usar la [guía MVP11](guia-ensayo-reconciliado-mvp11.md).

Fecha límite: 19-11-2026, 23:59, America/Santiago. Este procedimiento prepara una
demostración local; no acredita Render ni operación productiva.

## Candidato que se debe usar

Rama local `correccion/mvp10-cierre-sesion-ensayo`, basada en el candidato publicado
`ba2422fadff2cab93ab842a6ecdd3990f1434471`. No usar una copia arbitraria de main:
los PR #47/#48/#49 se integraron después y PR #52 presenta conflictos de interfaz
al preparar esta entrega. La rama original y el PR permanecen intactos. La
corrección de cierre de sesión de esta copia es local, pendiente de publicación.

Se observó HTTP 404 al pulsar «Cerrar sesión» en el candidato anterior. La única
corrección funcional conecta el adaptador de logout ya existente en la fábrica
testing y su ruta POST en el lanzador local. No reconstruye autenticación ni
tickets; no modifica servicios, DTO, migraciones o políticas de seguridad.

## Requisitos comprobados

- Python 3.12.10 y dependencias existentes. En este equipo se reutiliza el venv de
  la corrección CI, sin instalar ni modificar paquetes en él.
- Node/Next del lockfile ya instalados en esta copia y Microsoft Edge instalado
  157.0.4341.60. Automatización con playwright-core 1.58.2 ya disponible.
- PostgreSQL de testing 17.11 y pgvector 0.8.6 en loopback:5433. El arnés crea
  otra base aleatoria exclusiva `synapdesk_auth07_sec01a_<UUID>` y comprueba
  identidad y migraciones `0006_user_created`; nunca usa desarrollo ni producción.
- Variables de testing en el archivo privado explícito de la raíz: host, puerto,
  base de control, usuario y contraseña de testing. No copiarlo a esta rama ni
  mostrar valores. El proceso los lee en memoria por el mecanismo existente.
- OpenSSL de Git for Windows; CA y certificados efímeros propios. Next→FastAPI
  usa HTTPS con CA/hostname verificados y SEC-01B. Edge→Next usa HTTP loopback
  sólo bajo el perfil local testing; esto no acredita cookies productivas.

APP_ENV=testing se comprueba en la composición. Se mantienen Origin, CSRF,
cookies estrictas, sesiones persistentes, rol/cuenta activa, evidencia de socket,
firma y antirreplay. No usar opciones para desactivar TLS o controles.

## Inicio reproducible en este equipo

Abrir PowerShell desde la raíz del repositorio. Son rutas de herramientas y del
archivo privado; ninguna contraseña va en argumentos o URL:

```powershell
$raizDemo = 'C:/Users/Felipe/Desktop/SynapDesk'
$copiaDemo = Join-Path $raizDemo 'artifacts/mvp10-delivery-worktree-20261118'
$pythonDemo = Join-Path $raizDemo 'artifacts/repair-main-ci-worktree-20261118/backend/.venv/Scripts/python.exe'
$privadoDemo = Join-Path $raizDemo '.env'
$playwrightDemo = Join-Path $raizDemo 'artifacts/mvp09-browser-tools/node_modules/playwright-core'
Set-Location (Join-Path $copiaDemo 'backend')
```

Para repetir automáticamente el recorrido acreditado en Edge real:

```powershell
& $pythonDemo -B -m herramientas.ingreso_local.verificar --modo navegador --env-file $privadoDemo --playwright-module $playwrightDemo
```

Para mostrarlo manualmente, se usa el mismo `herramientas.ingreso_local.demo` ya
existente. Esta envoltura sólo carga el archivo privado explícito en memoria:

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

Esperar la URL loopback y `private_credentials_file`. Mantener esta consola
abierta. Abrir la URL en Edge y consultar el archivo privado local únicamente
para las cuentas efímeras admin/agent; no pegar su contenido en chat, informes o
grabaciones. Cada ejecución genera cuentas y contraseñas nuevas `example.invalid`
con Argon2id, doce tickets iniciales y ninguna sesión previa al login. Son
fixtures autorizadas del ensayo, no un bootstrap operativo acreditado.

## Secuencia sugerida de demostración

1. Mostrar el alcance testing y el SHA local seleccionado, sin archivos privados.
2. Login admin con el formulario; el navegador obtiene CSRF. Confirmar /me con rol
   admin mediante la respuesta HTTP, sin mostrar cookies ni tokens.
3. Abrir `/tickets/nuevo`, crear un ticket sintético y mostrar el HTTP 201.
4. Mostrar listado paginado, abrir el detalle y actualizar el estado. Recargar:
   el valor persiste. La ejecución automática confirma inserción/actualización
   con conexiones SQL independientes; mostrar su reporte saneado si hace falta.
5. Abrir el menú de usuario y cerrar sesión: HTTP 204 y vuelta al login; el
   reporte automático confirma revocación SQL y rechazo de la cookie anterior.
6. Ingresar como agent y repetir creación/listado/detalle/cambio de estado/recarga
   y logout. Los dos roles usan las autorizaciones existentes.
7. Mostrar la evidencia automática de rechazos de Origin, CSRF, cookie ambigua,
   anónimo, estado/campos inválidos, sesión revocada y cuenta inactiva, además de
   SEC-01B inválido por TLS. No modificar controles durante la presentación.
8. Explicar las funciones ML según el estado real detallado abajo.
9. Cerrar el arnés desde su consola y comprobar la limpieza antes de terminar.

## Cierre seguro

En la consola del arnés manual pulsar **Enter**. Esperar la salida con
`database_deleted`, `next_stopped`, `fastapi_stopped` y `temporary_deleted` en true.
El arnés elimina sólo sus procesos, base, certificados y archivos privados.
No ejecutar kill por nombre, compose down, prune ni limpiar otros worktrees.

El verificador automático se cierra solo. Su base se elimina al final: la
persistencia acreditada comprende conexiones SQL, navegación y recarga durante
el ensayo, no conservación después de borrar deliberadamente la base.

## Búsqueda, modelos y RAG

| Función | Estado de esta entrega |
|---|---|
| API/interfaz de búsqueda implementada en main | Existe y conserva controles de sesión/Origin/CSRF y SEC-01B; no está habilitada en el lanzador CRUD local |
| Recuperación semántica con modelo real | No acreditada en este entorno: faltan dependencias/modelo/perfil V2 y base semántica preparada independiente |
| Clasificación de tickets con artefacto entrenado | Implementación existente, pero no hay artefacto validado disponible para demostrar inferencia |
| RAG | Prototipo separado de main con respuestas fijas; 23 tests y evaluación simulada 9/9 aprobados. No es generación real ni está integrado al CRUD |

Para recuperación faltan sentence-transformers 5.1.2, transformers 4.57.1 y torch
2.14.0, y el modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
en revisión `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` (384 dimensiones). Se
requiere además un perfil V2 (`schemaVersion=2`) calibrado y ligado al corpus real
por corpusId/corpusRevision, sus documentos indexados y una base semántica testing
separada, con la configuración correspondiente. No se descargó ni calibró nada
improvisadamente. Ver [ML](../ml/README.md) y el [contrato semántico](contratos/recuperacion-semantica-v1.md).

Para clasificación falta `ml/artifacts/ticket_classifier_es/ticket_classifier.joblib`
con `artifact_manifest.json`, `metrics.json`, SHA256, procedencia de dataset,
model_version y criterios aprobados. El entorno de inferencia existente usa
scikit-learn 1.9.1, NumPy 2.3.4, joblib 1.6.0 y las versiones fijadas en
[requirements ML](../ml/requirements.txt). No cargar joblib desconocidos ni
reentrenar sin datos/criterios aprobados; no mostrar predicciones inventadas.

La verificación offline de RAG se realizó sobre una extracción de los archivos
versionados de main `ca1d572c35472af525e4a2d85bf38881265e5818`, sin importarlos a
esta rama. El reporte indica `executionMode=simulated`, proveedor simulador local
y respuestas fijas. No se llamó a Gemini ni se usó una clave real.

## Evidencia nueva del ensayo MVP10

Se ejecutaron 94 comprobaciones Edge para admin y agent, 14 checkpoints SQL,
dos cierres confirmados por SQL, cuatro sesiones obtenidas por login (la segunda
de cada rol se usa para probar revocación/inactividad) y catorce tickets finales.
Las cuentas de cada prueba son ficticias y se eliminan junto con su base.

La suite completa PostgreSQL terminó con 440 aprobadas, incluidas las dos
regresiones nuevas de logout. También aprobaron 1.021 unitarias backend, cuatro
TLS y 32 pruebas del protocolo de ingreso, TypeScript y ESLint. Alembic
upgrade/current/heads/check aprobó en las bases propias del arnés. No se cuentan
los resultados históricos de CI como nuevas pruebas locales.

El inicio/cierre manual se comprobó por separado, sin login: por eso su reporte
declara `browser_verified=false`. La evidencia de navegador real corresponde al
ensayo automático de 94 comprobaciones, no a ese smoke de arranque.

Los reportes/capturas quedan fuera de Git, en artifacts de esta copia y en el
directorio de evidencia MVP10 del repositorio original. Antes de las 23:59 del
jueves, repetir el comando automático, confirmar disponibilidad del testing y
las herramientas, preparar el recorrido y mantener las limitaciones explícitas.
La reconciliación y revisión formal de PR #52 requieren otra autorización/tarea;
no son necesarias para ejecutar esta copia local de demostración.
