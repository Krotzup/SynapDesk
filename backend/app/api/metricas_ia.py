"""HU10 optativa: conteos globales de revisiones, sin contenido ni datos personales."""
from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.persistencia.modelos.recomendacion import RevisionRecomendacion
from app.recomendaciones.acceso import identidad_aplicacion
from app.recuperacion.servicio import ErrorRecuperacion

router = APIRouter()
DECISIONES = {"accepted": "recommendationsAccepted", "modified": "recommendationsModified",
              "rejected": "recommendationsRejected"}


def contar_revisiones(db):
    # Un solo snapshot; contar revisiones inmutables, no estados de borradores.
    row = db.execute(select(*(func.count().filter(RevisionRecomendacion.decision == decision)
                             for decision in DECISIONES))).one()
    return dict(zip(DECISIONES.values(), row))


@router.get("/metrics/recommendations")
def resumen(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_aplicacion(request, escritura=False)
    motor = request.app.state.motor_bd
    if motor is None:
        raise ErrorRecuperacion("METRICS_UNAVAILABLE", "Las métricas de revisiones no están disponibles.")
    try:
        with Session(motor) as db:
            return contar_revisiones(db)
    except SQLAlchemyError:
        raise ErrorRecuperacion("METRICS_UNAVAILABLE", "No se pudieron consultar las revisiones.") from None
