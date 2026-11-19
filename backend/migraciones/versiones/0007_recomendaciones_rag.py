"""Borradores RAG y revisiones humanas; el contenido original permanece intacto."""

from alembic import op
import sqlalchemy as sa

revision = "0007_recomendaciones_rag"
down_revision = "0006_user_created"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recomendaciones",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("fuentes", sa.JSON(), nullable=False),
        sa.Column("proveedor", sa.String(32), nullable=False),
        sa.Column("modelo", sa.String(80), nullable=False),
        sa.Column("version_prompt", sa.String(32), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("estado IN ('pending','accepted','modified','rejected')", name=op.f("ck_recomendaciones_estado_valido")),
    )
    op.create_index("ix_recomendaciones_ticket_creado", "recomendaciones", ["ticket_id", "creado_en"])
    op.create_index("uq_recomendaciones_ticket_pending", "recomendaciones", ["ticket_id"],
                    unique=True, postgresql_where=sa.text("estado = 'pending'"))
    op.create_table(
        "revisiones_recomendacion",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recomendacion_id", sa.Uuid(), sa.ForeignKey("recomendaciones.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("revisor_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("contenido_modificado", sa.Text()),
        sa.Column("comentario", sa.Text()),
        sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('accepted','modified','rejected')", name=op.f("ck_revisiones_recomendacion_decision_valida")),
    )


def downgrade() -> None:
    # Preservar decisiones y texto humano: no borrar historial de producción.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM revisiones_recomendacion) OR EXISTS (SELECT 1 FROM recomendaciones) THEN RAISE EXCEPTION 'No se puede retirar historial de recomendaciones'; END IF; END $$")
    op.drop_table("revisiones_recomendacion")
    op.drop_index("ix_recomendaciones_ticket_creado", table_name="recomendaciones")
    op.drop_index("uq_recomendaciones_ticket_pending", table_name="recomendaciones")
    op.drop_table("recomendaciones")
