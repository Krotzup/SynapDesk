"""Borradores RAG y una revisión humana inmutable por recomendación."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistencia.base import Base


class Recomendacion(Base):
    __tablename__ = "recomendaciones"
    __table_args__ = (
        CheckConstraint("estado IN ('pending','accepted','modified','rejected')", name="estado_valido"),
        Index("ix_recomendaciones_ticket_creado", "ticket_id", "creado_en"),
        Index("uq_recomendaciones_ticket_pending", "ticket_id", unique=True,
              postgresql_where=text("estado = 'pending'")),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ticket_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    fuentes: Mapped[list] = mapped_column(JSON, nullable=False)
    proveedor: Mapped[str] = mapped_column(String(32), nullable=False)
    modelo: Mapped[str] = mapped_column(String(80), nullable=False)
    version_prompt: Mapped[str] = mapped_column(String(32), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RevisionRecomendacion(Base):
    __tablename__ = "revisiones_recomendacion"
    __table_args__ = (CheckConstraint("decision IN ('accepted','modified','rejected')", name="decision_valida"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    recomendacion_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("recomendaciones.id", ondelete="RESTRICT"), nullable=False, unique=True)
    revisor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    contenido_modificado: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str | None] = mapped_column(Text)
    revisado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
