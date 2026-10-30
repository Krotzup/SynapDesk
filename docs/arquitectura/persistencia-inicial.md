# Persistencia relacional inicial

## Estado y alcance

Diseño inicial implementado para revisión mediante PR. La revisión `0001_usuarios_tickets` crea las tablas `usuarios` y `tickets` en PostgreSQL. No implementa rutas de usuarios o tickets, autenticación, predicciones ni persistencia vectorial.

Los campos internos se nombran en español y `snake_case`. Las futuras respuestas de API conservarán los nombres `camelCase` del contrato; los modelos ORM no se serializarán directamente como respuestas.

## Usuarios

| Columna PostgreSQL | Campo del dominio/API | Obligatorio | Comportamiento |
| --- | --- | --- | --- |
| `id` | `id` | Sí | UUID generado por PostgreSQL |
| `nombre` | `name` | Sí | Texto con contenido |
| `correo` | `email` | Sí | Único, sin espacios exteriores y en minúsculas |
| `hash_contrasena` | `passwordHash`, interno | Sí | Campo interno; no se enviará al frontend |
| `rol` | `role` | Sí | `admin` o `agent`; defecto `agent` |
| `activo` | `isActive` | Sí | Defecto `true`; admite desactivación lógica |
| `creado_en` | `createdAt` | Sí | Fecha con zona horaria; defecto `now()` |
| `actualizado_en` | `updatedAt` | Sí | Fecha con zona horaria; el ORM la actualiza al modificar |

El ORM normaliza el correo antes de persistir. La base exige esa normalización y su unicidad. La validación completa del formato de correo y el algoritmo de hash se implementarán en el módulo de usuarios/autenticación. Crear esta columna no implementa el proceso de hash ni permite iniciar sesión.

## Tickets

| Columna PostgreSQL | Campo del dominio/API | Obligatorio | Comportamiento |
| --- | --- | --- | --- |
| `id` | `id` | Sí | UUID generado por PostgreSQL |
| `titulo` | `title` | Sí | Texto con contenido |
| `descripcion` | `description` | Sí | Texto con contenido |
| `estado` | `status` | Sí | `open`, `in_progress`, `resolved`, `closed`; defecto `open` |
| `prioridad` | `priority` | Sí | `low`, `medium`, `high`, `critical`; defecto `medium` |
| `categoria` | `category` | No | Texto opcional; sin taxonomía definitiva |
| `area` | `area` | No | Texto opcional; sin mapeo automático desde ML |
| `creado_por_id` | `createdById`; API resumida `createdBy` | Sí | Referencia a `usuarios.id` |
| `asignado_a_id` | `assignedToId`; API resumida `assignedTo` | No | Referencia opcional a `usuarios.id` |
| `creado_en` | `createdAt` | Sí | Fecha con zona horaria; defecto `now()` |
| `actualizado_en` | `updatedAt` | Sí | Fecha con zona horaria; el ORM la actualiza al modificar |
| `resuelto_en` | `resolvedAt` | No | Fecha opcional con zona horaria |

## Decisiones técnicas iniciales

- Los UUID se generan con `gen_random_uuid()`, disponible en PostgreSQL 17.
- Las fechas utilizan `timestamp with time zone`. Las conexiones del backend trabajan en UTC.
- Los roles, estados y prioridades se almacenan como texto con restricciones `CHECK`; no se crean tipos ENUM nativos en PostgreSQL.
- Categoría y área permanecen opcionales. No se equipara la salida `type` del baseline ML a categoría ni se elimina `critical` del dominio.
- Las claves foráneas usan `RESTRICT` para conservar los vínculos históricos si se intenta eliminar físicamente un usuario referenciado. La desactivación mediante `activo=false` conserva los tickets.
- Hay índices para creador, agente asignado y estado/fecha de creación.
- Las fechas de actualización se gestionan mediante `onupdate` del ORM. Una actualización SQL directa debe establecer `actualizado_en` explícitamente.
- La migración conserva pgvector; no crea embeddings ni decide su dimensión.

Las reglas de autorización, asignación de agentes, transiciones de estado, fecha de resolución, retención y taxonomías siguen pendientes. No se consideran implementadas por el hecho de existir estas tablas.

## Aplicación y pruebas

Primero se aplica y verifica la revisión en `db_test`, usando `-x base=testing`. Las pruebas de persistencia usan datos ficticios y transacciones que se revierten al terminar. La prueba de migración revierte y reaplica la revisión dentro de una transacción externa que también se revierte.

Después de las verificaciones locales se puede aplicar `upgrade head` en la base de desarrollo. No se ejecuta `downgrade` en desarrollo como parte de este procedimiento: la reversión de esta revisión elimina las tablas y sus datos.

La migración no inserta usuarios, contraseñas ni tickets de demostración. Se necesita ejecutar las migraciones en cada entorno: los archivos Python se comparten mediante Git, los datos locales no.

## Referencias

- [Modelo inicial del dominio](modelo-dominio.md)
- [Contrato frontend–backend](../contratos/frontend-backend.md)
- [Procedimiento de migraciones](../../backend/migraciones/README.md)
- [UUID en PostgreSQL 17](https://www.postgresql.org/docs/17/functions-uuid.html)
- [Fechas y zonas horarias](https://www.postgresql.org/docs/17/datatype-datetime.html)
