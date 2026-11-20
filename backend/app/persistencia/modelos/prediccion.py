"""Predicción orientativa separada de los valores confirmados del ticket."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.persistencia.base import Base


class PrediccionTicket(Base):
    __tablename__ = "predicciones_ticket"
    __table_args__ = (UniqueConstraint("ticket_id", "huella", name="uq_predicciones_ticket_huella"),)

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, server_default=text("gen_random_uuid()"))
    ticket_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("tickets.id", ondelete="RESTRICT"), index=True)
    huella: Mapped[str] = mapped_column(String(64), nullable=False)
    resultado: Mapped[dict] = mapped_column(JSON, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
