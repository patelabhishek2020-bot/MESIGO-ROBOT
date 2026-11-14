"""Agent operations tables (agents 2–12)

Revision ID: 20260314_0002
Revises: 20260314_0001
Create Date: 2026-03-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260314_0002"
down_revision: Union[str, None] = "20260314_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_key", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True)),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True)),
        sa.Column("otp_challenge_id", postgresql.UUID(as_uuid=True)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_pending_approvals_action_key", "pending_approvals", ["action_key"])

    op.create_table(
        "otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("destination_masked", sa.String(128), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("related_approval_id", postgresql.UUID(as_uuid=True)),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("max_attempts", sa.Integer(), server_default="5"),
        sa.Column("status", sa.String(32), server_default="sent"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(64)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("products", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("rating", sa.Numeric(4, 2)),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "rate_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("moq", sa.Numeric(18, 2)),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(128)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(64), nullable=False, unique=True),
        sa.Column("direction", sa.String(16), server_default="export"),
        sa.Column("origin", sa.String(128)),
        sa.Column("destination", sa.String(128)),
        sa.Column("mode", sa.String(32)),
        sa.Column("carrier", sa.String(128)),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("etd", sa.DateTime(timezone=True)),
        sa.Column("eta", sa.DateTime(timezone=True)),
        sa.Column("docs_checklist", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(64), nullable=False, unique=True),
        sa.Column("direction", sa.String(16), server_default="receivable"),
        sa.Column("counterparty", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("line_items", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "compliance_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(128)),
        sa.Column("category", sa.String(64)),
        sa.Column("summary", sa.Text()),
        sa.Column("severity", sa.String(16), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "compliance_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_ref", sa.String(128), nullable=False),
        sa.Column("result", sa.String(32), server_default="pass"),
        sa.Column("findings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("checked_by_agent", sa.String(64), server_default="compliance"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "document_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("extracted_fields", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("risk_flags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("alert_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("model_used", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "staff_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("department", sa.String(128)),
        sa.Column("title", sa.String(128)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("hire_date", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "attendance_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("note", sa.Text()),
    )

    op.create_table(
        "self_update_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("proposed_change", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), server_default="proposed"),
        sa.Column("test_report", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("safe_test_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("owner_approved", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("deployed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "design_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("template", sa.String(64), server_default="commercial_invoice"),
        sa.Column("status", sa.String(32), server_default="queued"),
        sa.Column("input_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_path", sa.String(512)),
        sa.Column("preview_html", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "social_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("media_urls", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("external_id", sa.String(128)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "message_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), server_default="outbound"),
        sa.Column("to_address", sa.String(255)),
        sa.Column("from_address", sa.String(255)),
        sa.Column("subject", sa.String(255)),
        sa.Column("body_preview", sa.Text()),
        sa.Column("status", sa.String(32), server_default="queued"),
        sa.Column("provider_ref", sa.String(128)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "api_subscription_health",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="unknown"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("metrics", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("alert_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_api_subscription_health_provider", "api_subscription_health", ["provider"])

    op.create_table(
        "interface_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("channel", sa.String(16), server_default="text"),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("transcript", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_intent", sa.String(128)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for table in [
        "interface_sessions",
        "api_subscription_health",
        "message_logs",
        "social_posts",
        "design_jobs",
        "self_update_jobs",
        "attendance_logs",
        "staff_members",
        "document_analyses",
        "compliance_checks",
        "compliance_rules",
        "invoices",
        "shipments",
        "rate_quotes",
        "suppliers",
        "otp_challenges",
        "pending_approvals",
    ]:
        op.drop_table(table)
