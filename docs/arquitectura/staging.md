# Estrategia inicial de staging

## Propósito

Staging será el entorno compartido donde el equipo validará la integración de SynapDesk antes de demostraciones y entregas. No se considera un entorno de producción ni tendrá garantías empresariales de disponibilidad.

## Arquitectura propuesta

| Componente | Servicio propuesto | Responsabilidad |
| --- | --- | --- |
| Frontend | Vercel | Ejecutar la aplicación Next.js y publicar la interfaz web. |
| Backend | Render | Ejecutar el monolito modular FastAPI. |
| Base de datos | Supabase | Proporcionar PostgreSQL con pgvector. |
| Archivos | Supabase Storage | Conservar documentos fuera del sistema de archivos efímero del backend. |
| LLM | Por seleccionar | Generar recomendaciones a partir del contexto recuperado. |
| Código y automatización | GitHub | Mantener el código, las revisiones y las comprobaciones automáticas. |

## Flujo de despliegue

1. Crear una rama de trabajo desde `main`.
2. Implementar y verificar el cambio localmente.
3. Abrir un pull request.
4. Obtener la revisión correspondiente.
5. Ejecutar pruebas automáticas cuando estén disponibles.
6. Integrar el cambio en `main`.
7. Desplegar o actualizar staging.
8. Ejecutar una prueba rápida del flujo afectado.

La rama `main` será la fuente del entorno de staging. No se mantendrá inicialmente una rama permanente llamada `staging`.

## Configuración y secretos

Los valores sensibles se configurarán directamente en cada proveedor y nunca se almacenarán en Git.

Variables previstas para el backend:

```text
APP_ENV
DEBUG
LOG_LEVEL
DATABASE_URL
FRONTEND_ORIGIN
AUTH_SECRET_KEY
STORAGE_PROVIDER
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_BUCKET
EMBEDDING_PROVIDER
EMBEDDING_MODEL
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
LLM_TIMEOUT_SECONDS
LLM_MAX_OUTPUT_TOKENS
```

Las variables se agregarán a `.env.example` únicamente cuando el código comience a utilizarlas.

El frontend nunca recibirá:

- la URL privada de conexión a PostgreSQL;
- `AUTH_SECRET_KEY`;
- credenciales administrativas de almacenamiento;
- claves del proveedor LLM;
- `SUPABASE_SERVICE_ROLE_KEY`.

## Persistencia documental

El backend de staging no conservará documentos en su sistema de archivos local. Los documentos se almacenarán en un bucket privado y PostgreSQL conservará sus metadatos.

Reglas iniciales:

- aceptar inicialmente PDF y TXT;
- limitar cada archivo a 10 MB;
- generar nombres internos mediante UUID;
- validar extensión, MIME y tamaño;
- acceder a los archivos a través del backend;
- coordinar la eliminación del archivo y sus metadatos;
- utilizar solamente documentación autorizada.

## Migraciones

Cuando Alembic sea incorporado, todo cambio de esquema incluirá una migración versionada.

Flujo inicial:

1. probar la migración contra la base de testing;
2. revisar la migración dentro del pull request;
3. ejecutar `alembic upgrade head` de manera controlada contra staging;
4. comprobar el esquema resultante;
5. desplegar el backend compatible.

Las migraciones no se ejecutarán automáticamente al iniciar cada instancia mientras no exista un mecanismo seguro que evite ejecuciones concurrentes.

## Política de datos

Staging puede contener:

- usuarios ficticios;
- tickets sintéticos o anonimizados;
- documentación autorizada;
- direcciones de correo no reales;
- claves creadas exclusivamente para SynapDesk.

Staging no debe contener:

- contraseñas personales;
- tickets reales sin anonimización;
- documentos confidenciales;
- datos personales innecesarios;
- credenciales reutilizadas desde otros proyectos.

## Limitaciones aceptadas

- El backend gratuito puede suspenderse después de un periodo sin tráfico.
- La primera solicitud posterior a la suspensión puede tener latencia elevada.
- La base gratuita puede pausarse por inactividad.
- El almacenamiento y la base tienen capacidad limitada.
- No existe un acuerdo de nivel de servicio.
- Los planes y límites de los proveedores pueden cambiar.

Antes de una demostración se deberá comprobar con anticipación:

- frontend accesible;
- backend activo;
- health check correcto;
- conexión con PostgreSQL;
- acceso a documentos;
- disponibilidad del proveedor LLM;
- ejecución del flujo crítico.

## Alternativa de contingencia

Si la combinación gratuita resulta inestable o compleja, se evaluará un proveedor de pago económico que ejecute backend y PostgreSQL, conservando Vercel para frontend si continúa siendo adecuado.

No se contratará ningún servicio antes de medir los requisitos reales del backend, la base, el almacenamiento y las integraciones de inteligencia artificial.

## Criterios para aprobar la arquitectura definitiva

- El backend puede construirse y ejecutarse mediante Docker.
- PostgreSQL administrado admite pgvector.
- Existe almacenamiento persistente para documentos.
- Los secretos permanecen fuera del repositorio.
- El equipo puede consultar logs y estado de salud.
- El costo estimado es aceptable para el semestre.
- Las condiciones de uso permiten un proyecto académico.
- Existe un procedimiento de recuperación o recreación del entorno.

## Referencias de proveedores

- [Vercel Hobby](https://vercel.com/docs/plans/hobby)
- [Render Free](https://render.com/docs/free)
- [Supabase Pricing](https://supabase.com/pricing)
- [pgvector en Supabase](https://supabase.com/docs/guides/database/extensions/pgvector)

Las condiciones y precios deberán verificarse nuevamente antes del despliegue.
