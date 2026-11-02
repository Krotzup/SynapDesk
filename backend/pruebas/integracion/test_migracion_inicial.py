from alembic import command
from sqlalchemy import inspect, text


def test_migracion_se_revierte_se_aplica_y_coincide_con_modelos(
    conexion_bd_test, configuracion_alembic_test
) -> None:
    configuracion = configuracion_alembic_test

    command.downgrade(configuracion, "base")
    assert not inspect(conexion_bd_test).has_table("usuarios")
    assert not inspect(conexion_bd_test).has_table("tickets")

    command.upgrade(configuracion, "head")
    assert inspect(conexion_bd_test).has_table("usuarios")
    assert inspect(conexion_bd_test).has_table("tickets")
    assert inspect(conexion_bd_test).has_table("sesiones")
    assert inspect(conexion_bd_test).has_table("contextos_csrf")
    assert inspect(conexion_bd_test).has_table("tokens_csrf")
    assert inspect(conexion_bd_test).has_table("limites_autenticacion")
    assert inspect(conexion_bd_test).has_table("eventos_autenticacion")
    revision = conexion_bd_test.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()
    assert revision == "0002_autenticacion_persistencia"
    command.check(configuracion)

    vector = conexion_bd_test.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one()
    assert vector == "0.8.6"
