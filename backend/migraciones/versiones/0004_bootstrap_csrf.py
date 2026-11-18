"""Contadores de bootstrap separados del login, sin eventos por petición.

Revision ID: 0004_bootstrap_csrf
Revises: 0003_retirar_prioridad_critical
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_bootstrap_csrf"
down_revision = "0003_retirar_prioridad_critical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cuotas_bootstrap_csrf",
        sa.Column("ambito", sa.String(24), nullable=False),
        sa.Column("identidad", sa.LargeBinary(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usados", sa.Integer(), nullable=False),
        sa.CheckConstraint("ambito IN ('contextos_ip', 'contextos_global', 'intentos_ip', "
                           "'intentos_global', 'emisiones_contexto')", name=op.f("ck_cuotas_bootstrap_csrf_ambito_valido")),
        sa.CheckConstraint("octet_length(identidad) = 32", name=op.f("ck_cuotas_bootstrap_csrf_identidad_longitud")),
        sa.CheckConstraint("fin > inicio", name=op.f("ck_cuotas_bootstrap_csrf_ventana_valida")),
        sa.CheckConstraint("usados > 0 AND usados <= 1000000", name=op.f("ck_cuotas_bootstrap_csrf_usados_validos")),
        sa.PrimaryKeyConstraint("ambito", "identidad", name=op.f("pk_cuotas_bootstrap_csrf")),
    )
    op.create_index("ix_cuotas_bootstrap_csrf_fin", "cuotas_bootstrap_csrf", ["fin"])


def downgrade() -> None:
    op.drop_index("ix_cuotas_bootstrap_csrf_fin", table_name="cuotas_bootstrap_csrf")
    op.drop_table("cuotas_bootstrap_csrf")
