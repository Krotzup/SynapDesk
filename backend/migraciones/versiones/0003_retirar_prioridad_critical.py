"""Retira critical del catálogo y conserva sus tickets como high.

El downgrade restaura el catálogo anterior, sin inventar cuáles high eran
critical: la conversión de datos no es reversible.
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0003_retirar_prioridad_critical"
down_revision: str | None = "0002_autenticacion_persistencia"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Bloquea escrituras hasta instalar el nuevo catálogo en la misma transacción.
    op.execute(sa.text("LOCK TABLE tickets IN ACCESS EXCLUSIVE MODE"))
    op.execute(sa.text("UPDATE tickets SET prioridad = 'high', actualizado_en = now() WHERE prioridad = 'critical'"))
    op.drop_constraint(op.f("ck_tickets_prioridad_valida"), "tickets", type_="check")
    op.create_check_constraint(
        op.f("ck_tickets_prioridad_valida"), "tickets",
        "prioridad IN ('low', 'medium', 'high')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_tickets_prioridad_valida"), "tickets", type_="check")
    op.create_check_constraint(
        op.f("ck_tickets_prioridad_valida"), "tickets",
        "prioridad IN ('low', 'medium', 'high', 'critical')",
    )
