"""P2 事件/值班/通知：+12 张表，并补齐跨期外键。

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25

- 补 0001 遗留：alerts.suppressed_by_window_id -> maintenance_windows。
- 补 0002 遗留：ai_tasks.incident_id -> incidents。
- D-6：notification_records 建表即 REVOKE UPDATE, DELETE。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "correlation_rules",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("conditions", JSONB(), nullable=False),
        sa.Column("time_window_seconds", sa.Integer(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirm_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reject_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("mode IN ('auto', 'candidate')", name="ck_correlation_rules_mode"),
        sa.UniqueConstraint("name", name="uq_correlation_rules_name"),
    )

    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_maintenance_windows_ends", "maintenance_windows", ["ends_at"])
    op.create_foreign_key(
        "fk_alerts_suppressed_by_window",
        "alerts",
        "maintenance_windows",
        ["suppressed_by_window_id"],
        ["id"],
    )

    op.create_table(
        "incident_candidates",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column(
            "correlation_rule_id",
            sa.BigInteger(),
            sa.ForeignKey("correlation_rules.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("member_alert_ids", JSONB(), nullable=False),
        sa.Column("similarity", sa.Numeric(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_incident_candidates_status",
        ),
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), sa.ForeignKey("incident_candidates.id"), nullable=True),
        sa.Column("correlation_rule_id", sa.BigInteger(), sa.ForeignKey("correlation_rules.id"), nullable=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status_page_sync", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('P1', 'P2', 'P3', 'P4')", name="ck_incidents_severity"),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'cancelled', 'mitigated', 'resolved', 'closed')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint("source IN ('correlation', 'manual')", name="ck_incidents_source"),
        # D-10：cancelled 必填原因
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancelled_reason IS NOT NULL",
            name="ck_incidents_cancelled_reason",
        ),
    )
    op.create_index("idx_incidents_status_severity", "incidents", ["status", "severity"])
    op.create_index("idx_incidents_team", "incidents", ["team"])
    op.create_foreign_key(
        "fk_ai_tasks_incident",
        "ai_tasks",
        "incidents",
        ["incident_id"],
        ["id"],
    )

    op.create_table(
        "incident_alerts",
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id"), primary_key=True),
        sa.Column("correlation_rule_id", sa.BigInteger(), sa.ForeignKey("correlation_rules.id"), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_incident_alerts_alert", "incident_alerts", ["alert_id"])

    op.create_table(
        "postmortems",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("timeline", JSONB(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("incident_id", name="uq_postmortems_incident"),
    )

    op.create_table(
        "postmortem_action_items",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column(
            "postmortem_id",
            sa.BigInteger(),
            sa.ForeignKey("postmortems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'done')",
            name="ck_postmortem_action_items_status",
        ),
    )

    op.create_table(
        "status_page_entries",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False, server_default=sa.text("'internal'")),
        sa.Column("service_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("visibility IN ('public', 'internal')", name="ck_status_page_entries_visibility"),
        sa.UniqueConstraint("incident_id", name="uq_status_page_entries_incident"),
    )

    op.create_table(
        "status_page_updates",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.BigInteger(),
            sa.ForeignKey("status_page_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status_snapshot", sa.Text(), nullable=True),
        sa.Column("posted_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "oncall_schedules",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=False),
        sa.Column("rotation_rules", JSONB(), nullable=False),
        sa.Column("calendar", JSONB(), nullable=False),
        sa.Column("overrides", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_oncall_schedules_name"),
    )

    op.create_table(
        "escalation_policies",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("schedule_id", sa.BigInteger(), sa.ForeignKey("oncall_schedules.id"), nullable=False),
        sa.Column("levels", JSONB(), nullable=False),
        sa.Column("channel_fallbacks", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_escalation_policies_name"),
    )

    op.create_table(
        "notification_records",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("ack_action", sa.Text(), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column(
            "escalation_policy_id",
            sa.BigInteger(),
            sa.ForeignKey("escalation_policies.id"),
            nullable=True,
        ),
        sa.Column("escalation_level", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('queued', 'sent', 'failed', 'acked')", name="ck_notification_records_status"),
    )
    op.create_index("idx_notification_records_alert", "notification_records", ["alert_id"])
    op.create_index("idx_notification_records_incident", "notification_records", ["incident_id"])
    op.create_index("idx_notification_records_status", "notification_records", ["status", "created_at"])
    # D-6：只追加
    op.execute("REVOKE UPDATE, DELETE ON notification_records FROM CURRENT_USER")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON notification_records TO CURRENT_USER")
    op.drop_index("idx_notification_records_status", table_name="notification_records")
    op.drop_index("idx_notification_records_incident", table_name="notification_records")
    op.drop_index("idx_notification_records_alert", table_name="notification_records")
    op.drop_table("notification_records")
    op.drop_table("escalation_policies")
    op.drop_table("oncall_schedules")
    op.drop_table("status_page_updates")
    op.drop_table("status_page_entries")
    op.drop_table("postmortem_action_items")
    op.drop_table("postmortems")
    op.drop_index("idx_incident_alerts_alert", table_name="incident_alerts")
    op.drop_table("incident_alerts")
    op.drop_constraint("fk_ai_tasks_incident", "ai_tasks", type_="foreignkey")
    op.drop_index("idx_incidents_team", table_name="incidents")
    op.drop_index("idx_incidents_status_severity", table_name="incidents")
    op.drop_table("incidents")
    op.drop_table("incident_candidates")
    op.drop_constraint("fk_alerts_suppressed_by_window", "alerts", type_="foreignkey")
    op.drop_index("idx_maintenance_windows_ends", table_name="maintenance_windows")
    op.drop_table("maintenance_windows")
    op.drop_table("correlation_rules")
