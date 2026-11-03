"""Eventos mínimos: catálogo cerrado y ningún campo de texto libre."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistencia.modelos import EventoAutenticacion
from app.seguridad.proxies import IpVerificada
from app.seguridad.transacciones import Reloj, instante, operacion_bd, reloj_postgresql


class TipoEvento(StrEnum):
    LOGIN = "login"
    BLOQUEO = "rate_limit"
    SESION_CREADA = "session_created"
    SESION_REVOCADA = "session_revoked"
    VALIDACION = "validation"


class ResultadoEvento(StrEnum):
    EXITO = "success"
    RECHAZO = "failure"


class MotivoEvento(StrEnum):
    CREDENCIALES_VALIDAS = "credentials_validated"
    CREDENCIALES_INVALIDAS = "credentials_rejected"
    LIMITE = "rate_limited"
    ORIGIN = "origin_invalid"
    IP = "ip_unverified"
    CSRF = "csrf_invalid"
    SESION_INVALIDA = "session_invalid"
    CREACION = "session_created"
    LOGOUT = "logout"
    REEMPLAZO = "session_replaced"
    INFRAESTRUCTURA = "security_unavailable"


@dataclass(frozen=True)
class EventoPreparado:
    """Identificador provisional, no comprobante de commit."""

    id: UUID


class ServicioAuditoria:
    def __init__(self, db: Session, reloj: Reloj = reloj_postgresql) -> None:
        self.db = db
        self.reloj = reloj

    def registrar(self, *, tipo: TipoEvento, resultado: ResultadoEvento,
                  motivo: MotivoEvento | None = None, request_id: UUID | None = None,
                  usuario_id: UUID | None = None, sesion_id: UUID | None = None,
                  ip: IpVerificada | None = None) -> EventoPreparado:
        # Exigir enums reales: no aceptar cualquier str aunque StrEnum lo compare
        # igual. El request ID es un UUID del servidor, no un header sin filtrar.
        if (not isinstance(tipo, TipoEvento) or not isinstance(resultado, ResultadoEvento)
                or (motivo is not None and not isinstance(motivo, MotivoEvento))
                or any(valor is not None and not isinstance(valor, UUID)
                       for valor in (request_id, usuario_id, sesion_id))
                or (ip is not None and not isinstance(ip, IpVerificada))):
            raise ValueError("Evento de autenticación inválido.")
        with operacion_bd(self.db):
            evento = EventoAutenticacion(
                tipo_evento=tipo.value, resultado=resultado.value,
                motivo=motivo.value if motivo is not None else None,
                request_id=str(request_id) if request_id is not None else None,
                usuario_id=usuario_id, sesion_id=sesion_id,
                ip_verificada_digest=ip.digest if ip is not None else None,
                ocurrido_en=instante(self.db, self.reloj),
            )
            self.db.add(evento)
            self.db.flush()
            return EventoPreparado(evento.id)
