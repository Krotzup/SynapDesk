"""Agrega persistencia de sesiones, CSRF, límites y auditoría.

Revisión: 0002_autenticacion_persistencia
Revisión anterior: 0001_usuarios_tickets
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_autenticacion_persistencia"
down_revision: str | None = "0001_usuarios_tickets"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "sesiones",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("digest_credencial", postgresql.BYTEA(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "ultima_actividad",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_revocacion", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "octet_length(digest_credencial) = 32",
            name=op.f("ck_sesiones_digest_credencial_longitud"),
        ),
        sa.CheckConstraint(
            "ultima_actividad >= creado_en AND expira_en > creado_en",
            name=op.f("ck_sesiones_fechas_vigencia_validas"),
        ),
        sa.CheckConstraint(
            "ultima_actividad <= expira_en",
            name=op.f("ck_sesiones_actividad_no_supera_expiracion"),
        ),
        sa.CheckConstraint(
            "revocada_en IS NULL OR revocada_en >= creado_en",
            name=op.f("ck_sesiones_revocacion_no_anterior"),
        ),
        sa.CheckConstraint(
            "motivo_revocacion IS NULL OR btrim(motivo_revocacion) <> ''",
            name=op.f("ck_sesiones_motivo_revocacion_no_vacio"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            ondelete="RESTRICT",
            name=op.f("fk_sesiones_usuario_id_usuarios"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sesiones")),
        sa.UniqueConstraint(
            "digest_credencial", name=op.f("uq_sesiones_digest_credencial")
        ),
    )
    op.create_index(
        "ix_sesiones_usuario_revocada", "sesiones", ["usuario_id", "revocada_en"]
    )
    op.create_index(
        "ix_sesiones_expiracion_revocada", "sesiones", ["expira_en", "revocada_en"]
    )

    op.create_table(
        "contextos_csrf",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("digest_secreto", postgresql.BYTEA(), nullable=True),
        sa.Column("sesion_id", sa.Uuid(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('anonymous', 'authenticated')",
            name=op.f("ck_contextos_csrf_tipo_valido"),
        ),
        sa.CheckConstraint(
            "((tipo = 'anonymous' AND digest_secreto IS NOT NULL AND sesion_id IS NULL) "
            "OR (tipo = 'authenticated' AND digest_secreto IS NULL AND sesion_id IS NOT NULL))",
            name=op.f("ck_contextos_csrf_vinculacion_tipo_consistente"),
        ),
        sa.CheckConstraint(
            "digest_secreto IS NULL OR octet_length(digest_secreto) = 32",
            name=op.f("ck_contextos_csrf_digest_secreto_longitud"),
        ),
        sa.CheckConstraint(
            "expira_en > creado_en",
            name=op.f("ck_contextos_csrf_fechas_vigencia_validas"),
        ),
        sa.CheckConstraint(
            "revocado_en IS NULL OR revocado_en >= creado_en",
            name=op.f("ck_contextos_csrf_revocacion_no_anterior"),
        ),
        sa.ForeignKeyConstraint(
            ["sesion_id"],
            ["sesiones.id"],
            ondelete="RESTRICT",
            name=op.f("fk_contextos_csrf_sesion_id_sesiones"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contextos_csrf")),
        sa.UniqueConstraint(
            "digest_secreto", name=op.f("uq_contextos_csrf_digest_secreto")
        ),
        sa.UniqueConstraint("sesion_id", name=op.f("uq_contextos_csrf_sesion_id")),
    )
    op.create_index(
        "ix_contextos_csrf_sesion_revocado",
        "contextos_csrf",
        ["sesion_id", "revocado_en"],
    )
    op.create_index(
        "ix_contextos_csrf_expiracion_revocado",
        "contextos_csrf",
        ["expira_en", "revocado_en"],
    )

    op.create_table(
        "tokens_csrf",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contexto_id", sa.Uuid(), nullable=False),
        sa.Column("digest_token", postgresql.BYTEA(), nullable=False),
        sa.Column(
            "emitido_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(digest_token) = 32",
            name=op.f("ck_tokens_csrf_digest_token_longitud"),
        ),
        sa.CheckConstraint(
            "expira_en > emitido_en",
            name=op.f("ck_tokens_csrf_fechas_vigencia_validas"),
        ),
        sa.CheckConstraint(
            "invalidado_en IS NULL OR invalidado_en >= emitido_en",
            name=op.f("ck_tokens_csrf_invalidacion_no_anterior"),
        ),
        sa.ForeignKeyConstraint(
            ["contexto_id"],
            ["contextos_csrf.id"],
            ondelete="RESTRICT",
            name=op.f("fk_tokens_csrf_contexto_id_contextos_csrf"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tokens_csrf")),
        sa.UniqueConstraint("digest_token", name=op.f("uq_tokens_csrf_digest_token")),
    )
    op.create_index(
        "ix_tokens_csrf_contexto_vigencia",
        "tokens_csrf",
        ["contexto_id", "expira_en", "invalidado_en", "emitido_en"],
    )

    op.create_table(
        "limites_autenticacion",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tipo_clave", sa.String(32), nullable=False),
        sa.Column("clave_digest", postgresql.BYTEA(), nullable=False),
        sa.Column("ventana_inicia_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ventana_termina_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reservas", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "btrim(tipo_clave) <> ''",
            name=op.f("ck_limites_autenticacion_tipo_clave_no_vacio"),
        ),
        sa.CheckConstraint(
            "octet_length(clave_digest) = 32",
            name=op.f("ck_limites_autenticacion_clave_digest_longitud"),
        ),
        sa.CheckConstraint(
            "ventana_termina_en > ventana_inicia_en",
            name=op.f("ck_limites_autenticacion_ventana_valida"),
        ),
        sa.CheckConstraint(
            "intentos >= 0",
            name=op.f("ck_limites_autenticacion_intentos_no_negativos"),
        ),
        sa.CheckConstraint(
            "reservas >= 0",
            name=op.f("ck_limites_autenticacion_reservas_no_negativas"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_limites_autenticacion_version_positiva"),
        ),
        sa.CheckConstraint(
            "bloqueado_hasta IS NULL OR bloqueado_hasta >= ventana_inicia_en",
            name=op.f("ck_limites_autenticacion_bloqueo_no_anterior"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_limites_autenticacion")),
        sa.UniqueConstraint(
            "tipo_clave",
            "clave_digest",
            "ventana_inicia_en",
            name=op.f("uq_limites_autenticacion_clave_ventana_unica"),
        ),
    )
    op.create_index(
        "ix_limites_autenticacion_fin_bloqueo",
        "limites_autenticacion",
        ["ventana_termina_en", "bloqueado_hasta"],
    )
    op.create_index(
        "ix_limites_autenticacion_actualizado",
        "limites_autenticacion",
        ["actualizado_en"],
    )

    op.create_table(
        "eventos_autenticacion",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tipo_evento", sa.String(64), nullable=False),
        sa.Column(
            "ocurrido_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("sesion_id", sa.Uuid(), nullable=True),
        sa.Column("resultado", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("motivo", sa.String(128), nullable=True),
        sa.Column("ip_verificada_digest", postgresql.BYTEA(), nullable=True),
        sa.CheckConstraint(
            "btrim(tipo_evento) <> ''",
            name=op.f("ck_eventos_autenticacion_tipo_evento_no_vacio"),
        ),
        sa.CheckConstraint(
            "btrim(resultado) <> ''",
            name=op.f("ck_eventos_autenticacion_resultado_no_vacio"),
        ),
        sa.CheckConstraint(
            "request_id IS NULL OR btrim(request_id) <> ''",
            name=op.f("ck_eventos_autenticacion_request_id_no_vacio"),
        ),
        sa.CheckConstraint(
            "motivo IS NULL OR btrim(motivo) <> ''",
            name=op.f("ck_eventos_autenticacion_motivo_no_vacio"),
        ),
        sa.CheckConstraint(
            "ip_verificada_digest IS NULL OR octet_length(ip_verificada_digest) = 32",
            name=op.f("ck_eventos_autenticacion_ip_digest_longitud"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            ondelete="SET NULL",
            name=op.f("fk_eventos_autenticacion_usuario_id_usuarios"),
        ),
        sa.ForeignKeyConstraint(
            ["sesion_id"],
            ["sesiones.id"],
            ondelete="SET NULL",
            name=op.f("fk_eventos_autenticacion_sesion_id_sesiones"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eventos_autenticacion")),
    )
    op.create_index(
        "ix_eventos_autenticacion_fecha_tipo",
        "eventos_autenticacion",
        ["ocurrido_en", "tipo_evento"],
    )
    op.create_index(
        "ix_eventos_autenticacion_usuario_fecha",
        "eventos_autenticacion",
        ["usuario_id", "ocurrido_en"],
    )
    op.create_index(
        "ix_eventos_autenticacion_sesion_fecha",
        "eventos_autenticacion",
        ["sesion_id", "ocurrido_en"],
    )


def downgrade() -> None:
    op.drop_index("ix_eventos_autenticacion_sesion_fecha", table_name="eventos_autenticacion")
    op.drop_index("ix_eventos_autenticacion_usuario_fecha", table_name="eventos_autenticacion")
    op.drop_index("ix_eventos_autenticacion_fecha_tipo", table_name="eventos_autenticacion")
    op.drop_table("eventos_autenticacion")

    op.drop_index("ix_limites_autenticacion_actualizado", table_name="limites_autenticacion")
    op.drop_index("ix_limites_autenticacion_fin_bloqueo", table_name="limites_autenticacion")
    op.drop_table("limites_autenticacion")

    op.drop_index("ix_tokens_csrf_contexto_vigencia", table_name="tokens_csrf")
    op.drop_table("tokens_csrf")

    op.drop_index(
        "ix_contextos_csrf_expiracion_revocado", table_name="contextos_csrf"
    )
    op.drop_index("ix_contextos_csrf_sesion_revocado", table_name="contextos_csrf")
    op.drop_table("contextos_csrf")

    op.drop_index("ix_sesiones_expiracion_revocada", table_name="sesiones")
    op.drop_index("ix_sesiones_usuario_revocada", table_name="sesiones")
    op.drop_table("sesiones")
