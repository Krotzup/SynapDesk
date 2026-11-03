"""Cuotas persistentes conservadoras sobre el esquema AUTH-05 existente."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import ceil
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.configuracion import Configuracion
from app.persistencia.modelos import LimiteAutenticacion
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.origenes import ErrorConfiguracionSeguridad
from app.seguridad.proxies import IpVerificada
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, Reloj, instante, operacion_bd, reloj_postgresql,
)

T = TypeVar("T")


@dataclass(frozen=True)
class PoliticaLimite:
    intentos: int
    ventana: timedelta
    bloqueo: timedelta


@dataclass(frozen=True)
class ReferenciaLimite:
    id: UUID
    tipo: str
    digest: bytes = field(repr=False)
    inicio: datetime


@dataclass(frozen=True)
class ReservaIntento:
    id: UUID
    limites: tuple[ReferenciaLimite, ...] = field(repr=False)
    vence_en: datetime


@dataclass(frozen=True)
class DecisionLimite:
    permitido: bool
    observado_en: datetime
    reintentar_en: datetime | None = None
    reserva: ReservaIntento | None = field(default=None, repr=False)

    @property
    def codigo(self) -> str | None:
        return None if self.permitido else "RATE_LIMITED"

    @property
    def retry_after(self) -> int | None:
        if self.reintentar_en is None:
            return None
        return ceil((self.reintentar_en - self.observado_en).total_seconds())


def _digest_reserva(reserva_id: UUID, limites: tuple[ReferenciaLimite, ...]) -> bytes:
    # Referencias internas aleatorias, nunca cuenta/IP ni credenciales portadoras.
    return hashlib.sha256(b"synapdesk:reserva:v1\0" + reserva_id.bytes + b"".join(
        limite.tipo.encode("ascii") + b"\0" + limite.digest + limite.id.bytes
        + limite.inicio.isoformat().encode("ascii") for limite in limites
    )).digest()


class ServicioLimites:
    def __init__(self, db: Session, configuracion: Configuracion,
                 identificadores: ServicioIdentificadores, reloj: Reloj = reloj_postgresql) -> None:
        self.db = db
        self.identificadores = identificadores
        self.reloj = reloj
        self.reintentos = configuracion.auth_limite_reintentos_version
        self.politicas = {}
        for tipo in ("cuenta", "ip"):
            cuota = getattr(configuracion, f"auth_limite_{tipo}_intentos")
            ventana = getattr(configuracion, f"auth_limite_{tipo}_ventana_segundos")
            bloqueo = getattr(configuracion, f"auth_limite_{tipo}_bloqueo_segundos")
            if cuota is None or ventana is None or bloqueo is None:
                raise ErrorConfiguracionSeguridad("Falta configurar las cuotas de autenticación.")
            self.politicas[tipo] = PoliticaLimite(cuota, timedelta(seconds=ventana),
                                                 timedelta(seconds=bloqueo))

    def _operar(self, operacion: Callable[[], T]) -> T:
        with operacion_bd(self.db):
            # begin_nested hace flush incluso con no_autoflush. Nunca incluir
            # escrituras ajenas en el savepoint o repetir efectos del llamador.
            if self.db.new or self.db.dirty or self.db.deleted:
                raise ErrorSeguridad(C.TRANSACCION)
            for numero in range(self.reintentos + 1):
                try:
                    with self.db.begin_nested():
                        return operacion()
                except StaleDataError:
                    # Rollback del savepoint; nueva lectura y reloj, sin repetir
                    # Argon2, auditoría ni escrituras de sesión.
                    if numero == self.reintentos:
                        raise ErrorSeguridad(C.CONFLICTO_VERSION) from None
        raise ErrorSeguridad(C.INFRAESTRUCTURA)  # Defensa frente a configuración alterada.

    def _bloquear(self, claves: list[tuple[str, bytes]]) -> None:
        # El advisory lock cubre también la ausencia de filas y el cambio de
        # ventana. Una colisión de 64 bits solo serializa identidades adicionales.
        llaves = {int.from_bytes(hashlib.sha256(
                b"synapdesk:limite:v1\0" + tipo.encode("ascii") + digest,
            ).digest()[:8], "big", signed=True) for tipo, digest in claves}
        for llave in sorted(llaves):
            self.db.execute(text("SELECT pg_advisory_xact_lock(:llave)"), {"llave": llave})

    def _filas(self, claves: list[tuple[str, bytes]]) -> list[LimiteAutenticacion | None]:
        return [self.db.scalars(select(LimiteAutenticacion).where(
            LimiteAutenticacion.tipo_clave == tipo,
            LimiteAutenticacion.clave_digest == digest,
        ).with_for_update().execution_options(populate_existing=True)).one_or_none()
                for tipo, digest in sorted(claves)]

    def reservar(self, *, cuenta: str, ip: IpVerificada) -> DecisionLimite:
        if not isinstance(ip, IpVerificada):
            raise ErrorSeguridad(C.IP_NO_VERIFICABLE)
        claves = [("cuenta", self.identificadores.cuenta(cuenta)), ("ip", ip.digest)]

        def ejecutar() -> DecisionLimite:
            self._bloquear(claves)
            filas = self._filas(claves)
            ahora = instante(self.db, self.reloj)
            limites = []
            for (tipo, digest), fila in zip(sorted(claves), filas, strict=True):
                politica = self.politicas[tipo]
                if fila is None:
                    fila = LimiteAutenticacion(
                        tipo_clave=tipo, clave_digest=digest, ventana_inicia_en=ahora,
                        ventana_termina_en=ahora + politica.ventana,
                        intentos=0, reservas=0, actualizado_en=ahora,
                    )
                elif ahora >= max(fila.ventana_termina_en,
                                 fila.bloqueado_hasta or fila.ventana_termina_en):
                    # Reservas abandonadas caducan junto con la ventana. Nunca
                    # se extiende un bloqueo por repetir un intento rechazado.
                    fila.ventana_inicia_en = ahora
                    fila.ventana_termina_en = ahora + politica.ventana
                    fila.intentos = fila.reservas = 0
                    fila.bloqueado_hasta = None
                limites.append(fila)

            esperas = [max(fila.ventana_termina_en, fila.bloqueado_hasta or ahora)
                       for fila in limites if fila.intentos + fila.reservas >=
                       self.politicas[fila.tipo_clave].intentos or
                       (fila.bloqueado_hasta is not None and fila.bloqueado_hasta > ahora)]
            if esperas:
                self.db.flush()
                return DecisionLimite(False, ahora, max(esperas))

            for fila in limites:
                # Un rechazo por la otra clave no crea filas para identidades
                # nuevas ni comprobantes de reserva.
                self.db.add(fila)
                fila.reservas += 1
                fila.actualizado_en = ahora
                if fila.intentos + fila.reservas == self.politicas[fila.tipo_clave].intentos:
                    fila.bloqueado_hasta = ahora + self.politicas[fila.tipo_clave].bloqueo
            self.db.flush()
            referencias = tuple(ReferenciaLimite(fila.id, fila.tipo_clave, fila.clave_digest,
                                                fila.ventana_inicia_en) for fila in limites)
            reserva = ReservaIntento(uuid4(), referencias,
                                     min(fila.ventana_termina_en for fila in limites))
            # Comprobante por intento en el MISMO modelo: abierto=reservas 1,
            # consolidado=intentos 1. Vincula el recibo a ambas filas/ventanas;
            # evita consolidar dos veces o liberar la reserva de otra petición.
            self.db.add(LimiteAutenticacion(
                id=reserva.id, tipo_clave="reserva", clave_digest=_digest_reserva(reserva.id, referencias),
                ventana_inicia_en=ahora, ventana_termina_en=reserva.vence_en,
                intentos=0, reservas=1, actualizado_en=ahora,
            ))
            self.db.flush()
            return DecisionLimite(True, ahora, reserva=reserva)

        return self._operar(ejecutar)

    def consolidar(self, reserva: ReservaIntento) -> bool:
        """Todos los intentos reservados consumen cuota, incluso éxitos/caídas.

        Sin devolución de capacidad ni reset por éxito. Si caducó o ya fue
        consolidada devuelve false. No autoriza continuar una operación vencida.
        """
        if not isinstance(reserva, ReservaIntento) or len(reserva.limites) != 2:
            raise ErrorSeguridad(C.RESERVA_INVALIDA)

        def ejecutar() -> bool:
            claves = [(ref.tipo, ref.digest) for ref in reserva.limites]
            self._bloquear(claves)
            filas = self._filas(claves)
            recibo = self.db.scalar(select(LimiteAutenticacion).where(
                LimiteAutenticacion.id == reserva.id, LimiteAutenticacion.tipo_clave == "reserva",
            ).with_for_update().execution_options(populate_existing=True))
            ahora = instante(self.db, self.reloj)
            if recibo is None or recibo.clave_digest != _digest_reserva(reserva.id, reserva.limites):
                raise ErrorSeguridad(C.RESERVA_INVALIDA)
            if recibo.reservas == 0 or ahora >= recibo.ventana_termina_en:
                return False
            for ref, fila in zip(reserva.limites, filas, strict=True):
                if (fila is None or fila.id != ref.id or fila.ventana_inicia_en != ref.inicio
                        or fila.reservas < 1):
                    raise ErrorSeguridad(C.RESERVA_INVALIDA)
                fila.reservas -= 1
                fila.intentos += 1
                fila.actualizado_en = ahora
            recibo.reservas = 0
            recibo.intentos = 1
            recibo.actualizado_en = ahora
            self.db.flush()
            return True

        return self._operar(ejecutar)
