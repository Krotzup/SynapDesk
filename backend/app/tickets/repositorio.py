"""Primitivas SQL de confianza, sin autorización ni commit implícito.

Un UUID solo identifica una FK: no acredita usuario ni permiso. El coordinador
debe validar sesión/autorización y abarcar la operación con una transacción.
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import String, cast, false, func, or_, select, true
from sqlalchemy.orm import Session, aliased, joinedload, raiseload

from app.persistencia.modelos import Ticket as TicketORM, Usuario
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad, operacion_bd
from app.tickets.esquemas import (
    EstadoTicket, Ticket, TicketCreate, TicketList, TicketPagination, TicketStatusUpdate,
    TicketSummary, UsuarioTicket,
)
from app.tickets.transiciones import transicion_permitida


class CodigoTickets(StrEnum):
    ENTRADA = "ENTRADA"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    CONFLICTO_ESTADO = "CONFLICTO_ESTADO"
    TRANSICION_INVALIDA = "TRANSICION_INVALIDA"
    PERMISO_NO_RATIFICADO = "PERMISO_NO_RATIFICADO"
    NO_AUTORIZADO = "NO_AUTORIZADO"


class ErrorTickets(Exception):
    """Código interno, sin SQL, identificadores, texto del ticket ni secretos."""

    def __init__(self, codigo: CodigoTickets) -> None:
        self.codigo = codigo
        super().__init__(f"Operación de tickets rechazada: {codigo.value}.")


def exigir_uuid(value: UUID) -> None:
    if type(value) is not UUID:
        raise ErrorTickets(CodigoTickets.ENTRADA)


def _usuario(fila: Usuario) -> UsuarioTicket:
    return UsuarioTicket(id=fila.id, name=fila.nombre, email=fila.correo, role=fila.rol,
        isActive=fila.activo, createdAt=fila.creado_en, updatedAt=fila.actualizado_en)


def _representar(fila: TicketORM) -> Ticket:
    return Ticket(id=fila.id, title=fila.titulo, description=fila.descripcion,
        status=fila.estado, priority=fila.prioridad, category=fila.categoria, area=fila.area,
        createdBy=_usuario(fila.creador),
        assignedTo=_usuario(fila.asignado_a) if fila.asignado_a is not None else None,
        createdAt=fila.creado_en, updatedAt=fila.actualizado_en, resolvedAt=fila.resuelto_en)


def _relaciones(modelo):
    campos = (Usuario.id, Usuario.nombre, Usuario.correo, Usuario.rol,
              Usuario.activo, Usuario.creado_en, Usuario.actualizado_en)
    return (raiseload("*"), joinedload(modelo.creador).load_only(*campos, raiseload=True),
            joinedload(modelo.asignado_a).load_only(*campos, raiseload=True))


class RepositorioTickets:
    """No conectar directamente a Request/Depends ni a una identidad del cliente."""

    def __init__(self, db: Session) -> None:
        if db.get_bind().dialect.name != "postgresql":
            raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
        self.db = db

    def crear(self, datos: TicketCreate, *, creador_id: UUID) -> Ticket:
        exigir_uuid(creador_id)
        if type(datos) is not TicketCreate:
            raise ErrorTickets(CodigoTickets.ENTRADA)
        # Revalidar incluso una instancia creada con model_construct/copy(update).
        datos = TicketCreate.model_validate(datos.model_dump())
        with operacion_bd(self.db):
            fila = TicketORM(titulo=datos.title, descripcion=datos.description,
                             creado_por_id=creador_id)
            self.db.add(fila)
            self.db.flush()
            return self.detalle(fila.id)

    def listar(self, pagina: TicketPagination) -> TicketList:
        if type(pagina) is not TicketPagination:
            raise ErrorTickets(CodigoTickets.ENTRADA)
        pagina = TicketPagination.model_validate(pagina.model_dump())
        with operacion_bd(self.db):
            # Una única sentencia/snapshot incluye total aunque la página esté
            # vacía o fuera de rango; dos SELECT separados bajo READ COMMITTED
            # podrían devolver un total y una página de instantes diferentes.
            condiciones = []
            for nombre, campo in (("status", TicketORM.estado), ("priority", TicketORM.prioridad),
                                  ("category", TicketORM.categoria), ("area", TicketORM.area)):
                valor = getattr(pagina, nombre)
                if valor is not None:
                    condiciones.append(campo == valor)
            if pagina.search:
                # autoescape evita que % y _ del usuario se conviertan en comodines.
                campos = (TicketORM.titulo, TicketORM.descripcion, TicketORM.categoria,
                          TicketORM.area, cast(TicketORM.id, String))
                condiciones.append(or_(
                    *(campo.icontains(pagina.search, autoescape=True) for campo in campos),
                    TicketORM.creador.has(Usuario.nombre.icontains(pagina.search, autoescape=True)),
                ))
            total = select(func.count(TicketORM.id).label("cantidad")).where(*condiciones).cte("total_tickets")
            posicion = (pagina.page - 1) * pagina.pageSize
            filas = select(TicketORM).where(*condiciones).order_by(
                TicketORM.creado_en.desc(), TicketORM.id.desc(),
            )
            if posicion > 2**63 - 1:
                # OFFSET y count() son bigint en PostgreSQL. Una posición mayor
                # no puede contener filas; no enviar ese entero al controlador.
                # El total conserva el mismo snapshot y page no se trunca.
                filas = filas.where(false())
            else:
                filas = filas.offset(posicion)
            filas = filas.limit(pagina.pageSize).subquery()
            ticket = aliased(TicketORM, filas)
            resultado = self.db.execute(select(total.c.cantidad, ticket).select_from(total)
                .outerjoin(ticket, true()).options(*_relaciones(ticket)).order_by(
                    ticket.creado_en.desc(), ticket.id.desc())).all()
            cantidad = resultado[0][0]
            items = tuple(_representar(fila) for _, fila in resultado if fila is not None)
            return TicketList(items=items, page=pagina.page, pageSize=pagina.pageSize,
                totalItems=cantidad, totalPages=(cantidad + pagina.pageSize - 1) // pagina.pageSize)

    def detalle(self, ticket_id: UUID) -> Ticket:
        exigir_uuid(ticket_id)
        with operacion_bd(self.db):
            fila = self.db.scalar(select(TicketORM).where(TicketORM.id == ticket_id)
                .options(*_relaciones(TicketORM)).execution_options(populate_existing=True))
            if fila is None:
                raise ErrorTickets(CodigoTickets.NO_ENCONTRADO)
            return _representar(fila)

    def actualizar_estado(self, ticket_id: UUID, datos: TicketStatusUpdate, *,
                          estado_esperado: EstadoTicket | None = None) -> Ticket:
        exigir_uuid(ticket_id)
        if type(datos) is not TicketStatusUpdate:
            raise ErrorTickets(CodigoTickets.ENTRADA)
        datos = TicketStatusUpdate.model_validate(datos.model_dump())
        estado_esperado = datos.expectedStatus if datos.expectedStatus is not None else estado_esperado
        if estado_esperado is not None:
            # Precondición interna optativa; no añade campos/headers al HTTP.
            estado_esperado = TicketStatusUpdate(status=estado_esperado).status
        with operacion_bd(self.db):
            # Bloquear solo la fila del ticket, nunca los lados nullable de JOIN.
            fila = self.db.scalar(select(TicketORM).where(TicketORM.id == ticket_id)
                .with_for_update().execution_options(populate_existing=True))
            if fila is None:
                raise ErrorTickets(CodigoTickets.NO_ENCONTRADO)
            if estado_esperado is not None and fila.estado != estado_esperado:
                raise ErrorTickets(CodigoTickets.CONFLICTO_ESTADO)
            if not transicion_permitida(fila.estado, datos.status):
                raise ErrorTickets(CodigoTickets.TRANSICION_INVALIDA)
            if fila.estado != datos.status:
                fila.estado = datos.status
                # now() conserva el inicio de la transacción. Después de esperar
                # el lock podría retroceder frente a una escritura ya confirmada.
                # Usar el reloj del servidor después del lock y conservar monotonía.
                ahora = self.db.scalar(select(func.clock_timestamp()))
                fila.actualizado_en = max(fila.actualizado_en, ahora)
                if datos.status == "resolved":
                    fila.resuelto_en = fila.actualizado_en
                elif datos.status in {"open", "in_progress"}:
                    fila.resuelto_en = None
                self.db.flush()
            return self.detalle(ticket_id)

    def resumen(self) -> TicketSummary:
        with operacion_bd(self.db):
            total, abiertos, en_progreso, resueltos, cerrados = self.db.execute(select(
                func.count(TicketORM.id),
                *(func.count(TicketORM.id).filter(TicketORM.estado == estado)
                  for estado in ("open", "in_progress", "resolved", "closed")),
            )).one()
            return TicketSummary(totalTickets=total, openTickets=abiertos,
                inProgressTickets=en_progreso, resolvedTickets=resueltos, closedTickets=cerrados)
