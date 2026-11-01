from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.persistencia.base import Base
from app.persistencia.modelos.comunes import FechasRegistro


class Usuario(FechasRegistro, Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'agent')", name="rol_valido"),
        CheckConstraint("btrim(nombre) <> ''", name="nombre_no_vacio"),
        CheckConstraint("btrim(correo) <> ''", name="correo_no_vacio"),
        CheckConstraint("correo = lower(btrim(correo))", name="correo_normalizado"),
        CheckConstraint("btrim(hash_contrasena) <> ''", name="hash_no_vacio"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    correo: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    hash_contrasena: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'agent'")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    @validates("correo")
    def normalizar_correo(self, nombre_atributo: str, valor: str) -> str:
        return valor.strip().lower()
