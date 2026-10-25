"""P3 流程编排：+2 张表（workflows / workflow_runs）。

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25

- uk_workflows_current 部分唯一索引（同名仅一个当前版本）。
- D-10：source='ai_generated' 时 approved_by 必填（BR-05 库级约束）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("yaml", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source IN ('manual', 'ai_generated')", name="ck_workflows_source"),
        sa.CheckConstraint(
            "source <> 'ai_generated' OR approved_by IS NOT NULL",
            name="ck_workflows_ai_generated_approved_by",
        ),
        sa.UniqueConstraint("name", "version", name="uq_workflows_name_version"),
    )
    op.create_index(
        "uk_workflows_current",
        "workflows",
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("workflow_id", sa.BigInteger(), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("yaml_snapshot", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("triggered_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'triggered'")),
        sa.Column("steps_log", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "trigger_type IN ('alert', 'manual', 'schedule')", name="ck_workflow_runs_trigger_type"
        ),
        sa.CheckConstraint(
            "status IN ('triggered', 'running', 'waiting_approval', 'cancelled', 'succeeded', "
            "'failed', 'timeout')",
            name="ck_workflow_runs_status",
        ),
    )
    op.create_index(
        "idx_workflow_runs_workflow",
        "workflow_runs",
        ["workflow_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_workflow_runs_status", "workflow_runs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("idx_workflow_runs_workflow", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("uk_workflows_current", table_name="workflows")
    op.drop_table("workflows")
