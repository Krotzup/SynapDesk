"""Coordinación transaccional con sesiones existentes, sin frontera HTTP.

MVP02: admin/agent pueden crear, listar, consultar, cambiar estado y contar.
La autorización no incluye otras operaciones ni sustituye controles HTTP.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.seguridad.operaciones_sesion import ReferenciaSesion
from app.seguridad.sesiones import ServicioSesiones, SesionConsultada
from app.seguridad.transacciones import (
    CodigoSeguridad, ErrorSeguridad, Reloj, reloj_postgresql, transaccion_seguridad,
)
from app.tickets.esquemas import (
    EstadoTicket, Ticket, TicketCreate, TicketList, TicketPagination, TicketStatusUpdate, TicketSummary,
)
from app.tickets.repositorio import CodigoTickets, ErrorTickets, RepositorioTickets, exigir_uuid


class OperacionTicket(StrEnum):
    CREAR = "CREAR"
    LISTAR = "LISTAR"
    DETALLE = "DETALLE"
    ESTADO = "ESTADO"
    RESUMEN = "RESUMEN"


# Dependencia interna de código, nunca un dato enviado en JSON/configuración.
# LISTAR/RESUMEN conceden alcance global: una futura visibilidad por filas exige
# adaptar la consulta antes de autorizar esas operaciones.
AutorizadorTickets = Callable[[SesionConsultada, OperacionTicket, UUID | None], bool]
# Control interno del adaptador, ejecutado en la MISMA transacción de escritura.
# El booleano indica si aún no se invocó la tarea; no es un permiso del cliente.
ControlEscritura = Callable[[Session, SesionConsultada, bool], None]
_T = TypeVar("_T")


class ServicioTickets:
    def __init__(self, motor: Engine, *, autorizador: AutorizadorTickets | None = None,
                 reloj: Reloj = reloj_postgresql) -> None:
        if motor.dialect.name != "postgresql":
            raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
        self._motor = motor.execution_options(isolation_level="READ COMMITTED")
        self._autorizador = autorizador
        self._reloj = reloj

    def _autorizar(self, actual: SesionConsultada, operacion: OperacionTicket,
                   ticket_id: UUID | None) -> None:
        # Matriz MVP V1 aprobada por el PO. No otorga asignación, borrado,
        # edición libre, administración ni acceso a otros recursos.
        if type(operacion) is not OperacionTicket or actual.usuario.role not in {"admin", "agent"}:
            raise ErrorTickets(CodigoTickets.NO_AUTORIZADO)
        # Una política adicional puede restringir; nunca ampliar la matriz.
        if self._autorizador is not None and self._autorizador(actual, operacion, ticket_id) is not True:
            raise ErrorTickets(CodigoTickets.NO_AUTORIZADO)

    def _ejecutar(self, referencia: ReferenciaSesion | None, operacion: OperacionTicket,
                  ticket_id: UUID | None,
                  tarea: Callable[[RepositorioTickets, SesionConsultada], _T],
                  control_escritura: ControlEscritura | None = None) -> _T:
        if type(referencia) is not ReferenciaSesion:
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        with Session(self._motor) as db, transaccion_seguridad(db):
            db.execute(text("SET LOCAL search_path = pg_catalog, public"))
            db.execute(text("SET LOCAL lock_timeout = '3s'"))
            sesiones = ServicioSesiones(db, self._reloj)

            def validar():
                actual = sesiones.consultar(referencia.credencial)
                self._autorizar(actual, operacion, ticket_id)
                return actual

            actual = validar()
            if control_escritura is not None:
                control_escritura(db, actual, True)
            resultado = tarea(RepositorioTickets(db), actual)
            # Vigencia tras esperas/locks, antes del commit. Usuario y sesión
            # permanecen bloqueados por las primitivas existentes. Sin actividad
            # automática ni un nuevo mecanismo de autenticación.
            actual = validar()
            if control_escritura is not None:
                control_escritura(db, actual, False)
                validar()
        return resultado

    def crear(self, referencia: ReferenciaSesion | None, datos: TicketCreate, *,
              control_escritura: ControlEscritura | None = None) -> Ticket:
        return self._ejecutar(referencia, OperacionTicket.CREAR, None,
            lambda repo, actual: repo.crear(datos, creador_id=actual.usuario.id), control_escritura)

    def listar(self, referencia: ReferenciaSesion | None,
               pagina: TicketPagination | None = None) -> TicketList:
        return self._ejecutar(referencia, OperacionTicket.LISTAR, None,
            lambda repo, _: repo.listar(pagina if pagina is not None else TicketPagination()))

    def detalle(self, referencia: ReferenciaSesion | None, ticket_id: UUID) -> Ticket:
        exigir_uuid(ticket_id)
        return self._ejecutar(referencia, OperacionTicket.DETALLE, ticket_id,
            lambda repo, _: repo.detalle(ticket_id))

    def actualizar_estado(self, referencia: ReferenciaSesion | None, ticket_id: UUID,
                          datos: TicketStatusUpdate, *,
                          estado_esperado: EstadoTicket | None = None,
                          control_escritura: ControlEscritura | None = None) -> Ticket:
        exigir_uuid(ticket_id)
        return self._ejecutar(referencia, OperacionTicket.ESTADO, ticket_id,
            lambda repo, _: repo.actualizar_estado(ticket_id, datos, estado_esperado=estado_esperado),
            control_escritura)

    def resumen(self, referencia: ReferenciaSesion | None) -> TicketSummary:
        return self._ejecutar(referencia, OperacionTicket.RESUMEN, None, lambda repo, _: repo.resumen())
