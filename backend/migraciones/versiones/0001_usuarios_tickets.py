"""Crear las tablas iniciales de usuarios y tickets.

Revisión: 0001_usuarios_tickets
Revisión anterior: ninguna
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0001_usuarios_tickets"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=False),
        sa.Column("hash_contrasena", sa.Text(), nullable=False),
        sa.Column("rol", sa.String(16), server_default=sa.text("'agent'"), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rol IN ('admin', 'agent')", name=op.f("ck_usuarios_rol_valido")),
        sa.CheckConstraint("btrim(nombre) <> ''", name=op.f("ck_usuarios_nombre_no_vacio")),
        sa.CheckConstraint("btrim(correo) <> ''", name=op.f("ck_usuarios_correo_no_vacio")),
        sa.CheckConstraint("correo = lower(btrim(correo))", name=op.f("ck_usuarios_correo_normalizado")),
        sa.CheckConstraint("btrim(hash_contrasena) <> ''", name=op.f("ck_usuarios_hash_no_vacio")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("correo", name=op.f("uq_usuarios_correo")),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("prioridad", sa.String(16), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=True),
        sa.Column("area", sa.Text(), nullable=True),
        sa.Column("creado_por_id", sa.Uuid(), nullable=False),
        sa.Column("asignado_a_id", sa.Uuid(), nullable=True),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estado IN ('open', 'in_progress', 'resolved', 'closed')", name=op.f("ck_tickets_estado_valido")),
        sa.CheckConstraint("prioridad IN ('low', 'medium', 'high', 'critical')", name=op.f("ck_tickets_prioridad_valida")),
        sa.CheckConstraint("btrim(titulo) <> ''", name=op.f("ck_tickets_titulo_no_vacio")),
        sa.CheckConstraint("btrim(descripcion) <> ''", name=op.f("ck_tickets_descripcion_no_vacia")),
        sa.ForeignKeyConstraint(["creado_por_id"], ["usuarios.id"], ondelete="RESTRICT", name=op.f("fk_tickets_creado_por_id_usuarios")),
        sa.ForeignKeyConstraint(["asignado_a_id"], ["usuarios.id"], ondelete="RESTRICT", name=op.f("fk_tickets_asignado_a_id_usuarios")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index("ix_tickets_creado_por_id", "tickets", ["creado_por_id"])
    op.create_index("ix_tickets_asignado_a_id", "tickets", ["asignado_a_id"])
    op.create_index("ix_tickets_estado_creado_en", "tickets", ["estado", "creado_en"])


def downgrade() -> None:
    op.drop_index("ix_tickets_estado_creado_en", table_name="tickets")
    op.drop_index("ix_tickets_asignado_a_id", table_name="tickets")
    op.drop_index("ix_tickets_creado_por_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("usuarios")
