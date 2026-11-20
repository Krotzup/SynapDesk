"""Persistencia de predicciones sin alterar la clasificación validada."""
from alembic import op
import sqlalchemy as sa

revision = "0008_predicciones_ticket"
down_revision = "0007_recomendaciones_rag"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("predicciones_ticket",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticket_id", "huella", name="uq_predicciones_ticket_huella"))
    op.create_index("ix_predicciones_ticket_ticket_id", "predicciones_ticket", ["ticket_id"])


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM predicciones_ticket) THEN RAISE EXCEPTION 'Conservar historial ML antes de retirar'; END IF; END $$")
    op.drop_table("predicciones_ticket")
