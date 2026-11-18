# Preparación de publicación MVP09

## Base y selección

La rama `funcionalidad/mvp09-crud-http-publicacion` parte de
`5a73f024d6a3ef2476120b18042592cc017bb539` (`origin/main`, PR #50 fusionado).
La fuente `funcionalidad/integracion-crud-http-mvp` queda intacta en
`cb41512667c04ba7ea63e481685f5bcec2a86a8c`, incluidos sus tres commits
`26ed7d4`, `c8088b4` y `cb41512` y la procedencia de los once commits MVP07.

Se compararon los treinta archivos del delta MVP09 con main actualizado. Los dos
ajustes de expectativas de rutas ya están integrados por #50 y se excluyen:
[test_adaptadores_tickets.py](../../backend/pruebas/test_adaptadores_tickets.py)
y [test_tickets.py](../../backend/pruebas/test_tickets.py). Sus comentarios nuevos
en main se conservan. Para los otros 28 archivos se comprobó que main mantenía el
blob de la base original o que el archivo aún no existía, antes de aplicar sólo
su delta. No se aplicaron commits completos ni se reescribió la rama fuente.

Se reutilizan los servicios de autenticación, sesiones, CSRF, roles, DTO, SQL de
tickets y paginación extrema de #39; también las cookies estrictas y transporte
de #30 y la recuperación semántica de #32. No se cambian sus implementaciones.
Se conserva el manifiesto histórico de [44 archivos](mvp09-procedencia.json).

## Independencia respecto de #47 y #48

Al preparar este candidato el 18-11-2026, ambos PR siguen abiertos, sin fusionar:

| PR | HEAD revisado | Solapamiento directo | Tratamiento |
|---|---|---|---|
| #47 | `0e4a6136827c2267caeac507c2182ba1f4af2628` | [listado](../../frontend/src/app/(dashboard)/tickets/page.tsx), [detalle](../../frontend/src/app/(dashboard)/tickets/[id]/page.tsx) | No importar su refactor con Suspense ni sus componentes nuevos. Conservar la UI actual y los fallbacks mínimos ya verificados de MVP09. |
| #48 | `969cf7d88028b7a1f02bf656fd7b79f18a3bd248` | [listado](../../frontend/src/app/(dashboard)/tickets/page.tsx) | No importar la desactivación global de filtros ni sus cambios de navegación. Mantener el aviso y rechazo explícito de filtros sólo en el ensayo local. |

Ni el cliente API ni los contratos compartidos figuran en los diffs de esos PR.
Los componentes de carga, métricas, filtros y enlaces de main se preservan salvo
los pequeños fallbacks del listado/detalle del delta MVP09. Esto evita copiar
trabajo abierto, pero no garantiza ausencia de conflictos futuros: si se integra
#47 o #48 primero, hay que reconciliar esos dos archivos y repetir sus pruebas.

## Composición y límites

El cambio conecta HTTP de autenticación y tickets a servicios existentes mediante
una fábrica de ensayo separada, un ingreso local acreditado y la integración
Next.js. Las herramientas reproducibles se mantienen bajo
[ingreso_local](../../backend/herramientas/ingreso_local/README.md); las
instrucciones están en la [guía de ensayo](../guia-recorrido-local-mvp.md).

El ingreso se habilita por código sólo para testing; faltando sus garantías se
cierra por defecto. No habilita rutas de autenticación/tickets en la fábrica
productiva habitual, ni configura ingreso productivo, Render o bootstrap
operativo. No añade filtros, PATCH ampliado ni clasificación ML.

## Validación del candidato

Resultados nuevos del 18-11-2026, ejecutados sobre esta copia:

| Comprobación | Resultado |
|---|---|
| Recolección pytest completa | 1.466 casos, sin colisiones |
| Runner unitarias backend | 1.021 aprobadas, cero omisiones |
| Comando del job búsqueda/backend `python -m pytest pruebas -q` | 1.025 aprobadas; 441 omisiones optativas (438 PostgreSQL y 3 semánticas) |
| Runner PostgreSQL completo | 438 aprobadas, cero omisiones; PostgreSQL 17.11/pgvector 0.8.6 |
| TLS real | 4 aprobadas |
| Alembic | upgrade/current/heads/check aprobados; head `0006_user_created` |
| Frontend unitarias/búsqueda | 60/15 aprobadas |
| Proxy/SSR | 87 aprobadas, incluidas las 4 de ingreso local |
| Protocolo de ingreso | 32 aprobadas |
| Regresiones ML/semánticas sin modelo | 88 aprobadas, 3 optativas omitidas |
| TypeScript/ESLint/build webpack y build predeterminado de CI | Aprobados |
| Microsoft Edge instalado 157.0.4341.60 | 74 comprobaciones aprobadas, admin y agent |

Edge realizó login real, CSRF, /me, creación, listado paginado, detalle, cambio
de estado y recarga con persistencia. Se verificaron 12 checkpoints SQL, dos
sesiones de login y 14 tickets finales; también página extrema y los rechazos
de seguridad. El supervisor verificó SEC-01B inválido por HTTPS. Se eliminaron
las bases y temporales propios y se detuvieron sus procesos. El runner general
de PostgreSQL, el de Alembic y el navegador usaron bases aleatorias independientes.

El primer intento del comando backend en sandbox encontró WinError 5 al
enumerar temporales de pytest; se repitió sin modificar pruebas, con permisos
para procesos locales y un `--basetemp` nuevo de esta copia. Aprobó con un aviso
de escritura de caché del entorno. La primera ejecución ML encontró una salida
Windows no UTF-8; la repetición con `PYTHONUTF8=1` y `PYTHONIOENCODING=utf-8`
aprobó. No se cambiaron tests, exclusiones ni configuración para estos casos.

No se ejecutaron los tres casos backend de búsqueda con perfil V2/bases
semánticas propias ni los tres casos optativos ML/modelo. Los módulos de
recuperación, su ruta, contratos, modelo y esquema no cambian. Las regresiones
sin modelo y el proxy de búsqueda sí se ejecutaron. Esto no acredita una
inferencia semántica real ni clasificación ML integrada al CRUD.

Los resultados históricos de MVP09 no se cuentan como evidencia nueva.
La publicación, CI remota y revisión formal siguen pendientes de autorización
posterior sobre el SHA exacto del candidato. Los reportes y capturas locales
quedan excluidos de Git; la descripción del PR identificará su ubicación.
Los controles de documentación/contratos y workflow aprobaron. El análisis de
secretos de los 29 archivos del diff no produjo hallazgos; `pip check` y
`git diff --check` aprobaron.
