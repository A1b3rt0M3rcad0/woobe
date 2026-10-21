"""Add persistent artifact workspaces, immutable revisions and catalog history.

DDL is frozen at revision creation; it never imports mutable ORM metadata.
"""
from alembic import op
import sqlalchemy as sa

revision = '0107'
down_revision = '0106'
branch_labels = None
depends_on = None

DDL = ['CREATE SCHEMA artifacts',
 'CREATE TABLE artifacts.workspaces (\n'
 '\tproject_id UUID NOT NULL, \n'
 '\tenvironment VARCHAR(16) NOT NULL, \n'
 '\texternal_namespace VARCHAR(255) NOT NULL, \n'
 '\texternal_key VARCHAR(255) NOT NULL, \n'
 '\tname VARCHAR(255) NOT NULL, \n'
 '\tstorage_profile VARCHAR(128) NOT NULL, \n'
 '\tstatus VARCHAR(32) NOT NULL, \n'
 '\tversion BIGINT NOT NULL, \n'
 '\tcatalog_version BIGINT NOT NULL, \n'
 '\tquota_bytes BIGINT NOT NULL, \n'
 '\tused_bytes BIGINT NOT NULL, \n'
 '\treserved_bytes BIGINT NOT NULL, \n'
 '\tretention_days INTEGER NOT NULL, \n'
 '\tlabels JSONB NOT NULL, \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT uq_artifact_workspace_external UNIQUE (project_id, environment, external_namespace, '
 'external_key), \n'
 '\tCONSTRAINT ck_artifact_workspace_environment CHECK (environment IN '
 "('draft','staging','production')), \n"
 '\tCONSTRAINT ck_artifact_workspace_status CHECK (status IN '
 "('active','archived','deletion_pending','purged')), \n"
 '\tCONSTRAINT ck_artifact_workspace_version CHECK (version >= 1 AND catalog_version >= 0), \n'
 '\tCONSTRAINT ck_artifact_workspace_quota CHECK (quota_bytes >= 0 AND used_bytes >= 0 AND '
 'reserved_bytes >= 0 AND used_bytes + reserved_bytes <= quota_bytes), \n'
 '\tCONSTRAINT ck_artifact_workspace_retention CHECK (retention_days >= 0)\n'
 ')',
 'CREATE INDEX ix_artifact_workspaces_scope_page ON artifacts.workspaces (project_id, environment, '
 'id)',
 'CREATE TABLE artifacts.artifacts (\n'
 '\tworkspace_id VARCHAR(128) NOT NULL, \n'
 '\tpath VARCHAR(1024) NOT NULL, \n'
 '\tkind VARCHAR(16) NOT NULL, \n'
 '\trevision_id VARCHAR(128), \n'
 '\tversion BIGINT NOT NULL, \n'
 '\tdeleted BOOLEAN NOT NULL, \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT uq_artifact_workspace_identity UNIQUE (workspace_id, id), \n'
 "\tCONSTRAINT ck_artifact_kind CHECK (kind IN ('file','directory')), \n"
 '\tCONSTRAINT ck_artifact_version CHECK (version >= 1), \n'
 "\tCONSTRAINT ck_artifact_directory_revision CHECK (kind <> 'directory' OR revision_id IS "
 'NULL), \n'
 '\tFOREIGN KEY(workspace_id) REFERENCES artifacts.workspaces (id) ON DELETE RESTRICT\n'
 ')',
 'CREATE INDEX ix_artifact_workspace_page ON artifacts.artifacts (workspace_id, id)',
 'CREATE UNIQUE INDEX uq_artifact_live_path ON artifacts.artifacts (workspace_id, path) WHERE NOT '
 'deleted',
 'CREATE TABLE artifacts.revisions (\n'
 '\tworkspace_id VARCHAR(128) NOT NULL, \n'
 '\tartifact_id VARCHAR(128) NOT NULL, \n'
 '\tobject_key VARCHAR(1024) NOT NULL, \n'
 '\tcontent_type VARCHAR(255) NOT NULL, \n'
 '\tsize_bytes BIGINT NOT NULL, \n'
 '\tsha256 VARCHAR(64) NOT NULL, \n'
 '\torigin VARCHAR(32) NOT NULL, \n'
 '\tproducer_id VARCHAR(128), \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT uq_artifact_revision_identity UNIQUE (artifact_id, id), \n'
 '\tCONSTRAINT uq_artifact_revision_object_key UNIQUE (object_key), \n'
 '\tCONSTRAINT fk_artifact_revision_owner FOREIGN KEY(workspace_id, artifact_id) REFERENCES '
 'artifacts.artifacts (workspace_id, id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT ck_artifact_revision_size CHECK (size_bytes >= 0), \n'
 "\tCONSTRAINT ck_artifact_revision_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'), \n"
 '\tCONSTRAINT ck_artifact_revision_origin CHECK (origin IN '
 "('upload','application','agent','tool','processing','copy'))\n"
 ')',
 'CREATE INDEX ix_artifact_revisions_page ON artifacts.revisions (workspace_id, artifact_id, id)',
 'CREATE TABLE artifacts.head_history (\n'
 '\tworkspace_id VARCHAR(128) NOT NULL, \n'
 '\tartifact_id VARCHAR(128) NOT NULL, \n'
 '\tfrom_catalog_version BIGINT NOT NULL, \n'
 '\tuntil_catalog_version BIGINT, \n'
 '\tpath VARCHAR(1024) NOT NULL, \n'
 '\tkind VARCHAR(16) NOT NULL, \n'
 '\trevision_id VARCHAR(128), \n'
 '\tartifact_version BIGINT NOT NULL, \n'
 '\tdeleted BOOLEAN NOT NULL, \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT fk_artifact_history_owner FOREIGN KEY(workspace_id, artifact_id) REFERENCES '
 'artifacts.artifacts (workspace_id, id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_artifact_history_revision FOREIGN KEY(artifact_id, revision_id) REFERENCES '
 'artifacts.revisions (artifact_id, id), \n'
 '\tCONSTRAINT uq_artifact_history_version UNIQUE (artifact_id, from_catalog_version), \n'
 '\tCONSTRAINT ck_artifact_history_interval CHECK (from_catalog_version > 0 AND '
 '(until_catalog_version IS NULL OR until_catalog_version > from_catalog_version))\n'
 ')',
 'CREATE INDEX ix_artifact_history_visibility ON artifacts.head_history (workspace_id, '
 'from_catalog_version, until_catalog_version, artifact_id)',
 'CREATE UNIQUE INDEX uq_artifact_history_current ON artifacts.head_history (artifact_id) WHERE '
 'until_catalog_version IS NULL',
 'CREATE TABLE artifacts.grants (\n'
 '\tproject_id UUID NOT NULL, \n'
 '\tenvironment VARCHAR(16) NOT NULL, \n'
 '\tprincipal_id VARCHAR(128) NOT NULL, \n'
 '\tworkspace_id VARCHAR(128), \n'
 '\texternal_namespace VARCHAR(255), \n'
 '\tactions JSONB NOT NULL, \n'
 '\trevision BIGINT NOT NULL, \n'
 '\texpires_at TIMESTAMP WITH TIME ZONE, \n'
 '\trevoked BOOLEAN NOT NULL, \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT ck_artifact_grant_selector CHECK ((workspace_id IS NULL) <> (external_namespace IS '
 'NULL)), \n'
 '\tCONSTRAINT ck_artifact_grant_revision CHECK (revision >= 1), \n'
 '\tFOREIGN KEY(workspace_id) REFERENCES artifacts.workspaces (id) ON DELETE RESTRICT\n'
 ')',
 'CREATE INDEX ix_artifact_grants_principal_scope ON artifacts.grants (principal_id, project_id, '
 'environment)',
 'CREATE TABLE artifacts.uploads (\n'
 '\tworkspace_id VARCHAR(128) NOT NULL, \n'
 '\toperation_id VARCHAR(128) NOT NULL, \n'
 '\tprincipal_id VARCHAR(128) NOT NULL, \n'
 '\trequest_fingerprint VARCHAR(64) NOT NULL, \n'
 '\texpected_size BIGINT NOT NULL, \n'
 '\texpected_sha256 VARCHAR(64) NOT NULL, \n'
 '\tcontent_type VARCHAR(255) NOT NULL, \n'
 '\tpath VARCHAR(1024) NOT NULL, \n'
 '\tartifact_id VARCHAR(128), \n'
 '\texpected_revision VARCHAR(128), \n'
 '\t"offset" BIGINT NOT NULL, \n'
 '\tstatus VARCHAR(16) NOT NULL, \n'
 '\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\treceipt JSONB, \n'
 '\tparts JSONB NOT NULL, \n'
 '\tid VARCHAR(128) NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tPRIMARY KEY (id), \n'
 '\tCONSTRAINT uq_artifact_upload_operation UNIQUE (workspace_id, operation_id), \n'
 '\tCONSTRAINT ck_artifact_upload_offset CHECK (expected_size >= 0 AND "offset" >= 0 AND "offset" '
 '<= expected_size), \n'
 '\tCONSTRAINT ck_artifact_upload_status CHECK (status IN '
 "('created','uploading','verifying','committed','failed','aborted','expired')), \n"
 "\tCONSTRAINT ck_artifact_upload_receipt CHECK ((status = 'committed') = (receipt IS NOT "
 'NULL)), \n'
 '\tFOREIGN KEY(workspace_id) REFERENCES artifacts.workspaces (id) ON DELETE RESTRICT\n'
 ')',
 'CREATE INDEX ix_artifact_upload_expiration ON artifacts.uploads (status, expires_at)',
 'ALTER TABLE artifacts.artifacts ADD CONSTRAINT fk_artifact_current_revision FOREIGN KEY(id, '
 'revision_id) REFERENCES artifacts.revisions (artifact_id, id) DEFERRABLE INITIALLY DEFERRED',
 'CREATE FUNCTION artifacts.reject_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
 "RAISE EXCEPTION 'Artifact revisions are immutable'; END $$",
 'CREATE TRIGGER artifact_revision_immutable BEFORE UPDATE ON artifacts.revisions FOR EACH ROW '
 'EXECUTE FUNCTION artifacts.reject_revision_update()']


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.workspaces)')):
        raise RuntimeError('Export and purge Artifacts before downgrading its catalog')
    op.execute('DROP SCHEMA artifacts CASCADE')
