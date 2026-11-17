"""Representaciones internas compatibles con Ticket de frontend.

Los límites de paginación, el conteo Unicode y extra=forbid son candidatos de
integración, no una ratificación de los pendientes del contrato público.
"""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


EstadoTicket = Literal["open", "in_progress", "resolved", "closed"]
PrioridadTicket = Literal["low", "medium", "high"]


class EsquemaTicket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class TicketCreate(EsquemaTicket):
    title: str = Field(repr=False)
    description: str = Field(repr=False)

    @field_validator("title", "description")
    @classmethod
    def validar_texto(cls, value: str, info) -> str:
        # Cuenta unidades UTF-16 como string.length del formulario existente.
        # Su adopción pública y el tratamiento de campos extra siguen pendientes.
        value = value.strip()
        try:
            value.encode("utf-8")
            length = len(value.encode("utf-16-le")) // 2
        except UnicodeError:
            raise ValueError("El texto debe ser Unicode válido.") from None
        minimum, maximum = (5, 150) if info.field_name == "title" else (10, 5000)
        if "\x00" in value or not minimum <= length <= maximum:
            raise ValueError(f"El texto recortado debe tener entre {minimum} y {maximum} unidades UTF-16.")
        return value


class TicketPagination(EsquemaTicket):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class TicketStatusUpdate(EsquemaTicket):
    status: EstadoTicket


class UsuarioTicket(EsquemaTicket):
    """Proyección User de TS; excluye hashes, credenciales y relaciones privadas."""

    id: UUID
    name: str
    email: str
    role: Literal["admin", "agent"]
    isActive: bool
    createdAt: AwareDatetime
    updatedAt: AwareDatetime


class Ticket(EsquemaTicket):
    id: UUID
    title: str = Field(repr=False)
    description: str = Field(repr=False)
    status: EstadoTicket
    priority: PrioridadTicket
    category: str | None
    area: str | None
    createdBy: UsuarioTicket
    assignedTo: UsuarioTicket | None
    createdAt: AwareDatetime
    updatedAt: AwareDatetime
    resolvedAt: AwareDatetime | None


class TicketList(EsquemaTicket):
    items: tuple[Ticket, ...]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class TicketSummary(EsquemaTicket):
    """Conteos reales; no pretende implementar el DTO Metrics completo."""

    totalTickets: int = Field(ge=0)
    openTickets: int = Field(ge=0)
    inProgressTickets: int = Field(ge=0)
    resolvedTickets: int = Field(ge=0)
    closedTickets: int = Field(ge=0)
