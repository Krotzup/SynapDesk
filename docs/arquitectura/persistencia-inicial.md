# Persistencia relacional inicial

## Estado y alcance

La revisión `0001_usuarios_tickets` crea las tablas `usuarios` y `tickets` en PostgreSQL. La revisión posterior `0002_autenticacion_persistencia` agrega las cinco tablas de autenticación descritas abajo. Esta capa no implementa rutas de usuarios o tickets, servicios de autenticación, predicciones ni persistencia vectorial.

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

## Persistencia de autenticación

La [revisión 0002](../../backend/migraciones/versiones/0002_autenticacion_persistencia.py) agrega tablas sin alterar las de la revisión inicial:

| Tabla | Responsabilidad y relaciones principales |
| --- | --- |
| `sesiones` | Credencial opaca por digest único, creación, última actividad, expiración absoluta y revocación; FK `usuario_id` a `usuarios` con `RESTRICT`. |
| `contextos_csrf` | Contexto anónimo con digest de secreto o autenticado con `sesion_id`, nunca ambas vinculaciones; FK a `sesiones` con `RESTRICT` y contexto autenticado único por sesión; vigencia y revocación propias. |
| `tokens_csrf` | Varios tokens por contexto, cada uno con digest único, emisión, expiración e invalidación; FK `contexto_id` con `RESTRICT`. |
| `limites_autenticacion` | Clave HMAC seudonimizada, ventana, contadores, reservas y bloqueo; unicidad por tipo/clave/inicio de ventana y versión optimista para detectar actualizaciones obsoletas. No fija cuotas. |
| `eventos_autenticacion` | Fecha, tipo, resultado y contexto mínimo; referencias opcionales a usuario/sesión con `SET NULL`. El evento sobrevive al borrado de la entidad, pero pierde esa referencia. No fija retención. |

Los [modelos](../../backend/app/persistencia/modelos/) almacenan UUID internos, fechas con zona horaria y digests de 32 bytes. SHA-256 se reserva para secretos aleatorios de sesión/CSRF; cuenta normalizada e IP verificada requieren HMAC-SHA-256 con clave secreta exclusiva del servidor. Estos últimos datos son seudonimizados, no anónimos. La derivación se implementa fuera del ORM en el [servicio de identificadores](../../backend/app/seguridad/identificadores.py); la gestión/rotación operativa de claves y la verificación confiable de IP siguen pendientes. Los `CHECK` validan fechas de cada fila; los [servicios internos](../../backend/app/seguridad/README.md) acotan adicionalmente la expiración del token por su contexto/sesión y comprueban la vigencia bajo bloqueos. No se agregan restricciones entre tablas ni endpoints. Para políticas y decisiones aprobadas, consultar el [contrato de autenticación](../contratos/autenticacion-v1.md).

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
