from logging.config import fileConfig

from alembic import context
from alembic.util import CommandError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.persistencia.base import Base
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.entornos import seleccionar_configuracion_bd
from app.persistencia import modelos  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Los módulos importados arriba registran sus tablas en la base declarativa.
target_metadata = Base.metadata


def ejecutar_migraciones_sin_conexion() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_con_conexion(conexion) -> None:
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_migraciones_con_conexion() -> None:
    # Permite que herramientas o pruebas proporcionen su propia conexión.
    conexion_externa = config.attributes.get("connection")
    if conexion_externa is not None:
        ejecutar_con_conexion(conexion_externa)
        return

    argumentos = context.get_x_argument(as_dictionary=True)
    motor = None
    try:
        configuracion = seleccionar_configuracion_bd(
            argumentos.get("base", "principal")
        )
        motor = crear_motor_bd(configuracion)
        with motor.connect() as conexion:
            ejecutar_con_conexion(conexion)
    except ValidationError:
        raise CommandError(
            "La configuración de PostgreSQL es incompleta o inválida. Revisa .env."
        ) from None
    except ValueError as error:
        raise CommandError(str(error)) from None
    except SQLAlchemyError:
        raise CommandError(
            "No se pudo ejecutar Alembic en PostgreSQL. Revisa el servicio y .env."
        ) from None
    finally:
        if motor is not None:
            motor.dispose()


if context.is_offline_mode():
    ejecutar_migraciones_sin_conexion()
else:
    ejecutar_migraciones_con_conexion()
