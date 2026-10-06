"""Add immutable authority categories, materialized assignments and audit.

Revision ID: 0075
Revises: 0074
"""

from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE identity.authority_categories (\n\tworkspace_id UUID NOT NULL, \n\tname VARCHAR(128) NOT NULL, \n\tdescription VARCHAR(500), \n\tscope VARCHAR(16) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tsystem BOOLEAN NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_identity_authority_category_name UNIQUE (workspace_id, scope, name), \n\tCONSTRAINT ck_identity_authority_category_scope CHECK (scope IN ('workspace', 'project')), \n\tCONSTRAINT ck_identity_authority_category_status CHECK (status IN ('active', 'archived')), \n\tCONSTRAINT ck_identity_authority_category_revision CHECK (revision > 0), \n\tFOREIGN KEY(workspace_id) REFERENCES identity.workspaces (id) ON DELETE CASCADE\n)"
    )
    op.execute(
        "CREATE TABLE identity.authority_category_versions (\n\tcategory_id UUID NOT NULL, \n\trevision INTEGER NOT NULL, \n\tname VARCHAR(128) NOT NULL, \n\tpermissions JSONB NOT NULL, \n\tconditions JSONB NOT NULL, \n\tcatalog_revision VARCHAR(64) NOT NULL, \n\tdescription VARCHAR(500), \n\tcreated_by_user_id UUID, \n\tcreated_by_control_key_id UUID, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_identity_authority_category_version UNIQUE (category_id, revision), \n\tCONSTRAINT ck_identity_authority_version_revision CHECK (revision > 0), \n\tFOREIGN KEY(category_id) REFERENCES identity.authority_categories (id) ON DELETE CASCADE\n)"
    )
    op.execute(
        "CREATE TABLE identity.authority_assignments (\n\tworkspace_id UUID NOT NULL, \n\tsubject_user_id UUID NOT NULL, \n\tscope_id UUID NOT NULL, \n\tproject_id UUID, \n\tcategory_id UUID NOT NULL, \n\tcategory_revision INTEGER NOT NULL, \n\tpermissions JSONB NOT NULL, \n\tconditions JSONB NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(category_id, category_revision) REFERENCES identity.authority_category_versions (category_id, revision) ON DELETE RESTRICT, \n\tCONSTRAINT uq_identity_authority_assignment_scope UNIQUE (workspace_id, subject_user_id, scope_id), \n\tFOREIGN KEY(workspace_id) REFERENCES identity.workspaces (id) ON DELETE CASCADE, \n\tFOREIGN KEY(subject_user_id) REFERENCES identity.users (id) ON DELETE CASCADE\n)"
    )
    op.execute(
        "CREATE TABLE identity.authority_audit (\n\tworkspace_id UUID NOT NULL, \n\tactor_user_id UUID, \n\tactor_control_key_id UUID, \n\toperation VARCHAR(64) NOT NULL, \n\tsubject_id UUID NOT NULL, \n\trevision INTEGER NOT NULL, \n\tdetails JSONB NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES identity.workspaces (id) ON DELETE CASCADE\n)"
    )
    op.create_foreign_key(
        "fk_core_control_key_workspace_category",
        "workspace_control_keys",
        "authority_category_versions",
        ["workspace_category_id", "workspace_category_revision"],
        ["category_id", "revision"],
        source_schema="core",
        referent_schema="identity",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_core_control_key_project_category",
        "workspace_control_key_project_grants",
        "authority_category_versions",
        ["category_id", "category_revision"],
        ["category_id", "revision"],
        source_schema="core",
        referent_schema="identity",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_identity_authority_assignment_actor",
        "authority_assignments",
        ["workspace_id", "subject_user_id", "status"],
        schema="identity",
    )
    op.create_index(
        "ix_identity_authority_audit_workspace",
        "authority_audit",
        ["workspace_id", "id"],
        schema="identity",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_core_control_key_project_category",
        "workspace_control_key_project_grants",
        schema="core",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_core_control_key_workspace_category",
        "workspace_control_keys",
        schema="core",
        type_="foreignkey",
    )
    op.drop_table("authority_audit", schema="identity")
    op.drop_table("authority_assignments", schema="identity")
    op.drop_table("authority_category_versions", schema="identity")
    op.drop_table("authority_categories", schema="identity")
