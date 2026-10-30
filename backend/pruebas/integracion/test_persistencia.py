from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.persistencia.modelos import Ticket, Usuario


def crear_usuario(sesion, **cambios) -> Usuario:
    datos = {
        "nombre": "Agente ficticio",
        "correo": f"prueba-{uuid4()}@example.invalid",
        "hash_contrasena": "hash_ficticio_no_utilizable_para_autenticacion",
    }
    datos.update(cambios)
    usuario = Usuario(**datos)
    sesion.add(usuario)
    sesion.flush()
    return usuario


def crear_ticket(sesion, usuario: Usuario, **cambios) -> Ticket:
    datos = {
        "titulo": "Incidencia ficticia de conexión",
        "descripcion": "Registro generado exclusivamente para pruebas.",
        "creado_por_id": usuario.id,
    }
    datos.update(cambios)
    ticket = Ticket(**datos)
    sesion.add(ticket)
    sesion.flush()
    return ticket


def test_persistir_usuario_y_ticket_con_valores_iniciales(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    ticket = crear_ticket(sesion_bd_test, usuario)
    critico = crear_ticket(sesion_bd_test, usuario, prioridad="critical")

    assert isinstance(usuario.id, UUID)
    assert isinstance(ticket.id, UUID)
    assert usuario.rol == "agent"
    assert usuario.activo is True
    assert ticket.estado == "open"
    assert ticket.prioridad == "medium"
    assert critico.prioridad == "critical"
    assert ticket.asignado_a_id is None
    assert ticket.categoria is None and ticket.area is None
    assert ticket.resuelto_en is None
    assert ticket.creado_en.utcoffset().total_seconds() == 0
    assert sesion_bd_test.get(Ticket, ticket.id).creador.id == usuario.id


def test_correo_normalizado_no_permite_duplicados(sesion_bd_test) -> None:
    correo = f"prueba-{uuid4()}@example.invalid"
    primero = crear_usuario(sesion_bd_test, correo=f"  {correo.upper()}  ")
    assert primero.correo == correo

    with pytest.raises(IntegrityError) as error:
        crear_usuario(sesion_bd_test, correo=correo)
    assert error.value.orig.diag.constraint_name == "uq_usuarios_correo"


@pytest.mark.parametrize("campo", ["creado_por_id", "asignado_a_id"])
def test_ticket_rechaza_usuario_inexistente(sesion_bd_test, campo) -> None:
    usuario = crear_usuario(sesion_bd_test)
    with pytest.raises(IntegrityError) as error:
        crear_ticket(sesion_bd_test, usuario, **{campo: uuid4()})
    assert error.value.orig.sqlstate == "23503"


@pytest.mark.parametrize(
    ("entidad", "campo", "valor"),
    [
        ("usuario", "rol", "superadmin"),
        ("ticket", "estado", "pending"),
        ("ticket", "prioridad", "urgent"),
    ],
)
def test_base_rechaza_rol_estado_o_prioridad_fuera_del_contrato(
    sesion_bd_test, entidad, campo, valor
) -> None:
    usuario = crear_usuario(sesion_bd_test)
    with pytest.raises(IntegrityError) as error:
        if entidad == "usuario":
            crear_usuario(sesion_bd_test, **{campo: valor})
        else:
            crear_ticket(sesion_bd_test, usuario, **{campo: valor})
    assert error.value.orig.sqlstate == "23514"


def test_eliminacion_fisica_no_borra_creador_con_historial(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    crear_ticket(sesion_bd_test, usuario)
    with pytest.raises(IntegrityError) as error:
        sesion_bd_test.delete(usuario)
        sesion_bd_test.flush()
    assert error.value.orig.sqlstate == "23503"


def test_desactivar_usuario_conserva_ticket_y_actualiza_fecha(sesion_bd_test) -> None:
    fecha_anterior = datetime(2000, 1, 1, tzinfo=UTC)
    usuario = crear_usuario(
        sesion_bd_test, creado_en=fecha_anterior, actualizado_en=fecha_anterior
    )
    ticket = crear_ticket(sesion_bd_test, usuario)
    usuario.activo = False
    sesion_bd_test.flush()
    sesion_bd_test.refresh(usuario)

    assert usuario.activo is False
    assert usuario.actualizado_en > fecha_anterior
    assert sesion_bd_test.get(Ticket, ticket.id).creado_por_id == usuario.id
