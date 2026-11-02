from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistencia.base import Base

if TYPE_CHECKING:
    from app.persistencia.modelos.sesion import Sesion
    from app.persistencia.modelos.usuario import Usuario


class LimiteAutenticacion(Base):
    """Estado por ventana; clave_digest debe recibir HMAC-SHA-256 de la identidad.

    La derivación futura usará cuenta normalizada/IP verificada y una clave
    secreta exclusiva del servidor. SHA-256 simple no anonimiza estos datos.
    Este modelo solo almacena los 32 bytes; no implementa su derivación.
    """

    __tablename__ = "limites_autenticacion"
    __table_args__ = (
        CheckConstraint("btrim(tipo_clave) <> ''", name="tipo_clave_no_vacio"),
        CheckConstraint(
            "octet_length(clave_digest) = 32",
            name="clave_digest_longitud",
        ),
        CheckConstraint(
            "ventana_termina_en > ventana_inicia_en",
            name="ventana_valida",
        ),
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        CheckConstraint("reservas >= 0", name="reservas_no_negativas"),
        CheckConstraint("version >= 1", name="version_positiva"),
        CheckConstraint(
            "bloqueado_hasta IS NULL OR bloqueado_hasta >= ventana_inicia_en",
            name="bloqueo_no_anterior",
        ),
        UniqueConstraint(
            "tipo_clave",
            "clave_digest",
            "ventana_inicia_en",
            name="uq_limites_autenticacion_clave_ventana_unica",
        ),
        Index(
            "ix_limites_autenticacion_fin_bloqueo",
            "ventana_termina_en",
            "bloqueado_hasta",
        ),
        Index("ix_limites_autenticacion_actualizado", "actualizado_en"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tipo_clave: Mapped[str] = mapped_column(String(32), nullable=False)
    clave_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ventana_inicia_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ventana_termina_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    intentos: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    reservas: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __mapper_args__ = {"version_id_col": version}


class EventoAutenticacion(Base):
    """Evento mínimo sin credenciales ni cabeceras completas.

    Si se registra una IP verificada, su digest debe ser HMAC-SHA-256 con
    clave secreta exclusiva del servidor, no SHA-256 simple ni IP en claro.
    La derivación y gestión de esa clave quedan fuera de este modelo.
    """

    __tablename__ = "eventos_autenticacion"
    __table_args__ = (
        CheckConstraint("btrim(tipo_evento) <> ''", name="tipo_evento_no_vacio"),
        CheckConstraint("btrim(resultado) <> ''", name="resultado_no_vacio"),
        CheckConstraint(
            "request_id IS NULL OR btrim(request_id) <> ''",
            name="request_id_no_vacio",
        ),
        CheckConstraint(
            "motivo IS NULL OR btrim(motivo) <> ''",
            name="motivo_no_vacio",
        ),
        CheckConstraint(
            "ip_verificada_digest IS NULL OR octet_length(ip_verificada_digest) = 32",
            name="ip_digest_longitud",
        ),
        Index("ix_eventos_autenticacion_fecha_tipo", "ocurrido_en", "tipo_evento"),
        Index("ix_eventos_autenticacion_usuario_fecha", "usuario_id", "ocurrido_en"),
        Index("ix_eventos_autenticacion_sesion_fecha", "sesion_id", "ocurrido_en"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tipo_evento: Mapped[str] = mapped_column(String(64), nullable=False)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    usuario_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    sesion_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sesiones.id", ondelete="SET NULL"),
        nullable=True,
    )
    resultado: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_verificada_digest: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )

    usuario: Mapped["Usuario | None"] = relationship(
        back_populates="eventos_autenticacion"
    )
    sesion: Mapped["Sesion | None"] = relationship()
