# Contratos de integración

Esta carpeta contendrá los acuerdos versionados entre los componentes de SynapDesk.

Contratos previstos:

- frontend y backend;
- backend y modelo de Machine Learning;
- proveedor de embeddings;
- proveedor LLM.

Cada contrato deberá incluir datos de entrada, datos de salida, validaciones, errores esperados y al menos un ejemplo.

## Contratos disponibles

- [Contrato inicial entre frontend y backend](frontend-backend.md)
- [Contrato experimental de embeddings y recuperación](embeddings-recuperacion.md)
- [Contrato inicial entre backend y Machine Learning](backend-ml.md)
- [Contrato API de autenticación V1](autenticacion-v1.md)
- [Bootstrap administrativo V1](bootstrap-administrador-v1.md): P1–P10 y evento aprobados para implementación; verificación operativa del entorno pendiente.
- [Creación administrativa de usuarios V1](creacion-administrativa-usuarios-v1.md): P1–P15 y user_created aprobados; coordinador interno para admin/agent, sin rutas HTTP.
- [Adaptadores HTTP de autenticación D.1](autenticacion-http-adaptadores-v1.md): DRAFT, especificación interoperable y candidatos sin registro de rutas ni aprobación de pendientes.
- [Integración PR30/PR32](integracion-http-pr30-pr32-v1.md): requisitos candidatos de proxy, SSR, búsqueda, TLS e IP para revisión con Valentina y América.
- [Matriz de decisiones y plan D.2](auth07d2-matriz-decisiones-y-plan.md): DRAFT de preparación; aprobaciones previas, propuestas y evidencia pendiente separadas, sin habilitación de rutas.
