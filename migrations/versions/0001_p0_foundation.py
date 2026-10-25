"""P0 建库：14 张表（01-data-model §7）。

Revision ID: 0001
Revises:
Create Date: 2026-10-25

- 主键统一 bigint GENERATED ALWAYS AS IDENTITY；时间列 timestamptz（D-4）。
- 枚举 text + CHECK（不用 PG ENUM）；D-1 部分唯一索引与 D-10 CHECK 手写。
- D-6：audit_logs 首次建表即 REVOKE UPDATE, DELETE。
- alerts.suppressed_by_window_id 列在 P0 建、外键随 P2 maintenance_windows 落地（0003）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APPEND_ONLY_TABLES = ("audit_logs",)


def _id() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("permissions", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("team_scope", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("detail", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("cost", JSONB(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("actor_type IN ('user', 'system')", name="ck_audit_logs_actor_type"),
    )
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_user_id", "created_at"])
    op.create_index("idx_audit_logs_created", "audit_logs", ["created_at"])
    # D-6：只追加，库级撤销 UPDATE/DELETE（对迁移执行者当前角色生效）
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM CURRENT_USER")

    op.create_table(
        "credentials",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False, server_default=sa.text("'readonly'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("scope IN ('readonly', 'write')", name="ck_credentials_scope"),
        sa.UniqueConstraint("name", name="uq_credentials_name"),
    )

    op.create_table(
        "clusters",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("api_endpoint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("k8s_version", sa.Text(), nullable=True),
        sa.Column("credential_id", sa.BigInteger(), sa.ForeignKey("credentials.id"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('connected', 'degraded', 'disconnected', 'unknown')",
            name="ck_clusters_status",
        ),
        sa.UniqueConstraint("name", name="uq_clusters_name"),
    )
    op.create_index("idx_clusters_status", "clusters", ["status"])

    op.create_table(
        "providers",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("pull_mode", sa.Text(), nullable=True),
        sa.Column("config", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("credential_id", sa.BigInteger(), sa.ForeignKey("credentials.id"), nullable=True),
        sa.Column("fingerprint_fields", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("category IN ('source', 'query', 'action')", name="ck_providers_category"),
        sa.CheckConstraint("pull_mode IN ('push', 'poll')", name="ck_providers_pull_mode"),
        sa.UniqueConstraint("name", name="uq_providers_name"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'received'")),
        sa.Column("labels", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("enrichments", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("raw_payload", JSONB(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("first_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # 外键指向 P2 的 maintenance_windows，随 0003 落地
        sa.Column("suppressed_by_window_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_alerts_severity"),
        sa.CheckConstraint(
            "status IN ('received', 'deduplicated', 'enriched', 'correlated', 'standalone', "
            "'suppressed', 'notified', 'resolved')",
            name="ck_alerts_status",
        ),
        # D-10：suppressed 必须挂维护窗口（BR-07）
        sa.CheckConstraint(
            "status <> 'suppressed' OR suppressed_by_window_id IS NOT NULL",
            name="ck_alerts_suppressed_window",
        ),
    )
    # D-1 部分唯一索引：活跃周期内指纹唯一
    op.create_index(
        "uk_alerts_active_fingerprint",
        "alerts",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("status <> 'resolved'"),
    )
    op.create_index(
        "idx_alerts_labels",
        "alerts",
        ["labels"],
        postgresql_using="gin",
        postgresql_ops={"labels": "jsonb_path_ops"},
    )
    op.create_index(
        "idx_alerts_provider_time",
        "alerts",
        ["provider_id", sa.text("last_occurred_at DESC")],
    )
    op.create_index("idx_alerts_status_severity", "alerts", ["status", "severity"])

    op.create_table(
        "enrichment_rules",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("matchers", JSONB(), nullable=False),
        sa.Column("mappings", JSONB(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_enrichment_rules_name"),
    )

    op.create_table(
        "inspection_rules",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity_default", sa.Text(), nullable=False),
        sa.Column("k8s_version_fit", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "severity_default IN ('info', 'warning', 'critical')",
            name="ck_inspection_rules_severity_default",
        ),
        sa.UniqueConstraint("code", name="uq_inspection_rules_code"),
    )

    op.create_table(
        "inspection_policies",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("cluster_id", sa.BigInteger(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=False),
        sa.Column("ai_explain_level", sa.Text(), nullable=False, server_default=sa.text("'off'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "ai_explain_level IN ('off', 'info', 'warning', 'critical')",
            name="ck_inspection_policies_ai_explain_level",
        ),
        sa.UniqueConstraint("cluster_id", "name", name="uq_inspection_policies_cluster_name"),
    )

    op.create_table(
        "inspection_policy_rules",
        sa.Column(
            "policy_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection_policies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rule_id", sa.BigInteger(), sa.ForeignKey("inspection_rules.id"), primary_key=True),
    )

    op.create_table(
        "inspection_runs",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("policy_id", sa.BigInteger(), sa.ForeignKey("inspection_policies.id"), nullable=False),
        sa.Column("cluster_id", sa.BigInteger(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False, server_default=sa.text("'schedule'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("trigger IN ('schedule', 'manual')", name="ck_inspection_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')", name="ck_inspection_runs_status"
        ),
    )
    op.create_index(
        "idx_inspection_runs_cluster_time",
        "inspection_runs",
        ["cluster_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("inspection_runs.id"), nullable=False),
        sa.Column("cluster_id", sa.BigInteger(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("resource_ref", JSONB(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("raw_error", JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ignored_reason", sa.Text(), nullable=True),
        sa.Column("converted_alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_findings_severity"),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'ignored', "
            "'converted_to_alert')",
            name="ck_findings_status",
        ),
        # D-10：ignored 必填原因
        sa.CheckConstraint(
            "status <> 'ignored' OR ignored_reason IS NOT NULL",
            name="ck_findings_ignored_reason",
        ),
        sa.UniqueConstraint("run_id", "rule_code", "resource_ref", name="uk_findings_run_rule_resource"),
    )
    op.create_index("idx_findings_status_severity", "findings", ["status", "severity"])
    op.create_index("idx_findings_cluster_rule", "findings", ["cluster_id", "rule_code"])


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_table("inspection_runs")
    op.drop_table("inspection_policy_rules")
    op.drop_table("inspection_policies")
    op.drop_table("inspection_rules")
    op.drop_table("enrichment_rules")
    op.drop_index("idx_alerts_status_severity", table_name="alerts")
    op.drop_index("idx_alerts_provider_time", table_name="alerts")
    op.drop_index("idx_alerts_labels", table_name="alerts")
    op.drop_index("uk_alerts_active_fingerprint", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("providers")
    op.drop_index("idx_clusters_status", table_name="clusters")
    op.drop_table("clusters")
    op.drop_table("credentials")
    op.execute("GRANT UPDATE, DELETE ON audit_logs TO CURRENT_USER")
    op.drop_index("idx_audit_logs_created", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
