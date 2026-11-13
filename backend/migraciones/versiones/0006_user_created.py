"""Actor SynapDesk y rol de alta; conserva eventos y actores históricos."""

from alembic import op
import sqlalchemy as sa

revision = "0006_user_created"
down_revision = "0005_actor_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eventos_autenticacion", sa.Column("rol_asignado", sa.String(16), nullable=True))
    op.alter_column("eventos_autenticacion", "actor_id", existing_type=sa.String(32),
                    type_=sa.String(36), existing_nullable=True)
    op.drop_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
                       "eventos_autenticacion", type_="check")
    op.create_check_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
        "eventos_autenticacion",
        "(tipo_evento NOT IN ('admin_bootstrap','user_created') AND "
        "actor_tipo IS NULL AND actor_id IS NULL AND rol_asignado IS NULL) OR "
        "(tipo_evento = 'admin_bootstrap' AND actor_tipo IS NOT NULL AND "
        "actor_tipo = 'postgresql_role' AND actor_id IS NOT NULL AND "
        "actor_id ~ '^[1-9][0-9]{0,9}$' AND rol_asignado IS NULL) OR "
        "(tipo_evento = 'user_created' AND actor_tipo IS NOT NULL AND "
        "actor_tipo = 'synapdesk_user' AND actor_id IS NOT NULL AND "
        "actor_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' AND "
        "rol_asignado IS NOT NULL AND rol_asignado IN ('admin','agent') AND "
        "resultado = 'success' AND motivo IS NOT NULL AND motivo = 'user_created_by_admin')")


def downgrade() -> None:
    op.execute("LOCK TABLE eventos_autenticacion IN ACCESS EXCLUSIVE MODE")
    # No truncar UUID, borrar eventos ni despojar al evento de actor/rol.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM eventos_autenticacion "
               "WHERE tipo_evento='user_created') THEN RAISE EXCEPTION "
               "'No se puede retirar auditoría de altas existente'; END IF; END $$")
    op.drop_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
                       "eventos_autenticacion", type_="check")
    op.create_check_constraint(op.f("ck_eventos_autenticacion_actor_externo_valido"),
        "eventos_autenticacion",
        "(tipo_evento <> 'admin_bootstrap' AND actor_tipo IS NULL AND actor_id IS NULL) OR "
        "(tipo_evento = 'admin_bootstrap' AND actor_tipo IS NOT NULL AND "
        "actor_tipo = 'postgresql_role' AND actor_id IS NOT NULL AND "
        "actor_id ~ '^[1-9][0-9]{0,9}$')")
    op.alter_column("eventos_autenticacion", "actor_id", existing_type=sa.String(36),
                    type_=sa.String(32), existing_nullable=True)
    op.drop_column("eventos_autenticacion", "rol_asignado")
