"""P1 AI 域：+4 张表（ai_tasks / ai_mask_mappings / ai_explanations / ai_call_logs）。

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25

- ai_tasks.incident_id 外键指向 P2 的 incidents，随 0003 落地。
- D-6：ai_call_logs 建表即 REVOKE UPDATE, DELETE。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "ai_tasks",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("context_refs", JSONB(), nullable=False),
        # 外键指向 P2 的 incidents，随 0003 落地
        sa.Column("finding_id", sa.BigInteger(), sa.ForeignKey("findings.id"), nullable=True),
        sa.Column("incident_id", sa.BigInteger(), nullable=True),
        sa.Column("budget", JSONB(), nullable=False),
        sa.Column("calls_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requested_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approval_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('explain', 'investigate', 'workflow_gen')", name="ck_ai_tasks_type"),
        sa.CheckConstraint(
            "status IN ('created', 'sanitizing', 'running', 'pending_approval', 'cancelled', "
            "'completed', 'failed', 'budget_exceeded')",
            name="ck_ai_tasks_status",
        ),
    )
    op.create_index("idx_ai_tasks_status", "ai_tasks", ["status"])
    op.create_index("idx_ai_tasks_incident", "ai_tasks", ["incident_id"])
    op.create_index("idx_ai_tasks_finding", "ai_tasks", ["finding_id"])

    op.create_table(
        "ai_mask_mappings",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column(
            "task_id",
            sa.BigInteger(),
            sa.ForeignKey("ai_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("placeholder", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("encrypted_original", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("task_id", "placeholder", name="uq_ai_mask_mappings_task_placeholder"),
    )

    op.create_table(
        "ai_explanations",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("finding_id", sa.BigInteger(), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("ai_tasks.id"), nullable=True),
        sa.Column("sanitized_input_digest", sa.Text(), nullable=False),
        sa.Column("output", JSONB(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("finding_id", name="uq_ai_explanations_finding"),
    )

    op.create_table(
        "ai_call_logs",
        sa.Column("id", sa.BigInteger(), _id(), primary_key=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("ai_tasks.id"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("tool_used", sa.Text(), nullable=True),
        sa.Column("prompt_digest", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("result_code", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("result_code IN ('ok', 'error', 'timeout')", name="ck_ai_call_logs_result_code"),
    )
    op.create_index("idx_ai_call_logs_task", "ai_call_logs", ["task_id"])
    op.create_index("idx_ai_call_logs_created", "ai_call_logs", ["created_at"])
    # D-6：只追加
    op.execute("REVOKE UPDATE, DELETE ON ai_call_logs FROM CURRENT_USER")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON ai_call_logs TO CURRENT_USER")
    op.drop_index("idx_ai_call_logs_created", table_name="ai_call_logs")
    op.drop_index("idx_ai_call_logs_task", table_name="ai_call_logs")
    op.drop_table("ai_call_logs")
    op.drop_table("ai_explanations")
    op.drop_table("ai_mask_mappings")
    op.drop_index("idx_ai_tasks_finding", table_name="ai_tasks")
    op.drop_index("idx_ai_tasks_incident", table_name="ai_tasks")
    op.drop_index("idx_ai_tasks_status", table_name="ai_tasks")
    op.drop_table("ai_tasks")
