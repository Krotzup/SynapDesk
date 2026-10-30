# Migraciones

Alembic utiliza la configuración de PostgreSQL del backend. No guardes credenciales en `alembic.ini`, `env.py` ni en las revisiones.

## Estado actual

Existe una revisión inicial: `0001_usuarios_tickets`, que crea `usuarios` y `tickets`, sus relaciones, restricciones e índices.

`upgrade head` crea las tablas y registra la revisión en `alembic_version`. No inserta registros de usuarios o tickets ni crea columnas vectoriales.

## Comandos

Desde `backend/`, en CMD con el entorno virtual activo:

```cmd
python -m alembic --version
python -m alembic heads
python -m alembic history
```

Los comandos `heads` y `history` no requieren PostgreSQL. `heads` debe mostrar `0001_usuarios_tickets (head)`.

Para verificar primero contra `db_test`:

```cmd
python -m alembic -x base=testing upgrade head
python -m alembic -x base=testing current
python -m alembic -x base=testing check
```

La selección explícita utiliza las variables `POSTGRES_TEST_*`. Una selección desconocida produce un error, en lugar de utilizar la base principal. `APP_ENV=testing` por sí solo no selecciona la base de pruebas.

Sin `-x base=testing`, Alembic utiliza las variables `POSTGRES_*` de la base principal:

```cmd
python -m alembic current
```

Después de verificar la revisión en testing se puede aplicar en desarrollo con `python -m alembic upgrade head`. `current` debe mostrar el identificador aplicado. `check` verifica la correspondencia entre modelos y estructura; no genera revisiones.

## Incorporar modelos y revisiones

1. Definir los modelos SQLAlchemy derivados de `app.persistencia.base.Base`.
2. Importar sus módulos en `migraciones/env.py` para registrar sus tablas.
3. Crear una revisión contra la base de pruebas mediante `python -m alembic -x base=testing revision --autogenerate -m "descripcion_del_cambio"`.
4. Revisar manualmente `upgrade()` y `downgrade()` antes de ejecutar la revisión.
5. Aplicarla y verificarla primero en `db_test`.
6. Versionar los modelos y su revisión en el mismo PR.

Una revisión compartida y aplicada por el equipo no debe editarse para cambiar su comportamiento: se crea una revisión nueva.

La generación automática produce una propuesta que debe revisarse. No ejecutes generación automática con metadatos incompletos: podría proponer eliminar tablas que no estén registradas.

Las migraciones serán el mecanismo de cambio de estructura; evita `Base.metadata.create_all()` al iniciar FastAPI. El backend no aplica migraciones automáticamente.

La extensión pgvector sigue habilitada por la inicialización Docker existente. Este paso no cambia esa responsabilidad ni crea columnas vectoriales.

## Reversión y datos

La función `downgrade()` de `0001_usuarios_tickets` elimina primero `tickets` y después `usuarios`, con sus datos. La prueba de integración comprueba reversión y reaplicación exclusivamente en `db_test` y dentro de una transacción que revierte al terminar. No ejecutes esa reversión en la base de desarrollo como parte de la comprobación normal.

## Nombres obligatorios

`env.py`, `script.py.mako`, `revision`, `upgrade()` y `downgrade()` son nombres reconocidos por Alembic. La carpeta del proyecto se denomina `migraciones` y las revisiones se guardarán en `versiones`.

## Referencias

- [Tutorial oficial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Generación automática](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
