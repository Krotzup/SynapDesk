from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistencia.base import Base

if TYPE_CHECKING:
    from app.persistencia.modelos.usuario import Usuario


class Sesion(Base):
    """Sesión opaca persistida sin almacenar su secreto portador."""

    __tablename__ = "sesiones"
    __table_args__ = (
        CheckConstraint(
            "octet_length(digest_credencial) = 32",
            name="digest_credencial_longitud",
        ),
        CheckConstraint(
            "ultima_actividad >= creado_en AND expira_en > creado_en",
            name="fechas_vigencia_validas",
        ),
        CheckConstraint(
            "ultima_actividad <= expira_en",
            name="actividad_no_supera_expiracion",
        ),
        CheckConstraint(
            "revocada_en IS NULL OR revocada_en >= creado_en",
            name="revocacion_no_anterior",
        ),
        CheckConstraint(
            "motivo_revocacion IS NULL OR btrim(motivo_revocacion) <> ''",
            name="motivo_revocacion_no_vacio",
        ),
        Index("ix_sesiones_usuario_revocada", "usuario_id", "revocada_en"),
        Index("ix_sesiones_expiracion_revocada", "expira_en", "revocada_en"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    digest_credencial: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ultima_actividad: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    motivo_revocacion: Mapped[str | None] = mapped_column(String(64), nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="sesiones")
    contextos_csrf: Mapped[list["ContextoCsrf"]] = relationship(
        back_populates="sesion"
    )
