"""Owner evidence for exact candidate suite execution, not a client pass flag."""
from alembic import op
import sqlalchemy as sa

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade():
    for owner, root in (("agent", "agents"), ("network", "networks")):
        op.create_table("asac_evaluations",
            sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("project_id", sa.UUID(), nullable=False),
            sa.Column("resource_id", sa.UUID(), nullable=False),
            sa.Column("candidate_id", sa.UUID(), nullable=False),
            sa.Column("operation_id", sa.UUID(), nullable=False),
            sa.Column("actor", sa.String(96), nullable=False),
            sa.Column("request_digest", sa.String(71), nullable=False),
            sa.Column("state", sa.String(16), nullable=False),
            sa.Column("suite", sa.JSON(), nullable=False),
            *[sa.Column(name, sa.String(71), nullable=False) for name in (
                "suite_digest", "dataset_digest", "policy_digest", "runtime_digest", "record_digest", "binding_digest")],
            sa.Column("cases", sa.JSON(), nullable=False),
            sa.Column("error_code", sa.String(128), nullable=True),
            sa.UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name=f"uq_{owner}_asac_evaluation_operation"),
            sa.CheckConstraint("state IN ('accepted', 'running', 'passed', 'failed', 'uncertain')", name=f"ck_{owner}_asac_evaluation_state"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["candidate_id"], [f"{owner}.asac_candidates.id"], ondelete="RESTRICT"), schema=owner)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM agent.asac_evaluations)
        OR EXISTS (SELECT 1 FROM network.asac_evaluations)
        THEN RAISE EXCEPTION 'Retained evaluation evidence prevents destructive downgrade';
        END IF; END $$""")
    for owner in ("network", "agent"):
        op.drop_table("asac_evaluations", schema=owner)
