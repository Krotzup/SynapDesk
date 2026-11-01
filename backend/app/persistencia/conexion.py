from fastapi import Request
from sqlalchemy import URL, Engine, create_engine

from app.configuracion import Configuracion


def construir_url_bd(configuracion: Configuracion) -> URL:
    if not configuracion.tiene_configuracion_bd:
        raise ValueError("Falta configurar PostgreSQL en las variables de entorno.")

    return URL.create(
        drivername="postgresql+psycopg",
        username=configuracion.postgres_user,
        password=configuracion.postgres_password.get_secret_value(),
        host=configuracion.postgres_host,
        port=configuracion.postgres_port,
        database=configuracion.postgres_db,
    )


def crear_motor_bd(configuracion: Configuracion) -> Engine:
    """Crea el motor; la primera conexión se abre al realizar una consulta."""
    return create_engine(
        construir_url_bd(configuracion),
        pool_pre_ping=True,
        pool_timeout=5,
        echo=False,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "sslmode": configuracion.postgres_sslmode,
            "options": "-c statement_timeout=5000 -c timezone=UTC",
        },
    )


def obtener_motor_bd(request: Request) -> Engine | None:
    return request.app.state.motor_bd
