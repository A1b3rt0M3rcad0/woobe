"""Freeze bounded legacy write authority before new granular permissions exist."""
from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE core.project_configuration_legacy_authorities (
        project_id uuid NOT NULL REFERENCES core.projects(id) ON DELETE CASCADE,
        subject_type varchar(16) NOT NULL, subject_id uuid NOT NULL,
        permission varchar(64) NOT NULL, catalog_revision varchar(64) NOT NULL,
        PRIMARY KEY(project_id, subject_type, subject_id, permission))""")
    op.execute("""INSERT INTO core.project_configuration_legacy_authorities
        SELECT g.project_id, 'control_key', g.control_key_id, p.value, 'pre-project_configuration.v1'
        FROM core.workspace_control_key_project_grants g
        CROSS JOIN LATERAL jsonb_array_elements_text(g.permissions) p(value)
        WHERE p.value IN ('provider:write', 'provider:credential:rotate', 'secret:write', 'tool:write', 'project:environment:write')
        ON CONFLICT DO NOTHING""")
    op.execute("""INSERT INTO core.project_configuration_legacy_authorities
        SELECT g.project_id, 'human', g.subject_user_id, p.value, 'pre-project_configuration.v1'
        FROM identity.authority_assignments g
        CROSS JOIN LATERAL jsonb_array_elements_text(g.permissions) p(value)
        WHERE g.project_id IS NOT NULL AND g.status='active'
        AND p.value IN ('provider:write', 'provider:credential:rotate', 'secret:write', 'tool:write', 'project:environment:write')
        ON CONFLICT DO NOTHING""")


def downgrade():
    raise RuntimeError("Legacy authority provenance cannot be recreated after cutover")
