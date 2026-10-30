import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.persistencia.conexion import crear_motor_bd
from app.persistencia.entornos import seleccionar_configuracion_bd

RAIZ_BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def configuracion_bd_test():
    if os.getenv("EJECUTAR_PRUEBAS_BD") != "1":
        pytest.skip("Requiere db_test y EJECUTAR_PRUEBAS_BD=1.")
    return seleccionar_configuracion_bd("testing")


def configuracion_alembic(conexion) -> Config:
    configuracion = Config(str(RAIZ_BACKEND / "alembic.ini"))
    configuracion.attributes["connection"] = conexion
    return configuracion


@pytest.fixture
def conexion_bd_test(configuracion_bd_test):
    motor = crear_motor_bd(configuracion_bd_test)
    try:
        with motor.connect() as conexion:
            transaccion = conexion.begin()
            try:
                command.upgrade(configuracion_alembic(conexion), "head")
                yield conexion
            finally:
                transaccion.rollback()
    finally:
        motor.dispose()


@pytest.fixture
def configuracion_alembic_test(conexion_bd_test):
    return configuracion_alembic(conexion_bd_test)


@pytest.fixture
def sesion_bd_test(conexion_bd_test):
    with Session(
        bind=conexion_bd_test,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as sesion:
        yield sesion
