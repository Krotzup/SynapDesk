# Proxy, SSR e ingreso local

Desde frontend, `npm run test:proxy` conserva las regresiones de main y agrega
los casos del BFF local y la capacidad SSR. Necesita OpenSSL en PATH. Genera
su propia CA, la confía sólo al proceso Node y elimina únicamente su temporal.
El backend HTTPS de esta suite es un servidor de prueba; no acredita SQL ni Edge.

Los hooks comunes permanecen en [tests/support](../support/); no se duplican
los hooks ni se restaura el runner antiguo de MVP07. Las pruebas de cookies de
#30 y búsqueda permanecen intactas. La composición local no sustituye el filtro.

El [driver CRUD](browser-crud.mjs) usa Microsoft Edge instalado, formularios reales,
Next, FastAPI TLS y checkpoints PostgreSQL independientes. Se ejecuta con el
[runner explícito](../../../backend/herramientas/ingreso_local/verificar.py),
no con `npm run test:proxy`. Ver [guía reproducible](../../../docs/guia-recorrido-local-mvp.md).
No instala navegadores, no fabrica sesiones y no usa mocks de las operaciones CRUD.

El [protocolo](../../../backend/herramientas/ingreso_local/protocolo.test.mjs)
se comprueba con `node --test herramientas/ingreso_local/protocolo.test.mjs`
desde backend. Sus casos no equivalen a una acreditación de entorno productivo.
