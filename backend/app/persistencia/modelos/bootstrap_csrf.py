"""Una fila reciclable por ámbito/identidad, independiente del login."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.persistencia.base import Base


class CuotaBootstrapCsrf(Base):
    __tablename__ = "cuotas_bootstrap_csrf"
    __table_args__ = (
        CheckConstraint("ambito IN ('contextos_ip', 'contextos_global', 'intentos_ip', "
                        "'intentos_global', 'emisiones_contexto')", name="ambito_valido"),
        CheckConstraint("octet_length(identidad) = 32", name="identidad_longitud"),
        CheckConstraint("fin > inicio", name="ventana_valida"),
        CheckConstraint("usados > 0 AND usados <= 1000000", name="usados_validos"),
        Index("ix_cuotas_bootstrap_csrf_fin", "fin"),
    )

    ambito: Mapped[str] = mapped_column(String(24), primary_key=True)
    identidad: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usados: Mapped[int] = mapped_column(nullable=False)
