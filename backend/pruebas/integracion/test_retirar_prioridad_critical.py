from uuid import uuid4

from alembic import command
from sqlalchemy import inspect, text


def test_migracion_conserva_tickets_y_restringe_catalogo(
    conexion_bd_test, configuracion_alembic_test
) -> None:
    conexion = conexion_bd_test
    configuracion = configuracion_alembic_test
    command.downgrade(configuracion, "0002_autenticacion_persistencia")
    usuario_id = conexion.execute(
        text("INSERT INTO usuarios (nombre, correo, hash_contrasena) "
             "VALUES ('Agente ficticio', :correo, 'hash_ficticio') RETURNING id"),
        {"correo": f"migracion-{uuid4()}@example.invalid"},
    ).scalar_one()
    ids = {}
    for prioridad in ("critical", "high", "medium", "low"):
        ids[prioridad] = conexion.execute(
            text("INSERT INTO tickets (titulo, descripcion, creado_por_id, prioridad) "
                 "VALUES ('Prueba', 'Ticket ficticio', :usuario, :prioridad) RETURNING id"),
            {"usuario": usuario_id, "prioridad": prioridad},
        ).scalar_one()

    command.upgrade(configuracion, "head")
    for original, ticket_id in ids.items():
        fila = conexion.execute(
            text("SELECT prioridad, titulo, descripcion, creado_por_id FROM tickets WHERE id = :id"),
            {"id": ticket_id},
        ).one()
        assert tuple(fila) == ("high" if original == "critical" else original,
                               "Prueba", "Ticket ficticio", usuario_id)
    restricciones = inspect(conexion).get_check_constraints("tickets")
    prioridad = next(c for c in restricciones if c["name"] == "ck_tickets_prioridad_valida")
    assert "critical" not in prioridad["sqltext"]
    command.check(configuracion)

    command.downgrade(configuracion, "0002_autenticacion_persistencia")
    assert conexion.execute(
        text("SELECT prioridad FROM tickets WHERE id = :id"), {"id": ids["critical"]},
    ).scalar_one() == "high"
    # Volver a head también verifica que una actualización sin critical es válida.
    command.upgrade(configuracion, "head")
