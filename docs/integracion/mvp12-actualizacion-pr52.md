# MVP12 — actualización no destructiva de PR #52

Rama de preparación `correccion/mvp12-actualizacion-pr52`, creada desde el HEAD
remoto `ba2422fadff2cab93ab842a6ecdd3990f1434471`, sin sustituir la rama publicada.
Main comprobado: `ca1d572c35472af525e4a2d85bf38881265e5818`. No recibió nuevos
commits desde MVP11. Los PR #47/#48/#49 ya están fusionados.

## Historia y decisiones

El merge normal `4302efa92e98eade122728faccba91a90e88e362` tiene como primer padre
el HEAD original de #52 y como segundo padre main actualizado. Conserva los cuatro
commits publicados, sin rebase, reemplazo de rama ni reescritura. El merge sólo
ocurre en la copia de preparación; no se fusiona nada hacia main.

Se inspeccionaron las versiones original, main y MVP11 de las dos páginas en
conflicto. En [listado](../../frontend/src/app/(dashboard)/tickets/page.tsx) se
conservan TicketListSummary/Suspense y TicketFilters deshabilitado de main;
se retiran el Promise.all y el aviso condicionado al ingreso local obsoletos.
En [detalle](../../frontend/src/app/(dashboard)/tickets/[id]/page.tsx) se conserva
TicketRecommendations/Suspense, retirando el Promise.all y el mensaje duplicado
de recomendaciones. Ambas páginas quedan idénticas a main y MVP11. Las demás
mejoras de frontend entran con su historia original mediante el merge.

Después se incorpora sólo el delta revisado de MVP11: ruta logout de la fábrica
testing y admisión POST en el lanzador, regresiones PostgreSQL, checkpoints SQL,
driver Edge admin/agent y documentación. No se duplican endpoints ni se modifica
adicionalmente el cliente API o transporte. La actualización de procedencia en
el supervisor identifica este ensayo MVP12, sin alterar su comportamiento.

Los servicios de autenticación y tickets, DTO, cookies estrictas, SQL/paginación
extrema, migraciones, búsqueda semántica y RAG permanecen como main. APP_ENV=testing,
TLS/CA, SEC-01B, evidencia de socket, firma/antirreplay, Origin, CSRF, sesiones y
autorización admin/agent siguen siendo obligatorios. Las cuentas ficticias se
provisionan únicamente en la base aleatoria propia; no acreditan bootstrap operativo.

## Inicio y cierre reproducibles

Usar las herramientas existentes y las dependencias del lockfile: Python 3.12,
Node, OpenSSL, Edge instalado, playwright-core y PostgreSQL 17/pgvector 0.8.6
aislado. En este equipo, desde PowerShell:

```powershell
$raizDemo = 'C:/Users/Felipe/Desktop/SynapDesk'
$copiaDemo = Join-Path $raizDemo 'artifacts/mvp12-pr52-update-20261118'
$pythonDemo = Join-Path $raizDemo 'artifacts/repair-main-ci-worktree-20261118/backend/.venv/Scripts/python.exe'
$privadoDemo = Join-Path $raizDemo '.env'
$playwrightDemo = Join-Path $raizDemo 'artifacts/mvp09-browser-tools/node_modules/playwright-core'
Set-Location (Join-Path $copiaDemo 'backend')
& $pythonDemo -B -m herramientas.ingreso_local.verificar --modo navegador --env-file $privadoDemo --playwright-module $playwrightDemo
```

La ruta privada se lee en memoria, sin copiarla ni mostrarla. El verificador
crea otra base propia, obtiene sesiones mediante login real y genera evidencia
saneada en un directorio nuevo de artifacts. No usa respuestas simuladas del CRUD.

Para presentar manualmente se usa el mismo lanzador existente:

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

Mantener la consola abierta. Consultar las cuentas efímeras sólo localmente,
sin incluirlas en grabaciones. Admin: login, /me, creación, listado, detalle,
estado, recarga y logout. Después repetir como agent. El ensayo automático
comprueba inserción/persistencia y revocación mediante conexiones SQL independientes.

En modo manual pulsar Enter en la consola del lanzador y esperar database_deleted,
temporary_deleted, next_stopped y fastapi_stopped en true. El verificador
automático se cierra solo. Nunca cerrar contenedores o procesos ajenos.

No se habilitan filtros o PATCH ampliado. Métricas y recomendaciones opcionales
no bloquean el CRUD. No se acredita despliegue Render, HTTPS público, cookies
Secure públicas, clasificación con artefactos entrenados ni generación real RAG.
La búsqueda semántica se conserva, pero su API no se habilita en este lanzador CRUD.

## Publicación posterior

Validación nueva ejecutada el 18-11-2026 sobre esta copia, sin reutilizar MVP11:

| Control | Resultado |
|---|---|
| Unitarias backend | 1.021 aprobadas, sin omisiones |
| PostgreSQL real | 440 aprobadas, sin omisiones; 17.11 y pgvector 0.8.6 |
| Alembic | upgrade/current/heads/check correctos, head 0006_user_created |
| TLS | 4 aprobadas |
| Recolección pytest | 1.468 pruebas, sin colisiones |
| Búsqueda/backend | 1.025 aprobadas, 443 omitidas por condiciones existentes; PostgreSQL se ejecutó además en su runner dedicado |
| Frontend unitarias / búsqueda | 63 / 15 aprobadas |
| Proxy/SSR / protocolo local | 87 / 32 aprobadas |
| TypeScript / ESLint / build | Aprobados |
| Regresiones ML/RAG sin modelo | 111 aprobadas y 3 omitidas; no acredita inferencia real |
| Edge real | 94 comprobaciones; admin → CRUD → logout → agent → CRUD → logout |
| PostgreSQL durante Edge | 14 checkpoints; dos logout con sesión revocada y cuatro sesiones nacidas de login real |
| Contratos / workflow / secretos / dependencias / diff | Aprobados |

Las suites se solapan y sus cantidades no se suman. Se verificaron 24 hashes de
fuentes ejecutadas, trece archivos recientes de frontend idénticos a main y
servicios/DTO/migraciones/búsqueda intactos. Los rechazos de seguridad conservaron
las filas sin cambios. Next/FastAPI, bases y temporales propios se cerraron y
eliminaron correctamente; no se intervinieron recursos ajenos. Los reportes
saneados quedan en artifacts del candidato y en el informe local de esta tarea.

El destino futuro es la rama remota existente de #52, mediante push normal desde
la rama de preparación después de reconfirmar HEAD remoto y recibir autorización
expresa sobre el SHA exacto validado. No publicar la rama MVP11 en su lugar.
Mantener discusión y revisores de #52, actualizar su descripción con las nuevas
evidencias y esperar CI sobre el candidato actualizado. No reutilizar los checks
históricos como aprobación de MVP12. La revisión formal y el merge requieren
sus autorizaciones correspondientes. Esta preparación no hace push ni despliegue.
