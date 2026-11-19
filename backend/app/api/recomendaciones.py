"""API de borradores con revisión humana; deshabilitada salvo configuración explícita."""

from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.persistencia.modelos.recomendacion import Recomendacion, RevisionRecomendacion
from app.persistencia.modelos.ticket import Ticket
from app.recuperacion.servicio import ErrorRecuperacion
from app.recomendaciones.acceso import identidad_recomendaciones
from app.recomendaciones.generacion import MODEL, PROMPT_VERSION, generar

router = APIRouter()


class RevisionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: str
    modifiedContent: str | None = Field(default=None, max_length=10000)
    feedback: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validar(self):
        if self.decision not in {"accepted", "modified", "rejected"}:
            raise ValueError("La decisión no es válida.")
        if self.decision == "modified" and not (self.modifiedContent or "").strip():
            raise ValueError("La modificación requiere contenido.")
        if self.decision != "modified" and self.modifiedContent is not None:
            raise ValueError("Solo la modificación admite contenido editado.")
        return self


class GeneracionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _disponible(request, *, generar_nueva: bool = False):
    config = request.app.state.configuracion
    if not config.rag_enabled or request.app.state.motor_bd is None:
        raise ErrorRecuperacion("RECOMMENDATIONS_UNAVAILABLE", "Las recomendaciones no están disponibles.")
    if generar_nueva and (request.app.state.recuperacion is None or not config.gemini_api_key
                         or not config.gemini_api_key.get_secret_value() or not config.rag_external_data_approved):
        raise ErrorRecuperacion("RECOMMENDATIONS_UNAVAILABLE", "La generación todavía no está preparada.")
    return request.app.state.motor_bd


def _representar(row: Recomendacion, review: RevisionRecomendacion | None = None) -> dict:
    return {"id": str(row.id), "ticketId": str(row.ticket_id), "content": row.contenido,
            "status": row.estado, "sources": row.fuentes,
            "createdAt": row.creado_en.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "review": ({"decision": review.decision, "modifiedContent": review.contenido_modificado,
                        "feedback": review.comentario,
                        "reviewedAt": review.revisado_en.astimezone(UTC).isoformat().replace("+00:00", "Z")}
                       if review else None)}


def _ticket(db: Session, ticket_id: UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise ErrorRecuperacion("TICKET_NOT_FOUND", "El ticket no existe.", 404)
    return ticket


@router.get("/tickets/{ticket_id}/recommendations")
def listar(ticket_id: UUID, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_recomendaciones(request, escritura=False)
    motor = _disponible(request)
    try:
        with Session(motor) as db:
            _ticket(db, ticket_id)
            rows = db.scalars(select(Recomendacion).where(Recomendacion.ticket_id == ticket_id)
                              .order_by(Recomendacion.creado_en.desc(), Recomendacion.id.desc())).all()
            ids = [row.id for row in rows if row.estado != "pending"]
            reviews = {review.recomendacion_id: review for review in
                       db.scalars(select(RevisionRecomendacion).where(
                           RevisionRecomendacion.recomendacion_id.in_(ids))).all()} if ids else {}
            return [_representar(row, reviews.get(row.id)) for row in rows]
    except SQLAlchemyError:
        raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudieron consultar las recomendaciones.") from None


@router.get("/recommendations/{recommendation_id}")
def obtener(recommendation_id: UUID, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_recomendaciones(request, escritura=False)
    motor = _disponible(request)
    try:
        with Session(motor) as db:
            row = db.get(Recomendacion, recommendation_id)
            if row is None:
                raise ErrorRecuperacion("RECOMMENDATION_NOT_FOUND", "La recomendación no existe.", 404)
            review = db.scalar(select(RevisionRecomendacion).where(
                RevisionRecomendacion.recomendacion_id == row.id)) if row.estado != "pending" else None
            return _representar(row, review)
    except SQLAlchemyError:
        raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo consultar la recomendación.") from None


@router.post("/tickets/{ticket_id}/recommendations", status_code=201)
def crear(ticket_id: UUID, entrada: GeneracionEntrada, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_recomendaciones(request, escritura=True)
    motor = _disponible(request, generar_nueva=True)
    config = request.app.state.configuracion
    try:
        with Session(motor) as db:
            ticket = _ticket(db, ticket_id)
            if db.scalar(select(Recomendacion.id).where(Recomendacion.ticket_id == ticket_id,
                                                      Recomendacion.estado == "pending").limit(1)):
                raise ErrorRecuperacion("RECOMMENDATION_PENDING", "Revisa el borrador pendiente antes de generar otro.", 409)
            query = f"{ticket.titulo}\n{ticket.descripcion}"[:1000]
        result = generar(query, request.app.state.recuperacion,
                         api_key=config.gemini_api_key.get_secret_value(),
                         timeout=config.rag_timeout_seconds, max_chunks=config.rag_max_context_chunks,
                         search_query=f"{ticket.titulo} {ticket.descripcion[:220]}")
        if result is None:
            raise ErrorRecuperacion("INSUFFICIENT_INFORMATION", "No hay evidencia suficiente para recomendar pasos.", 422)
        content, sources = result
        source_data = [{key: str(value) if isinstance(value, UUID) else value
                        for key, value in item.items() if key in {
                            "documentId", "documentChunkId", "title", "excerpt", "score", "sourceUrl"}}
                       for item in sources]
        with Session(motor) as db, db.begin():
            _ticket(db, ticket_id)
            row = Recomendacion(ticket_id=ticket_id, contenido=content, estado="pending",
                                fuentes=source_data, proveedor="Google Gemini API", modelo=MODEL,
                                version_prompt=PROMPT_VERSION)
            db.add(row)
            db.flush()
            db.refresh(row)
            output = _representar(row)
        return output
    except IntegrityError:
        raise ErrorRecuperacion("RECOMMENDATION_PENDING", "Ya existe un borrador pendiente.", 409) from None
    except SQLAlchemyError:
        raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo guardar la recomendación.") from None


@router.post("/recommendations/{recommendation_id}/reviews", status_code=204)
def revisar(recommendation_id: UUID, entrada: RevisionEntrada, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identity = identidad_recomendaciones(request, escritura=True)
    motor = _disponible(request)
    try:
        with Session(motor) as db, db.begin():
            row = db.scalar(select(Recomendacion).where(Recomendacion.id == recommendation_id).with_for_update())
            if row is None:
                raise ErrorRecuperacion("RECOMMENDATION_NOT_FOUND", "La recomendación no existe.", 404)
            if row.estado != "pending":
                raise ErrorRecuperacion("RECOMMENDATION_ALREADY_REVIEWED", "La recomendación ya fue revisada.", 409)
            row.estado = entrada.decision
            db.add(RevisionRecomendacion(recomendacion_id=row.id, revisor_id=identity.id,
                                         decision=entrada.decision,
                                         contenido_modificado=entrada.modifiedContent.strip() if entrada.modifiedContent else None,
                                         comentario=entrada.feedback.strip() if entrada.feedback else None))
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    except IntegrityError:
        raise ErrorRecuperacion("RECOMMENDATION_ALREADY_REVIEWED", "La recomendación ya fue revisada.", 409) from None
    except SQLAlchemyError:
        raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo guardar la revisión.") from None
