"""DTO, límites de confianza y cierre HTTP del núcleo MVP01, sin infraestructura."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine

from app.api.esquemas_auth import AuthUser
from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.seguridad.operaciones_sesion import ReferenciaSesion
from app.seguridad.sesiones import Identidad, SesionConsultada
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate, TicketSummary
from app.tickets.repositorio import CodigoTickets, ErrorTickets, RepositorioTickets
from app.tickets.servicio import OperacionTicket, ServicioTickets


def test_creacion_recorta_sin_aceptar_campos_servidor():
    datos = TicketCreate(title=" \tTicket de prueba\n", description="  Descripción válida.  ")
    assert datos.model_dump() == {"title": "Ticket de prueba", "description": "Descripción válida."}
    assert "Descripción" not in repr(datos)
    with pytest.raises(ValidationError):
        TicketCreate(title="Ticket de prueba", description="Descripción válida.", createdBy=uuid4())


@pytest.mark.parametrize("cambio", [
    {"title": "    "}, {"title": "abcd"}, {"title": "a" * 151},
    {"description": "x" * 9}, {"description": "x" * 5001},
    {"title": 12345}, {"description": None},
    {"title": "abc\x00def"}, {"description": "texto\ud800inválido"},
])
def test_creacion_rechaza_entrada_invalida_sin_imprimirla(cambio):
    with pytest.raises(ValidationError) as error:
        TicketCreate(**({"title": "Ticket válido", "description": "Descripción válida."} | cambio))
    assert "input_value" not in str(error.value)


def test_limite_candidato_utf16_compatible_con_formulario():
    assert TicketCreate(title="🙂" * 75, description="Descripción válida.").title == "🙂" * 75
    with pytest.raises(ValidationError):
        TicketCreate(title="🙂" * 76, description="Descripción válida.")


@pytest.mark.parametrize("datos", [
    {"page": 0}, {"page": -1}, {"page": True}, {"page": "2"},
    {"pageSize": 0}, {"pageSize": 101}, {"sort": "sql"},
])
def test_paginacion_estricta(datos):
    with pytest.raises(ValidationError):
        TicketPagination(**datos)


@pytest.mark.parametrize("estado", ["critical", "OPEN", "", None, 1])
def test_estados_fuera_del_modelo_no_se_aceptan(estado):
    with pytest.raises(ValidationError):
        TicketStatusUpdate(status=estado)


def test_actualizacion_no_admite_campos_ajenos():
    with pytest.raises(ValidationError):
        TicketStatusUpdate(status="closed", priority="high")


@pytest.fixture
def servicio():
    # Motor perezoso: estas pruebas nunca establecen una conexión.
    motor = create_engine("postgresql+psycopg://", hide_parameters=True)
    try:
        yield ServicioTickets(motor)
    finally:
        motor.dispose()


@pytest.mark.parametrize("referencia", [None, uuid4(), "identificador", SecretStr("servicio")])
def test_uuid_o_credencial_servicio_no_autorizan_creacion(servicio, referencia):
    with pytest.raises(ErrorSeguridad) as error:
        servicio.crear(referencia, TicketCreate(title="Ticket válido", description="Descripción válida."))
    assert error.value.codigo == CodigoSeguridad.SESION_INEXISTENTE


def test_authuser_presentado_no_sustituye_sesion(servicio):
    with pytest.raises(ErrorSeguridad):
        servicio.resumen(AuthUser(id=uuid4(), email="test@example.invalid", role="admin"))


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_creacion_admite_solo_roles_del_contrato(servicio, rol):
    # Identidad sintética exclusiva de unidad, no se crea ni usa en producción.
    ahora = datetime.now(UTC)
    actual = SesionConsultada(uuid4(), Identidad(uuid4(), "test@example.invalid", rol), ahora, ahora)
    servicio._autorizar(actual, OperacionTicket.CREAR, None)


@pytest.mark.parametrize("rol", ["admin", "agent"])
@pytest.mark.parametrize("operacion", list(OperacionTicket))
def test_matriz_mvp_aprobada(servicio, operacion, rol):
    ahora = datetime.now(UTC)
    actual = SesionConsultada(uuid4(), Identidad(uuid4(), "test@example.invalid", rol), ahora, ahora)
    servicio._autorizar(actual, operacion, None)


@pytest.mark.parametrize("rol,operacion", [("otro", OperacionTicket.CREAR),
    ("otro", OperacionTicket.LISTAR), ("admin", "DELETE"), ("agent", "USUARIOS")])
def test_politica_adicional_no_amplia_matriz(servicio, rol, operacion):
    servicio._autorizador = lambda *_: True
    ahora = datetime.now(UTC)
    actual = SesionConsultada(uuid4(), Identidad(uuid4(), "test@example.invalid", rol), ahora, ahora)
    with pytest.raises(ErrorTickets):
        servicio._autorizar(actual, operacion, None)


def test_autorizador_no_acepta_un_valor_truthy_como_permiso():
    motor = create_engine("postgresql+psycopg://", hide_parameters=True)
    try:
        servicio = ServicioTickets(motor, autorizador=lambda *_: "true")
        ahora = datetime.now(UTC)
        actual = SesionConsultada(uuid4(), Identidad(uuid4(), "test@example.invalid", "admin"), ahora, ahora)
        with pytest.raises(ErrorTickets):
            servicio._autorizar(actual, OperacionTicket.RESUMEN, None)
    finally:
        motor.dispose()


def test_nucleo_exige_postgresql():
    from sqlalchemy.orm import Session
    motor = create_engine("sqlite://")
    try:
        with Session(motor) as db, pytest.raises(ErrorSeguridad):
            RepositorioTickets(db)
        with pytest.raises(ErrorSeguridad):
            ServicioTickets(motor)
    finally:
        motor.dispose()


def test_conteos_no_inventan_metricas_y_son_inmutables():
    resumen = TicketSummary(totalTickets=1, openTickets=1, inProgressTickets=0,
                           resolvedTickets=0, closedTickets=0)
    assert "avgResolutionTimeHours" not in resumen.model_dump()
    with pytest.raises(ValidationError):
        resumen.totalTickets = 2


def test_aplicacion_conserva_exactamente_las_rutas_anteriores():
    app = crear_aplicacion(Configuracion(_env_file=None, app_env="testing"))
    # La búsqueda de #32 ya está integrada; el núcleo de tickets no agrega rutas.
    assert set(app.openapi()["paths"]) == {
        "/api/v1/health", "/api/v1/ready", "/api/v1/auth/csrf", "/api/v1/search",
    }
