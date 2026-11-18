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
- [Recuperación semántica V1 y estados de búsqueda](recuperacion-semantica-v1.md)
- [Contrato inicial entre backend y Machine Learning](backend-ml.md)
- [Contrato API de autenticación V1](autenticacion-v1.md)
- [Bootstrap administrativo V1](bootstrap-administrador-v1.md): P1–P10 y evento aprobados para implementación; verificación operativa del entorno pendiente.
- [Creación administrativa de usuarios V1](creacion-administrativa-usuarios-v1.md): P1–P15 y user_created aprobados; coordinador interno para admin/agent, sin rutas HTTP.
- [Adaptadores HTTP de autenticación D.1](autenticacion-http-adaptadores-v1.md): formalización D.3 en alcance P1–P10; endpoints, precedencia y cookies/errores, con detalles adicionales pendientes y rutas cerradas.
- [Integración PR30/PR32](integracion-http-pr30-pr32-v1.md): responsabilidades aprobadas y especificaciones ejecutables para Valentina/América sobre HEAD fijados; pendientes operativos identificados.
- [Matriz de decisiones y plan D.2](auth07d2-matriz-decisiones-y-plan.md): antecedente histórico D.1, sustituido en decisiones por D.3; preserva la revisión anterior.

- [Compatibilidad, decisiones, aceptación y plan D.3](auth07d3-compatibilidad-y-plan-integracion.md): P1–P10 aprobadas, brecha logout inactivo, cuotas/presupuestos sin cifras inventadas, matriz IP Render y secuencia por incrementos.
- [Comunicación interna segura SEC-01B](comunicacion-interna-segura-v1.md): mecanismo aprobado; operación/infraestructura todavía por acreditar.
