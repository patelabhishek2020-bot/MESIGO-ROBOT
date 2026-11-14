"""Initial Mesigo schema

Revision ID: 20260314_0001
Revises:
Create Date: 2026-03-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260314_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255)),
        sa.Column("registration_number", sa.String(128)),
        sa.Column("tax_id", sa.String(128)),
        sa.Column("country", sa.String(64)),
        sa.Column("address", sa.Text()),
        sa.Column("website", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("email", sa.String(255)),
        sa.Column("logo_url", sa.String(512)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(128)),
        sa.Column("hs_code", sa.String(64)),
        sa.Column("category", sa.String(128)),
        sa.Column("description", sa.Text()),
        sa.Column("unit", sa.String(32)),
        sa.Column("is_import", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_export", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country_code", sa.String(8), nullable=False),
        sa.Column("region", sa.String(128)),
        sa.Column("currency", sa.String(8)),
        sa.Column("direction", sa.String(16), server_default="both"),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("permissions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("full_name", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_owner", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    op.create_table(
        "voice_biometrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(128), server_default="primary"),
        sa.Column("sample_path", sa.String(512)),
        sa.Column("embedding_ref", sa.String(512)),
        sa.Column("status", sa.String(32), server_default="enrolled"),
        sa.Column("enrollment_phrase", sa.String(255)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("enrolled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_voice_biometrics_user_id", "voice_biometrics", ["user_id"])

    op.create_table(
        "encrypted_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("description", sa.Text()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("category", "key", name="uq_setting_category_key"),
    )
    op.create_index("ix_encrypted_settings_category", "encrypted_settings", ["category"])

    op.create_table(
        "system_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("value_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "approval_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_key", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.String(64)),
        sa.Column("mode", sa.String(32), server_default="approval"),
        sa.Column("amount_limit", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(8)),
        sa.Column("requires_owner", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_username", sa.String(64)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("status", sa.String(32), server_default="success"),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("contact_name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("country", sa.String(64)),
        sa.Column("source", sa.String(128)),
        sa.Column("status", sa.String(32), server_default="new"),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("whatsapp", sa.String(64)),
        sa.Column("wechat_id", sa.String(128)),
        sa.Column("company_name", sa.String(255)),
        sa.Column("role_title", sa.String(128)),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "document_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("retention_days", sa.Integer()),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_categories.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512)),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("checksum", sa.String(128)),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(32), server_default="stored"),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for table in [
        "documents",
        "document_categories",
        "contacts",
        "leads",
        "audit_logs",
        "approval_rules",
        "system_state",
        "encrypted_settings",
        "voice_biometrics",
        "user_roles",
        "users",
        "roles",
        "markets",
        "products",
        "companies",
    ]:
        op.drop_table(table)
