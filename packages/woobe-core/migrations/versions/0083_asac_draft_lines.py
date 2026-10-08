"""Owner-scoped isolated Drafts, verified revisions and durable operation receipts."""
from alembic import op
import sqlalchemy as sa

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def _base():
    return [sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False)]


def upgrade():
    for owner, root in (("agent", "agents"), ("network", "networks")):
        op.create_table("asac_resources", *_base(),
            sa.Column("resource_uid", sa.UUID(), nullable=False),
            sa.UniqueConstraint("project_id", "resource_id", name=f"uq_{owner}_asac_resource_native"),
            sa.UniqueConstraint("project_id", "resource_uid", name=f"uq_{owner}_asac_resource_uid"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="RESTRICT"), schema=owner)
        op.create_table("asac_drafts", *_base(),
            sa.Column("resource_uid", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("generation", sa.Integer(), nullable=False),
            sa.Column("artifact_id", sa.UUID(), nullable=True),
            sa.Column("definition_digest", sa.String(71), nullable=True),
            sa.Column("origin", sa.JSON(), nullable=False),
            sa.Column("working_revision_id", sa.String(39), nullable=True),
            sa.UniqueConstraint("project_id", "resource_id", "name", name=f"uq_{owner}_asac_draft_name"),
            sa.UniqueConstraint("project_id", "resource_uid", "name", name=f"uq_{owner}_asac_draft_uid"),
            sa.CheckConstraint("generation >= 1", name=f"ck_{owner}_asac_draft_generation"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="RESTRICT"), schema=owner)
        op.create_table("asac_revisions", *_base(),
            sa.Column("resource_uid", sa.UUID(), nullable=False),
            sa.Column("revision_id", sa.String(39), nullable=False),
            sa.Column("artifact_id", sa.UUID(), nullable=False),
            sa.Column("document", sa.JSON(), nullable=False),
            sa.Column("actor", sa.String(96), nullable=False),
            sa.UniqueConstraint("project_id", "resource_uid", "revision_id", name=f"uq_{owner}_asac_revision_identity"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="RESTRICT"), schema=owner)
        op.create_table("asac_operations", *_base(),
            sa.Column("actor", sa.String(96), nullable=False),
            sa.Column("operation_id", sa.UUID(), nullable=False),
            sa.Column("request_digest", sa.String(71), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name=f"uq_{owner}_asac_operation_identity"), schema=owner)


def downgrade():
    for owner in ("network", "agent"):
        for table in ("asac_operations", "asac_revisions", "asac_drafts", "asac_resources"):
            op.drop_table(table, schema=owner)
