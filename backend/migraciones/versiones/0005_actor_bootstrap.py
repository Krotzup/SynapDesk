"""Actor externo opcional, obligatorio para admin_bootstrap; eventos previos intactos."""

from alembic import op
import sqlalchemy as sa

revision = "0005_actor_bootstrap"
down_revision = "0004_bootstrap_csrf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eventos_autenticacion", sa.Column("actor_tipo", sa.String(32), nullable=True))
    op.add_column("eventos_autenticacion", sa.Column("actor_id", sa.String(32), nullable=True))
    op.create_check_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
        "eventos_autenticacion",
        "(tipo_evento <> 'admin_bootstrap' AND actor_tipo IS NULL AND actor_id IS NULL) OR "
        "(tipo_evento = 'admin_bootstrap' AND actor_tipo IS NOT NULL AND "
        "actor_tipo = 'postgresql_role' AND actor_id IS NOT NULL AND "
        "actor_id ~ '^[1-9][0-9]{0,9}$')")


def downgrade() -> None:
    op.execute("LOCK TABLE eventos_autenticacion IN ACCESS EXCLUSIVE MODE")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM eventos_autenticacion "
               "WHERE tipo_evento='admin_bootstrap') THEN RAISE EXCEPTION "
               "'No se puede retirar el actor administrativo existente'; END IF; END $$")
    op.drop_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
                       "eventos_autenticacion", type_="check")
    op.drop_column("eventos_autenticacion", "actor_id")
    op.drop_column("eventos_autenticacion", "actor_tipo")
