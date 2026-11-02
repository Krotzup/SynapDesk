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
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistencia.base import Base

if TYPE_CHECKING:
    from app.persistencia.modelos.sesion import Sesion


class ContextoCsrf(Base):
    """Identidad de contexto independiente de la identidad de sesión."""

    __tablename__ = "contextos_csrf"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('anonymous', 'authenticated')",
            name="tipo_valido",
        ),
        CheckConstraint(
            "((tipo = 'anonymous' AND digest_secreto IS NOT NULL AND sesion_id IS NULL) "
            "OR (tipo = 'authenticated' AND digest_secreto IS NULL AND sesion_id IS NOT NULL))",
            name="vinculacion_tipo_consistente",
        ),
        CheckConstraint(
            "digest_secreto IS NULL OR octet_length(digest_secreto) = 32",
            name="digest_secreto_longitud",
        ),
        CheckConstraint("expira_en > creado_en", name="fechas_vigencia_validas"),
        CheckConstraint(
            "revocado_en IS NULL OR revocado_en >= creado_en",
            name="revocacion_no_anterior",
        ),
        Index("ix_contextos_csrf_sesion_revocado", "sesion_id", "revocado_en"),
        Index("ix_contextos_csrf_expiracion_revocado", "expira_en", "revocado_en"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    digest_secreto: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, unique=True
    )
    sesion_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sesiones.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sesion: Mapped["Sesion | None"] = relationship(back_populates="contextos_csrf")
    tokens: Mapped[list["TokenCsrf"]] = relationship(back_populates="contexto")


class TokenCsrf(Base):
    """Token CSRF almacenado únicamente por su digest."""

    __tablename__ = "tokens_csrf"
    __table_args__ = (
        CheckConstraint(
            "octet_length(digest_token) = 32",
            name="digest_token_longitud",
        ),
        CheckConstraint("expira_en > emitido_en", name="fechas_vigencia_validas"),
        CheckConstraint(
            "invalidado_en IS NULL OR invalidado_en >= emitido_en",
            name="invalidacion_no_anterior",
        ),
        Index(
            "ix_tokens_csrf_contexto_vigencia",
            "contexto_id",
            "expira_en",
            "invalidado_en",
            "emitido_en",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contexto_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contextos_csrf.id", ondelete="RESTRICT"),
        nullable=False,
    )
    digest_token: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True
    )
    emitido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invalidado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contexto: Mapped["ContextoCsrf"] = relationship(back_populates="tokens")
