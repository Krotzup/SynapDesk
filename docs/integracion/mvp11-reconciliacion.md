# Reconciliación MVP11 de PR #52 y logout

> Registro histórico. La incorporación no destructiva autorizada posteriormente
> se documenta en [MVP12](mvp12-actualizacion-pr52.md); sus resultados se validan
> por separado sobre la historia real de PR #52.

Base: main `ca1d572c35472af525e4a2d85bf38881265e5818`, con #47, #48 y #49
fusionados. PR #52 sigue abierto en `ba2422fadff2cab93ab842a6ecdd3990f1434471`
y GitHub informa conflictos. Fuente logout: `c81367aae9a7213581afb02f69976e91ba39a5a0`.
Se prepara `correccion/mvp11-reconciliar-crud-logout` desde main; no se modifica
ninguna rama original ni se ejecutan merge, rebase o publicación.

## Selección por correspondencia

Se compararon los 30 archivos del delta acumulado MVP10 frente a su base
`5a73f024d6a3ef2476120b18042592cc017bb539`. Para 28 rutas, main conserva el
blob de esa base o la ruta sigue ausente: se incorporan selectivamente. Las dos
páginas compartidas se excluyen del parche, conservando íntegramente main.
No se aplicaron commits completos ni se eligió un lado de un conflicto sin revisión.

| Archivo o grupo | Decisión y motivo |
|---|---|
| [Listado](../../frontend/src/app/(dashboard)/tickets/page.tsx) | Main intacto: consulta principal y métricas opcionales separadas mediante Suspense (#47). |
| [Detalle](../../frontend/src/app/(dashboard)/tickets/[id]/page.tsx) | Main intacto: detalle independiente de recomendaciones opcionales (#47). |
| [TicketListSummary](../../frontend/src/components/tickets/TicketListSummary.tsx) | Main intacto: errores opcionales no impiden listado. |
| [TicketRecommendations](../../frontend/src/components/recommendations/TicketRecommendations.tsx) | Main intacto: error saneado y carga opcional. |
| [TicketFilters](../../frontend/src/components/tickets/TicketFilters.tsx) | Main intacto: controles deshabilitados y aviso vigente (#48). |
| [Filtros](../../frontend/src/lib/ticket-filters.ts) y [regresión](../../frontend/tests/unit/ticket-filters.test.mjs) | Main intacto: sólo paginación soportada; no reintroducir filtros antiguos. |
| [Header](../../frontend/src/components/layout/Header.tsx), [Sidebar](../../frontend/src/components/layout/SidebarStatusSummary.tsx), [HomeSummary](../../frontend/src/components/home/HomeSummary.tsx), [MetricsSummary](../../frontend/src/components/metrics/MetricsSummary.tsx) | Main intacto: navegación y búsqueda deshabilitada actuales. |
| [Admin](../../frontend/src/app/(dashboard)/admin/page.tsx) y [arquitectura](../arquitectura/estructura-frontend.md) | Main intacto: placeholder/documentación de #49. |
| [Adaptador auth](../../backend/app/api/adaptadores_auth.py) | Incorporar proveedor opcional de procedencia exclusivamente testing; reutilizar los servicios existentes. |
| [Composición local](../../backend/herramientas/ingreso_local/aplicacion.py) y [servidor Next](../../backend/herramientas/ingreso_local/servidor_next.mjs) | Incorporar HTTP/CRUD y logout MVP10, sin habilitar fábrica productiva. |
| [Cliente API](../../frontend/src/lib/api.ts), [proxy](../../frontend/src/lib/backend-proxy.ts), [SSR](../../frontend/src/lib/transport/server.ts), [login](../../frontend/src/components/auth/LoginForm.tsx) | Incorporar conexión faltante manteniendo las políticas estrictas de #30. No reemplazar DTO o servicios. |
| [Driver Edge](../../frontend/tests/proxy/browser-crud.mjs) | Adaptar sólo expectativas: aviso y controles deshabilitados actuales; error opcional de recomendaciones vigente. Mantener CRUD, SQL y logout real. |
| [Supervisor](../../backend/herramientas/ingreso_local/demo.py) | Actualizar procedencia del candidato; conservar cuentas, base y limpieza exclusivas. |
| Contratos, regresiones y guías restantes | Incorporar pruebas y procedencia; marcar MVP09/MVP10 históricos y aportar guía vigente. |

Los servicios de tickets, SQL/paginación extrema (#39), modelos, migraciones,
DTO públicos, rutas de búsqueda y módulos RAG permanecen como main. La corrección
de expectativas de rutas de #50 permanece intacta. No se copian archivos privados.

## Validación

Los resultados nuevos y los SHA finales se registran en el informe saneado de
esta tarea. Los números de las guías históricas no se presentan como resultados
del candidato actual. El ensayo vigente está en la [guía MVP11](../guia-ensayo-reconciliado-mvp11.md).

Validación ejecutada el 18-11-2026 sobre este candidato:

| Control | Resultado nuevo |
|---|---|
| Unitarias backend | 1.021 aprobadas |
| PostgreSQL real aislado | 440 aprobadas; PostgreSQL 17.11, pgvector 0.8.6 |
| Alembic | upgrade, current, heads y check correctos; head 0006_user_created |
| TLS | 4 aprobadas |
| Recolección pytest | 1.468 pruebas, sin colisiones |
| Búsqueda/backend, comando completo | 1.025 aprobadas, 443 omitidas por sus condiciones existentes; PostgreSQL se ejecutó además en su runner dedicado |
| Frontend unitarias / búsqueda | 63 / 15 aprobadas |
| Proxy y SSR / protocolo de ingreso | 87 / 32 aprobadas |
| ML y RAG existentes | 114 ejecutadas: 111 aprobadas y 3 omitidas; no acredita modelos reales |
| TypeScript, ESLint y build | Aprobados |
| Edge instalado | 94 comprobaciones aprobadas; admin primero y luego agent |
| SQL del navegador | 14 checkpoints, inserción/estado/recarga y dos logout con sesión revocada; cuatro sesiones nacidas de login real |

Las suites se solapan: no sumar sus cantidades como pruebas únicas. La base del
ensayo y la del runner PostgreSQL fueron eliminadas al terminar; Next/FastAPI y
los archivos temporales propios también se cerraron/eliminaron correctamente.
No se alteraron contenedores existentes ni se ejecutó CI remota para esta rama.

## Alternativas de publicación

Se recomienda A: mantener PR #52 y sus revisiones, integrando main con un merge
normal autorizado en su rama y commits adicionales de reconciliación/logout.
Esta rama preparatoria nace de main y no desciende del HEAD de #52: no se puede
publicar directamente encima de #52 sin reescribirlo. Una tarea posterior debe
resolver por las decisiones anteriores, verificar igualdad del árbol esperado,
repetir las pruebas pertinentes y publicar con push normal. No se ejecuta aquí.

B, PR sustitutivo desde esta rama, ofrece un diff limpio contra main pero dispersa
la revisión y duplica el trabajo abierto. Reservarlo para una restricción técnica
o política que impida A; no cerrar #52 sin acuerdo. Ambas opciones requieren nueva
autorización de publicación, CI remota del candidato actualizado y revisión formal.
