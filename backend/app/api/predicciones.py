"""Predicción persistida y generación explícita para tickets anteriores al modelo."""
from datetime import UTC
from uuid import UUID
from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.recomendaciones import GeneracionEntrada, _ticket
from app.persistencia.modelos import PrediccionTicket
from app.recuperacion.servicio import ErrorRecuperacion
from app.recomendaciones.acceso import identidad_aplicacion

router = APIRouter()


def representar(row):
    return {**row.resultado, "id": str(row.id), "ticketId": str(row.ticket_id),
            "createdAt": row.creado_en.astimezone(UTC).isoformat()}


def generar_prediccion(request, ticket_id):
    motor = request.app.state.motor_bd
    servicio = getattr(request.app.state, "clasificacion", None)
    if not servicio or motor is None:
        raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "La clasificación todavía no está preparada.")
    try:
        with Session(motor) as db:
            ticket = _ticket(db, ticket_id)
            title, description = ticket.titulo, ticket.descripcion
            huella = servicio.huella(title, description)
            row = db.scalar(select(PrediccionTicket).where(
                PrediccionTicket.ticket_id == ticket_id, PrediccionTicket.huella == huella))
            if row:
                return representar(row)
        resultado = servicio.predecir(title, description)
        with Session(motor) as db, db.begin():
            ticket = _ticket(db, ticket_id)
            if (ticket.titulo, ticket.descripcion) != (title, description):
                raise ErrorRecuperacion("TICKET_STATE_CONFLICT", "El ticket cambió; vuelve a solicitar la predicción.", 409)
            row = PrediccionTicket(ticket_id=ticket_id, huella=huella, resultado=resultado)
            db.add(row)
            db.flush()
            db.refresh(row)
            output = representar(row)
        return output
    except IntegrityError:
        with Session(motor) as db:
            row = db.scalar(select(PrediccionTicket).where(
                PrediccionTicket.ticket_id == ticket_id, PrediccionTicket.huella == huella))
            if row:
                return representar(row)
        raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "No se pudo guardar la predicción.") from None
    except SQLAlchemyError:
        raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "No se pudo consultar o guardar la predicción.") from None


@router.get("/tickets/{ticket_id}/prediction")
def obtener(ticket_id: UUID, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_aplicacion(request, escritura=False)
    if request.app.state.motor_bd is None:
        raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "La clasificación no está disponible.")
    try:
        with Session(request.app.state.motor_bd) as db:
            _ticket(db, ticket_id)
            row = db.scalar(select(PrediccionTicket).where(PrediccionTicket.ticket_id == ticket_id)
                .order_by(PrediccionTicket.creado_en.desc(), PrediccionTicket.id.desc()).limit(1))
            return representar(row) if row else None
    except SQLAlchemyError:
        raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "No se pudo consultar la predicción.") from None


@router.post("/tickets/{ticket_id}/prediction")
def crear(ticket_id: UUID, entrada: GeneracionEntrada, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_aplicacion(request, escritura=True)
    return generar_prediccion(request, ticket_id)
