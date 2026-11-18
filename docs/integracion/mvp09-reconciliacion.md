# Reconciliación selectiva del CRUD sobre main — MVP09

Este documento conserva la reconciliación y los resultados históricos de la rama
MVP09 original. La base, selección y validación del candidato de publicación se
registran por separado en [Preparación de publicación](mvp09-publicacion.md).

Base: 3580ac4bfa90ff4ad982e9aee656cc507ca41312. Rama local:
funcionalidad/integracion-crud-http-mvp. Fuente histórica preservada:
059f31bbdbd9d4308a4bcbec249f1b12b9a390e3 y sus once commits MVP07.

Se localizó y leyó el informe original SYNAPDESK-SYNC-MAIN-AND-PREPARE-CRUD-INTEGRATION
y sus anexos plan-por-archivo, file-integration-plan, correspondencias y comprobaciones
de parches, conservados en artifacts/sync-main-crud-20261118 de la copia original.
El [manifiesto](mvp09-procedencia.json) conserva los 44 registros, los identificadores
de blob de fuente/base, los commits fuente, las acciones originales y la huella SHA256
del plan. Los informes originales se preservan como evidencia local, sin versionar
archivos privados ni reutilizar sus resultados como validación de MVP09.

## Selección y correspondencia

14 archivos corresponden a funcionalidad ya integrada, 3 necesitan incorporación,
14 adaptación, 8 son herramientas de testing y 5 se excluyen. No se aplicaron los
once commits completos. Se portaron los deltas acotados de composición y las piezas
ausentes; los archivos divergentes se adaptaron por bloques sobre main.

La tabla completa sigue abajo. En los hooks trasladados, el enlace apunta al
destino actual de main. Los cinco archivos excluidos permanecen en la fuente histórica.

## Adaptaciones verificables

- Autenticación: [AdaptadorAuth](../../backend/app/api/adaptadores_auth.py) admite
  un proveedor de procedencia sólo por código y testing. Los servicios existentes
  de contraseña, CSRF, sesiones, roles y auditoría se reutilizan. La fábrica habitual
  sigue cerrada; no se configura un ingreso productivo.
- HTTP local: [composición](../../backend/herramientas/ingreso_local/aplicacion.py)
  conecta los cinco adaptadores de tickets actuales. No limita page a nueve dígitos;
  usa el repositorio corregido de #39. El resumen existente sirve también en la ruta
  de métricas esperada por la UI. Rechaza filtros no soportados y parámetros duplicados.
- Transporte: [canal](../../frontend/src/lib/backend-proxy.ts) añade el sello únicamente
  si el lanzador privado instaló la capacidad. Conserva SEC-01B, TLS, plazos, límites,
  readLimited y ambas modalidades del filtro de cookies de main. No importa dcb7b44.
  [SSR](../../frontend/src/lib/transport/server.ts) marca sus lecturas para delegación
  acotada por método, recurso y navegación; se conserva la política original de cookies.
- Interfaz: conserva las páginas y TicketStatusControl de main, evita duplicar
  TicketReading y desacopla errores de recomendaciones/conteos del CRUD. En el ensayo
  anuncia filtros pendientes y rechaza explícitamente una URL con filtros.
  [LoginForm](../../frontend/src/components/auth/LoginForm.tsx) usa POST y espera
  hidratación antes de habilitar envío para impedir contraseñas en URL.
- Cliente API: conserva readResponse, estado HTTP, SESSION_CHANGED y la guarda de
  generación de sesión; sólo selecciona el BFF CSRF local cuando se solicita el ensayo.
- Pruebas fuera del plan: dos expectativas de rutas en [test_tickets](../../backend/pruebas/test_tickets.py)
  y [test_adaptadores_tickets](../../backend/pruebas/test_adaptadores_tickets.py) aún
  omitían /search, ya integrado por #32. Se agregó esa ruta esperada sin quitar casos.
  [test_ingreso_local_http](../../backend/pruebas/integracion/test_ingreso_local_http.py)
  añade regresiones de las rutas compuestas con SQL real, página enorme y validación.

No se alteran DTO, modelos, migraciones, permisos admin/agent, SQL de tickets,
servicios internos ni autenticación operativa. Filtros ampliados, PATCH de otros
campos, administración y clasificación ML quedan fuera. Las ramas y copias de
compañeras no se modifican; no hay publicación ni merge.

## Reproducción y límites

La [guía](../guia-recorrido-local-mvp.md) documenta las herramientas, destino testing,
fixture autorizada y comandos. Los reportes y capturas se generan bajo artifacts de
esta copia y quedan fuera de Git. Cada ejecución crea base aleatoria, claves y
certificados propios; cierra sus procesos y elimina sus recursos al terminar.

La persistencia demostrada comprende login, navegación y recargas con conexiones
SQL independientes durante el ensayo. No acredita Render, bootstrap operativo,
cookies production, múltiples workers ni durabilidad después de borrar la base.
Publicar la rama requerirá autorización, PR, CI remota y revisión de la composición.
La clasificación ML real necesita después un incremento separado con modelo/versionado,
inferencias y persistencia/contratos de predicción acordados; #32 es recuperación
semántica y no acredita esa clasificación.

## Clasificación de los 44 archivos

Validación local del 18-11-2026: 1.466 casos recolectados sin colisiones, 1.021
unitarias backend, 438 PostgreSQL (incluyen 8 nuevas de rutas locales), 4 TLS,
60 unitarias frontend, 15 de búsqueda y 87 proxy/SSR (83 existentes más 4 nuevas,
ejecutadas por separado). Protocolo de ingreso: 32 casos. Sin fallos ni omisiones
en esos runners. Los 3 casos semánticos con perfil V2 siguen fuera del runner PG
general existente; no se acreditan como ejecutados en MVP09.

Edge instalado 157.0.4341.60: 74 comprobaciones para admin/agent, 12 checkpoints SQL,
dos sesiones obtenidas por login y 14 tickets finales (12 fixtures y 2 creados desde
formularios). PostgreSQL 17.11 con pgvector 0.8.6. SEC-01B inválido rechazado por
HTTPS real. Bases, procesos y temporales propios eliminados al finalizar.
También aprobaron TypeScript, ESLint, build webpack, Alembic upgrade/current/heads/check,
contratos/workflow, pip check, controles de secretos y git diff --check.
Son resultados locales del candidato; no equivalen a CI remota ni revisión formal.

| Archivo del plan original | Clasificación MVP09 |
|---|---|
| [.env.example](../../.env.example) | Ya integrado en main |
| [backend/app/api/adaptadores_auth.py](../../backend/app/api/adaptadores_auth.py) | Necesita adaptación |
| [backend/herramientas/ingreso_local/README.md](../../backend/herramientas/ingreso_local/README.md) | Necesita adaptación |
| [backend/herramientas/ingreso_local/__init__.py](../../backend/herramientas/ingreso_local/__init__.py) | Necesita incorporación |
| [backend/herramientas/ingreso_local/aplicacion.py](../../backend/herramientas/ingreso_local/aplicacion.py) | Necesita adaptación |
| [backend/herramientas/ingreso_local/demo.py](../../backend/herramientas/ingreso_local/demo.py) | Herramienta de testing |
| [backend/herramientas/ingreso_local/evidencia.py](../../backend/herramientas/ingreso_local/evidencia.py) | Necesita incorporación |
| [backend/herramientas/ingreso_local/protocolo.mjs](../../backend/herramientas/ingreso_local/protocolo.mjs) | Necesita adaptación |
| [backend/herramientas/ingreso_local/protocolo.test.mjs](../../backend/herramientas/ingreso_local/protocolo.test.mjs) | Herramienta de testing |
| [backend/herramientas/ingreso_local/servidor_next.mjs](../../backend/herramientas/ingreso_local/servidor_next.mjs) | Herramienta de testing |
| [backend/herramientas/ingreso_local/verificar.py](../../backend/herramientas/ingreso_local/verificar.py) | Herramienta de testing |
| [backend/pruebas/test_ingreso_local.py](../../backend/pruebas/test_ingreso_local.py) | Herramienta de testing |
| [docs/arquitectura/estructura-frontend.md](../../docs/arquitectura/estructura-frontend.md) | Ya integrado en main |
| [docs/contratos/comunicacion-interna-segura-v1.md](../../docs/contratos/comunicacion-interna-segura-v1.md) | Necesita adaptación |
| [docs/contratos/frontend-backend.md](../../docs/contratos/frontend-backend.md) | Necesita adaptación |
| [docs/contratos/ingreso-local-mvp04.md](../../docs/contratos/ingreso-local-mvp04.md) | Necesita adaptación |
| [docs/guia-recorrido-local-mvp.md](../../docs/guia-recorrido-local-mvp.md) | Necesita adaptación |
| `docs/integracion/mvp07-consolidacion-y-publicacion.md` (fuente histórica excluida) | Debe excluirse |
| `docs/integracion/mvp07-procedencia.json` (fuente histórica excluida) | Debe excluirse |
| [frontend/.env.example](../../frontend/.env.example) | Ya integrado en main |
| [frontend/README.md](../../frontend/README.md) | Ya integrado en main |
| [frontend/package.json](../../frontend/package.json) | Ya integrado en main |
| [frontend/src/app/(dashboard)/inicio/page.tsx](../../frontend/src/app/(dashboard)/inicio/page.tsx) | Ya integrado en main |
| [frontend/src/app/(dashboard)/layout.tsx](../../frontend/src/app/(dashboard)/layout.tsx) | Ya integrado en main |
| [frontend/src/app/(dashboard)/tickets/[id]/page.tsx](../../frontend/src/app/(dashboard)/tickets/[id]/page.tsx) | Necesita adaptación |
| [frontend/src/app/(dashboard)/tickets/page.tsx](../../frontend/src/app/(dashboard)/tickets/page.tsx) | Necesita adaptación |
| [frontend/src/app/api/local/csrf/route.ts](../../frontend/src/app/api/local/csrf/route.ts) | Necesita incorporación |
| [frontend/src/app/api/v1/[...path]/route.ts](../../frontend/src/app/api/v1/[...path]/route.ts) | Ya integrado en main |
| [frontend/src/components/auth/LoginForm.tsx](../../frontend/src/components/auth/LoginForm.tsx) | Necesita adaptación |
| `frontend/src/components/tickets/TicketReading.tsx` (fuente histórica excluida) | Debe excluirse |
| [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) | Necesita adaptación |
| [frontend/src/lib/backend-proxy.ts](../../frontend/src/lib/backend-proxy.ts) | Necesita adaptación |
| [frontend/src/lib/transport/client.ts](../../frontend/src/lib/transport/client.ts) | Ya integrado en main |
| [frontend/src/lib/transport/server.ts](../../frontend/src/lib/transport/server.ts) | Necesita adaptación |
| [frontend/tests/proxy/README.md](../../frontend/tests/proxy/README.md) | Herramienta de testing |
| `frontend/tests/proxy/browser-critical.mjs` (fuente histórica excluida) | Debe excluirse |
| [frontend/tests/proxy/browser-crud.mjs](../../frontend/tests/proxy/browser-crud.mjs) | Herramienta de testing |
| `frontend/tests/proxy/cookie-cases.mjs` (fuente histórica excluida) | Debe excluirse |
| [frontend/tests/proxy/hooks.mjs](../../frontend/tests/support/hooks.mjs) | Ya integrado en main |
| [frontend/tests/proxy/next-headers-stub.mjs](../../frontend/tests/support/next-headers-stub.mjs) | Ya integrado en main |
| [frontend/tests/proxy/proxy.test.mjs](../../frontend/tests/proxy/proxy.test.mjs) | Herramienta de testing |
| [frontend/tests/proxy/register.mjs](../../frontend/tests/support/register.mjs) | Ya integrado en main |
| [frontend/tests/proxy/run.mjs](../../frontend/tests/proxy/run.mjs) | Ya integrado en main |
| [frontend/tests/proxy/server-only-stub.mjs](../../frontend/tests/support/server-only-stub.mjs) | Ya integrado en main |
