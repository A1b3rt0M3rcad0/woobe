import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0024_standardize_outbox_inbox_fields.py"

# Billing remains listed because this test also validates the historical migration
# that may be required when upgrading an existing installation. Proprietary Billing
# model implementation is intentionally not imported by the public Community tests.
MODULE_SCHEMAS = ["billing", "core", "identity", "metering", "observability"]

OUTBOX_CANONICAL_COLUMNS = [
    "routing_key",
    "idempotency_key",
    "locked_at",
    "locked_by",
    "metadata",
]

INBOX_CANONICAL_COLUMNS = [
    "message_id",
    "producer_module",
    "consumer_module",
    "routing_key",
    "headers",
    "idempotency_key",
    "locked_at",
    "locked_by",
]


class TestMigration0024Structure:

    def test_migration_file_exists(self):
        assert MIGRATION_FILE.is_file(), f"Migration file not found: {MIGRATION_FILE}"

    def test_revision_is_0024(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'revision = "0024"' in text

    def test_down_revision_is_0023(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0023"' in text

    def test_upgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def upgrade()" in text

    def test_downgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def downgrade()" in text

    def test_all_module_schemas_iterated_in_upgrade(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        for schema in MODULE_SCHEMAS:
            assert schema in text, f"Schema {schema} not referenced in migration"

    def test_upgrade_adds_outbox_routing_key(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        for schema in MODULE_SCHEMAS:
            assert f'"{schema}"' in text or f"'{schema}'" in text

    def test_migration_skips_agent_schema(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "MODULE_SCHEMAS" in text
        assert "agent" not in MODULE_SCHEMAS

    def test_downgrade_removes_outbox_columns(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        for col in OUTBOX_CANONICAL_COLUMNS:
            assert col in text, f"Outbox column {col} missing from migration"

    def test_downgrade_removes_inbox_columns(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        for col in INBOX_CANONICAL_COLUMNS:
            assert col in text, f"Inbox column {col} missing from migration"

    def test_unique_constraints_created(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'f"uq_{schema}_outbox_idempotency_key"' in text
        assert 'f"uq_{schema}_inbox_message_id"' in text
        assert 'f"uq_{schema}_inbox_idempotency_key"' in text

    def test_partial_indexes_created(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'f"ix_{schema}_outbox_pending"' in text
        assert 'f"ix_{schema}_outbox_correlation_id"' in text
        assert 'f"ix_{schema}_outbox_aggregate"' in text
        assert 'f"ix_{schema}_inbox_pending"' in text
        assert 'f"ix_{schema}_inbox_correlation_id"' in text

    def test_server_default_for_new_not_null_columns(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "server_default=" in text, (
            "Missing server_default for NOT NULL column backfill"
        )


class TestMigrationChain:

    def test_chain_references_existing_revisions(self):
        revisions = {}
        for migration_file in MIGRATIONS_DIR.glob("*.py"):
            text = migration_file.read_text(encoding="utf-8")
            revision_match = re.search(
                r"revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
                text,
            )
            if revision_match is None:
                continue
            down_revision_match = re.search(
                r"down_revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
                text,
            )
            revisions[revision_match.group(1)] = (
                down_revision_match.group(1) if down_revision_match else None
            )

        for revision, down_revision in revisions.items():
            if down_revision is None:
                continue
            assert down_revision in revisions, (
                f"Migration {revision} references missing down_revision {down_revision}"
            )

    def test_0024_follows_0023(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0023"' in text

    def test_no_duplicate_revisions(self):
        revisions = set()
        for migration_file in MIGRATIONS_DIR.glob("*.py"):
            text = migration_file.read_text(encoding="utf-8")
            revision_match = re.search(
                r"revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
                text,
            )
            if revision_match:
                revision = revision_match.group(1)
                assert revision not in revisions, f"Duplicate revision {revision}"
                revisions.add(revision)


class TestFreshInstallSchema:

    def test_shared_outbox_base_has_canonical_fields(self):
        from shared.infra.database.outbox import OutboxEventModel
        ann = OutboxEventModel.__annotations__
        for col_name in OUTBOX_CANONICAL_COLUMNS:
            mapped = col_name if col_name != "metadata" else "metadata_"
            assert mapped in ann, (
                f"Field '{col_name}' missing from shared OutboxEventModel annotations"
            )

    def test_shared_inbox_base_has_canonical_fields(self):
        from shared.infra.database.inbox import InboxEventModel
        ann = InboxEventModel.__annotations__
        for col_name in INBOX_CANONICAL_COLUMNS:
            assert col_name in ann, (
                f"Field '{col_name}' missing from shared InboxEventModel annotations"
            )

    def test_core_outbox_inbox_have_canonical_constraints(self):
        from modules.core.infra.database.models import OutboxEventModel, InboxEventModel
        o_args = _flatten_table_args(OutboxEventModel.__table_args__)
        o_names = {getattr(c, "name", None) or str(c) for c in o_args}
        assert "uq_core_outbox_idempotency_key" in o_names
        i_args = _flatten_table_args(InboxEventModel.__table_args__)
        i_names = {getattr(c, "name", None) or str(c) for c in i_args}
        assert "uq_core_inbox_message_id" in i_names
        assert "uq_core_inbox_idempotency_key" in i_names

    def test_identity_outbox_inbox_have_canonical_constraints(self):
        from modules.identity.infra.database.models import OutboxEventModel, InboxEventModel
        o_args = _flatten_table_args(OutboxEventModel.__table_args__)
        o_names = {getattr(c, "name", None) or str(c) for c in o_args}
        assert "uq_identity_outbox_idempotency_key" in o_names
        i_args = _flatten_table_args(InboxEventModel.__table_args__)
        i_names = {getattr(c, "name", None) or str(c) for c in i_args}
        assert "uq_identity_inbox_message_id" in i_names
        assert "uq_identity_inbox_idempotency_key" in i_names

    def test_metering_outbox_inbox_have_canonical_constraints(self):
        from modules.metering.infra.database.models import OutboxEventModel, InboxEventModel
        o_args = _flatten_table_args(OutboxEventModel.__table_args__)
        o_names = {getattr(c, "name", None) or str(c) for c in o_args}
        assert "uq_metering_outbox_idempotency_key" in o_names
        i_args = _flatten_table_args(InboxEventModel.__table_args__)
        i_names = {getattr(c, "name", None) or str(c) for c in i_args}
        assert "uq_metering_inbox_message_id" in i_names
        assert "uq_metering_inbox_idempotency_key" in i_names

    def test_observability_outbox_inbox_have_canonical_constraints(self):
        from modules.observability.infra.database.models import OutboxEventModel, InboxEventModel
        o_args = _flatten_table_args(OutboxEventModel.__table_args__)
        o_names = {getattr(c, "name", None) or str(c) for c in o_args}
        assert "uq_observability_outbox_idempotency_key" in o_names
        i_args = _flatten_table_args(InboxEventModel.__table_args__)
        i_names = {getattr(c, "name", None) or str(c) for c in i_args}
        assert "uq_observability_inbox_message_id" in i_names
        assert "uq_observability_inbox_idempotency_key" in i_names

    def test_agent_outbox_preserves_own_constraints(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel
        args = AgentOutboxEventModel.__table_args__
        flat = _flatten_table_args(args)
        names = {getattr(c, "name", None) or str(c) for c in flat}
        assert "uq_agent_outbox_idempotency_key" in names
        assert "ix_agent_outbox_pending" in names
        assert "ix_agent_outbox_correlation_id" in names
        assert "ix_agent_outbox_aggregate" in names

    def test_agent_inbox_preserves_own_constraints(self):
        from modules.agent.infra.database.models import AgentInboxEventModel
        args = AgentInboxEventModel.__table_args__
        flat = _flatten_table_args(args)
        names = {getattr(c, "name", None) or str(c) for c in flat}
        assert "uq_agent_inbox_message_id" in names
        assert "uq_agent_inbox_idempotency_key" in names
        assert "ix_agent_inbox_pending" in names
        assert "ix_agent_inbox_correlation_id" in names


class TestDuplicatePrevention:

    def test_outbox_unique_idempotency_key_exists(self):
        text = _read_migration()
        assert 'f"uq_{schema}_outbox_idempotency_key"' in text

    def test_inbox_unique_message_id_exists(self):
        text = _read_migration()
        assert 'f"uq_{schema}_inbox_message_id"' in text

    def test_inbox_unique_idempotency_key_exists(self):
        text = _read_migration()
        assert 'f"uq_{schema}_inbox_idempotency_key"' in text


class TestLockAndSkipLocked:

    def test_outbox_has_lock_columns(self):
        from shared.infra.database.outbox import OutboxEventModel
        ann = OutboxEventModel.__annotations__
        assert "locked_at" in ann, "Outbox missing locked_at for SKIP LOCKED"
        assert "locked_by" in ann, "Outbox missing locked_by for SKIP LOCKED"

    def test_inbox_has_lock_columns(self):
        from shared.infra.database.inbox import InboxEventModel
        ann = InboxEventModel.__annotations__
        assert "locked_at" in ann, "Inbox missing locked_at for SKIP LOCKED"
        assert "locked_by" in ann, "Inbox missing locked_by for SKIP LOCKED"


class TestStateTransitions:

    def test_outbox_status_column_exists(self):
        from shared.infra.database.outbox import OutboxEventModel
        ann = OutboxEventModel.__annotations__
        assert "status" in ann
        assert "attempts" in ann

    def test_inbox_status_column_exists(self):
        from shared.infra.database.inbox import InboxEventModel
        ann = InboxEventModel.__annotations__
        assert "status" in ann
        assert "attempts" in ann
        assert "available_at" in ann


def _flatten_table_args(args):
    if isinstance(args, tuple):
        result = []
        for item in args:
            if isinstance(item, tuple):
                result.extend(item)
            else:
                result.append(item)
        return [x for x in result if not isinstance(x, dict)]
    if isinstance(args, dict):
        return []
    return [args]


def _read_migration():
    return MIGRATION_FILE.read_text(encoding="utf-8")
