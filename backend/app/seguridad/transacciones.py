from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session


class CodigoSeguridad(StrEnum):
    ORIGIN_INVALIDO = "ORIGIN_INVALIDO"
    IP_NO_VERIFICABLE = "IP_NO_VERIFICABLE"
    RESERVA_INVALIDA = "RESERVA_INVALIDA"
    CONFLICTO_VERSION = "CONFLICTO_VERSION"
    SESION_INEXISTENTE = "SESION_INEXISTENTE"
    SESION_VENCIDA = "SESION_VENCIDA"
    SESION_REVOCADA = "SESION_REVOCADA"
    USUARIO_INEXISTENTE = "USUARIO_INEXISTENTE"
    USUARIO_INACTIVO = "USUARIO_INACTIVO"
    ROL_INVALIDO = "ROL_INVALIDO"
    CONTEXTO_INVALIDO = "CONTEXTO_INVALIDO"
    TOKEN_INVALIDO = "TOKEN_INVALIDO"
    TOKEN_VENCIDO = "TOKEN_VENCIDO"
    LIMITE_TOKENS = "LIMITE_TOKENS"
    TRANSACCION = "TRANSACCION"
    INFRAESTRUCTURA = "INFRAESTRUCTURA"


class ErrorSeguridad(Exception):
    """Código interno tipado; nunca incluye entrada, SQL ni excepción del driver."""

    def __init__(self, codigo: CodigoSeguridad) -> None:
        self.codigo = codigo
        super().__init__(f"Operación de seguridad rechazada: {codigo.value}.")


Reloj = Callable[[Session], datetime]


def reloj_postgresql(db: Session) -> datetime:
    # now() conservaría el inicio de la transacción, incluso tras esperar locks.
    return db.execute(text("SELECT clock_timestamp()")).scalar_one()


def instante(db: Session, reloj: Reloj) -> datetime:
    ahora = reloj(db)
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
    return ahora.astimezone(UTC)


@contextmanager
def operacion_bd(db: Session, *, exigir_transaccion: bool = True) -> Iterator[None]:
    if exigir_transaccion and (not db.in_transaction() or not db.is_active):
        raise ErrorSeguridad(CodigoSeguridad.TRANSACCION)
    try:
        # El llamador hace flush explícito; nunca se envían cambios pendientes
        # antes de adquirir los bloqueos de esta operación por autoflush.
        with db.no_autoflush:
            yield
    except SQLAlchemyError as error:
        estado = getattr(getattr(error, "orig", None), "sqlstate", None)
        codigo = (
            CodigoSeguridad.TRANSACCION
            if isinstance(error, (IntegrityError, InvalidRequestError))
            or estado in {"40001", "40P01", "55P03"}
            else CodigoSeguridad.INFRAESTRUCTURA
        )
        raise ErrorSeguridad(codigo) from None


@contextmanager
def transaccion_seguridad(db: Session) -> Iterator[None]:
    """Commit/rollback del llamador. No anidar sobre un autobegin preexistente.

    Usar resultados de emisión fuera del bloque solo si terminó sin excepción.
    Una Session por petición/hilo; el bloque incluye la futura escritura protegida.
    """
    if db.in_transaction():
        raise ErrorSeguridad(CodigoSeguridad.TRANSACCION)
    with operacion_bd(db, exigir_transaccion=False):
        with db.begin():
            yield
