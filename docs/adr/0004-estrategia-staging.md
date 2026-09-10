# ADR-0004: Proponer una arquitectura inicial para staging

* Estado: Aprobado
* Fecha: 09-09-2026
* Fecha aprobación: 10-09-2026
* Responsables: equipo SynapDesk

## Contexto

SynapDesk necesita un entorno compartido y de bajo costo para validar la integración y realizar demostraciones. El backend, la base de datos y los documentos requieren persistencia y capacidades diferentes.

## Alternativas consideradas

1. Ejecutar frontend, backend y base de datos en un único proveedor de pago.
2. Utilizar Vercel para frontend, Render para backend y Supabase para PostgreSQL, pgvector y archivos.
3. Mantener staging en el computador de un integrante.
4. Desplegar desde el inicio en infraestructura cloud empresarial.

## Decisión propuesta

Evaluar como primera alternativa:

* Vercel para el frontend Next.js;
* Render para el backend FastAPI;
* Supabase para PostgreSQL, pgvector y almacenamiento documental;
* GitHub como origen del despliegue y control de cambios.

Esta decisión no autoriza todavía la creación de servicios ni el almacenamiento de secretos. Deberá validarse cuando exista un backend mínimo desplegable.

## Razones

* Permite comenzar con un costo reducido.
* Cada servicio se ajusta al tipo de componente que ejecuta.
* Supabase proporciona PostgreSQL, pgvector y almacenamiento persistente.
* Render permite desplegar un backend Python.
* Vercel se integra directamente con Next.js.
* Evita mantener infraestructura propia para la demostración.

## Consecuencias

### Positivas

* Staging puede comenzar sin contratar infraestructura empresarial.
* Los documentos no dependen del sistema de archivos efímero del backend.
* Frontend, backend y persistencia pueden evolucionar independientemente.

### Negativas o riesgos

* El sistema queda distribuido entre varios proveedores.
* Los servicios gratuitos pueden suspenderse por inactividad.
* La primera solicitud puede presentar latencia elevada.
* Los planes gratuitos pueden cambiar durante el semestre.
* La observación de errores queda repartida entre distintos paneles.

## Medidas de mitigación

* Mantener configuración mediante variables de entorno.
* No utilizar funcionalidades propietarias sin una justificación clara.
* Preparar una lista de comprobación previa a las demostraciones.
* Mantener migraciones reproducibles.
* Conservar una alternativa de despliegue de bajo costo.
* Revisar condiciones, precios y límites antes de crear los servicios.

## Condiciones para aceptar la decisión

* Backend mínimo contenerizado y medido.
* Compatibilidad comprobada con PostgreSQL y pgvector administrados.
* Estrategia de archivos validada.
* Costos y términos aceptados por el equipo.
* Responsables de las cuentas y secretos definidos.

## Condiciones para revisar la decisión

Se evaluará otra alternativa si el costo, los límites, la latencia, la suspensión por inactividad o la complejidad operacional dificultan la demostración del producto.

