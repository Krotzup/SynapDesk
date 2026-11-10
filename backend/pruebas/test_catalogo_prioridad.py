from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint

from app.persistencia.modelos import Ticket


def configuracion_sin_conexion():
    salida = StringIO()
    configuracion = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=salida,
    )
    return configuracion, salida


def test_nuevo_catalogo_tiene_una_revision_y_sql_coherente_con_orm():
    configuracion, salida = configuracion_sin_conexion()
    assert ScriptDirectory.from_config(configuracion).get_heads() == [
        "0003_retirar_prioridad_critical",
    ]
    command.upgrade(configuracion, "0002_autenticacion_persistencia:head", sql=True)
    sql = salida.getvalue()
    assert "LOCK TABLE tickets IN ACCESS EXCLUSIVE MODE" in sql
    assert "WHERE prioridad = 'critical'" in sql
    assert "SET prioridad = 'high', actualizado_en = now()" in sql
    assert sql.index("UPDATE tickets") < sql.index("DROP CONSTRAINT") < sql.index("ADD CONSTRAINT")
    restriccion = next(
        c for c in Ticket.__table__.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_tickets_prioridad_valida"
    )
    assert "critical" not in str(restriccion.sqltext)
    assert f"CHECK ({restriccion.sqltext})" in sql
    assert "BEGIN;" in sql and "COMMIT;" in sql


def test_downgrade_restaura_catalogo_sin_inventar_etiquetas_historicas():
    configuracion, salida = configuracion_sin_conexion()
    command.downgrade(configuracion, "head:0002_autenticacion_persistencia", sql=True)
    sql = salida.getvalue()
    assert "prioridad IN ('low', 'medium', 'high', 'critical')" in sql
    assert "UPDATE tickets" not in sql
