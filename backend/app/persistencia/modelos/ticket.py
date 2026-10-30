from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistencia.base import Base
from app.persistencia.modelos.comunes import FechasRegistro

if TYPE_CHECKING:
    from app.persistencia.modelos.usuario import Usuario


class Ticket(FechasRegistro, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('open', 'in_progress', 'resolved', 'closed')",
            name="estado_valido",
        ),
        CheckConstraint(
            "prioridad IN ('low', 'medium', 'high', 'critical')",
            name="prioridad_valida",
        ),
        CheckConstraint("btrim(titulo) <> ''", name="titulo_no_vacio"),
        CheckConstraint("btrim(descripcion) <> ''", name="descripcion_no_vacia"),
        Index("ix_tickets_estado_creado_en", "estado", "creado_en"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'open'")
    )
    prioridad: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'medium'")
    )
    categoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    area: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asignado_a_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    creador: Mapped["Usuario"] = relationship(foreign_keys=[creado_por_id])
    asignado_a: Mapped["Usuario | None"] = relationship(foreign_keys=[asignado_a_id])
