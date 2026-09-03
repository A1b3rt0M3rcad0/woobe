"""Architecture tests for cross-cutting messaging contracts (specs 090-100).

Each spec in the transversal phase adds validation clauses to this file.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
MIGRATIONS_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "migrations"
SHARED_MESSAGING_DIR = CORE_SRC / "shared" / "messaging"
WORKER_COMPOSITION = (
    PROJECT_ROOT / "packages" / "woobe-workers" / "src" / "module_registry_composition.py"
)

MODULES = ["agent", "billing", "core", "identity", "metering", "observability"]


def test_event_envelope_module_exists():
    """Spec 090: shared.messaging.event_envelope must exist."""
    from shared.messaging import event_envelope  # noqa: F811
    assert hasattr(event_envelope, "EventEnvelope")
    assert hasattr(event_envelope, "validate_event_envelope")


def test_event_envelope_has_required_fields():
    """Spec 090: EventEnvelope must define event_id, event_type, event_version,
    occurred_at, producer_module, routing_key, payload, idempotency_key,
    correlation_id as required fields."""
    from shared.messaging.event_envelope import REQUIRED_ENVELOPE_FIELDS
    expected = frozenset({
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    })
    assert expected.issubset(REQUIRED_ENVELOPE_FIELDS), (
        f"Expected {expected} to be subset of REQUIRED_ENVELOPE_FIELDS"
    )


def test_event_envelope_has_validation():
    """Spec 090: validate_event_envelope function must be callable."""
    from shared.messaging.event_envelope import validate_event_envelope
    assert callable(validate_event_envelope)


def test_event_envelope_has_causation_id():
    """Spec 090: EventEnvelope dataclass must accept causation_id (optional)."""
    from shared.messaging.event_envelope import EventEnvelope
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "causation_id" in fields


def test_event_envelope_has_metadata():
    """Spec 090: EventEnvelope dataclass must accept metadata (optional container)."""
    from shared.messaging.event_envelope import EventEnvelope
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "metadata" in fields


def test_event_envelope_has_event_type_pattern():
    """Spec 090: EVENT_TYPE_PATTERN regex must be defined."""
    from shared.messaging.event_envelope import EVENT_TYPE_PATTERN
    assert EVENT_TYPE_PATTERN.match("agent.execution.requested.v1")
    assert not EVENT_TYPE_PATTERN.match("agent.execution_requested")
    assert not EVENT_TYPE_PATTERN.match("plain_string")


def test_event_envelope_has_routing_key_pattern():
    """Spec 090: ROUTING_KEY_PATTERN regex must be defined."""
    from shared.messaging.event_envelope import ROUTING_KEY_PATTERN
    assert ROUTING_KEY_PATTERN.match("agent.execution.requested.v1")


def test_shared_messaging_init_importable():
    """The shared.messaging package must be importable."""
    mod = importlib.import_module("shared.messaging")
    assert mod is not None


def test_shared_messaging_package_has_expected_modules():
    """All shared messaging contract modules must exist."""
    expected = {
        "event_envelope",
        "outbox_contracts",
        "inbox_contracts",
        "rabbitmq_topology",
        "retry_policy",
        "dead_letter_policy",
        "idempotency_contracts",
        "versioning_policy",
        "compatibility_policy",
    }
    found = {p.stem for p in SHARED_MESSAGING_DIR.glob("*.py") if p.stem != "__init__"}
    missing = expected - found
    assert not missing, f"Missing shared messaging modules: {missing}"


# --- Spec 091: Outbox contract ---


def test_outbox_contracts_module_exists():
    """Spec 091: shared.messaging.outbox_contracts must exist."""
    from shared.messaging import outbox_contracts
    assert hasattr(outbox_contracts, "OutboxEventProtocol")
    assert hasattr(outbox_contracts, "validate_outbox_envelope")


def test_outbox_contracts_has_required_envelope_fields():
    """Spec 091: REQUIRED_ENVELOPE_FIELDS must include all mandated fields."""
    from shared.messaging.outbox_contracts import REQUIRED_ENVELOPE_FIELDS
    expected = frozenset({
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    })
    assert expected.issubset(REQUIRED_ENVELOPE_FIELDS)


def test_outbox_contracts_has_validation_function():
    """Spec 091: validate_outbox_envelope must be callable."""
    from shared.messaging.outbox_contracts import validate_outbox_envelope
    assert callable(validate_outbox_envelope)


def test_outbox_contracts_has_protocol():
    """Spec 091: OutboxEventProtocol must define event_type, routing_key
    and other expected properties."""
    from shared.messaging.outbox_contracts import OutboxEventProtocol
    props = ["event_type", "event_version", "routing_key",
             "idempotency_key", "correlation_id", "payload", "status"]
    for p in props:
        assert hasattr(OutboxEventProtocol, p), (
            f"OutboxEventProtocol missing property: {p}"
        )


def test_shared_domain_events_has_abstract_outbox_writer():
    """Spec 091: shared.domain.events.OutboxEventWriter must exist with abstract write()."""
    from shared.messaging.outbox_writer import OutboxEventWriter
    assert hasattr(OutboxEventWriter.write, "__isabstractmethod__")


def test_each_module_outbox_event_writer_exists():
    """Every canonical module has a SQLAlchemyOutboxEventWriter in infra/database/repositories."""
    modules = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]
    for mod_name in modules:
        try:
            mod = importlib.import_module(
                f"modules.{mod_name}.infra.database.repositories"
            )
        except ModuleNotFoundError:
            pytest.skip(f"No infra/database/repositories for {mod_name}")
        writers = [
            cls for name, cls in vars(mod).items()
            if name.endswith("OutboxEventWriter") and hasattr(cls, "write")
        ]
        assert len(writers) >= 1, (
            f"{mod_name} must have at least one OutboxEventWriter"
        )


# --- Spec 092: Inbox contract ---


def test_inbox_contracts_module_exists():
    """Spec 092: shared.messaging.inbox_contracts must exist."""
    from shared.messaging import inbox_contracts
    assert hasattr(inbox_contracts, "InboxEventProtocol")
    assert hasattr(inbox_contracts, "validate_inbox_envelope")


def test_inbox_contracts_has_required_fields():
    """Spec 092: REQUIRED_INBOX_ENVELOPE_FIELDS must include all mandated fields."""
    from shared.messaging.inbox_contracts import REQUIRED_INBOX_ENVELOPE_FIELDS
    expected = frozenset({
        "event_type",
        "event_version",
        "routing_key",
        "idempotency_key",
        "correlation_id",
        "producer_module",
        "occurred_at",
        "payload",
    })
    assert expected.issubset(REQUIRED_INBOX_ENVELOPE_FIELDS)


def test_inbox_contracts_has_validation_function():
    """Spec 092: validate_inbox_envelope must be callable."""
    from shared.messaging.inbox_contracts import validate_inbox_envelope
    assert callable(validate_inbox_envelope)


def test_inbox_contracts_has_protocol():
    """Spec 092: InboxEventProtocol must define all expected properties."""
    from shared.messaging.inbox_contracts import InboxEventProtocol
    props = ["message_id", "producer_module", "consumer_module",
             "event_type", "event_version", "routing_key",
             "idempotency_key", "correlation_id", "payload", "status"]
    for p in props:
        assert hasattr(InboxEventProtocol, p), (
            f"InboxEventProtocol missing property: {p}"
        )


def test_shared_infra_database_inbox_model_exists():
    """Spec 092: shared.infra.database.inbox.InboxEventModel must exist as abstract."""
    from shared.infra.database.inbox import InboxEventModel
    assert hasattr(InboxEventModel, "__abstract__")


def test_each_module_has_inbox_event_model():
    """Every canonical module has an InboxEventModel in infra/database/models."""
    modules = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]
    for mod_name in modules:
        try:
            mod = importlib.import_module(
                f"modules.{mod_name}.infra.database.models"
            )
        except ModuleNotFoundError:
            pytest.skip(f"No infra/database/models for {mod_name}")
        models = [
            cls for name, cls in vars(mod).items()
            if name == "InboxEventModel" and hasattr(cls, "__tablename__")
        ]
        if not models:
            models = [
                cls for name, cls in vars(mod).items()
                if name.endswith("InboxEventModel") and hasattr(cls, "__tablename__")
            ]
        assert len(models) >= 1, (
            f"{mod_name} must have at least one InboxEventModel"
        )


# --- Spec 093: RabbitMQ topology ---


def test_rabbitmq_topology_module_exists():
    """Spec 093: shared.messaging.rabbitmq_topology must exist."""
    from shared.messaging import rabbitmq_topology
    assert hasattr(rabbitmq_topology, "EXCHANGE_NAME")
    assert hasattr(rabbitmq_topology, "compute_queue_name")
    assert hasattr(rabbitmq_topology, "validate_routing_key")


def test_rabbitmq_topology_exchange_constants():
    """Spec 093: EXCHANGE_NAME, EXCHANGE_TYPE, EXCHANGE_DURABLE must be defined."""
    from shared.messaging.rabbitmq_topology import (
        EXCHANGE_NAME,
        EXCHANGE_TYPE,
        EXCHANGE_DURABLE,
    )
    assert EXCHANGE_NAME == "domain.events"
    assert EXCHANGE_TYPE == "topic"
    assert EXCHANGE_DURABLE is True


def test_rabbitmq_topology_has_validation_functions():
    """Spec 093: validate_queue_name, validate_routing_key, validate_binding
    and validate_exchange_declaration must be callable."""
    from shared.messaging.rabbitmq_topology import (
        validate_queue_name,
        validate_routing_key,
        validate_binding,
        validate_exchange_declaration,
    )
    assert callable(validate_queue_name)
    assert callable(validate_routing_key)
    assert callable(validate_binding)
    assert callable(validate_exchange_declaration)


def test_rabbitmq_topology_has_topology_config():
    """Spec 093: TopologyConfig dataclass must exist."""
    from shared.messaging.rabbitmq_topology import TopologyConfig
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    assert config.queue_name == "agent.billing-events"


def test_rabbitmq_topology_has_validate_topology_config():
    """Spec 093: validate_topology_config must be callable."""
    from shared.messaging.rabbitmq_topology import (
        TopologyConfig,
        validate_topology_config,
    )
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    validate_topology_config(config)


def test_rabbitmq_topology_has_compute_dlq_name():
    """Spec 093: compute_dlq_name_for_queue must exist."""
    from shared.messaging.rabbitmq_topology import compute_dlq_name_for_queue
    assert callable(compute_dlq_name_for_queue)
    assert compute_dlq_name_for_queue("agent.billing-events") == "agent.billing-events.dlq"


def test_rabbitmq_topology_has_extract_producer():
    """Spec 093: extract_producer_from_routing_key must exist."""
    from shared.messaging.rabbitmq_topology import extract_producer_from_routing_key
    assert extract_producer_from_routing_key("agent.execution.requested.v1") == "agent"


def test_rabbitmq_topology_has_extract_version():
    """Spec 093: extract_version_from_routing_key must exist."""
    from shared.messaging.rabbitmq_topology import extract_version_from_routing_key
    assert extract_version_from_routing_key("agent.execution.requested.v1") == 1


# --- Spec 094: Idempotency, Retry, Dead Letter ---


def test_idempotency_contracts_module_exists():
    """Spec 094: shared.messaging.idempotency_contracts must exist."""
    from shared.messaging import idempotency_contracts
    assert hasattr(idempotency_contracts, "validate_idempotency_key")
    assert hasattr(idempotency_contracts, "assert_idempotency_constraints")


def test_idempotency_contracts_has_validate_function():
    """Spec 094: validate_idempotency_key must be callable."""
    from shared.messaging.idempotency_contracts import validate_idempotency_key
    assert callable(validate_idempotency_key)


def test_retry_policy_module_exists():
    """Spec 094: shared.messaging.retry_policy must exist."""
    from shared.messaging import retry_policy
    assert hasattr(retry_policy, "RetryClassification")
    assert hasattr(retry_policy, "classify_error")
    assert hasattr(retry_policy, "compute_backoff_delay")
    assert hasattr(retry_policy, "should_retry")


def test_retry_policy_has_classification():
    """Spec 094: RetryClassification must have TRANSIENT and PERMANENT."""
    from shared.messaging.retry_policy import RetryClassification
    assert RetryClassification.TRANSIENT is not None
    assert RetryClassification.PERMANENT is not None


def test_retry_policy_has_classify_error():
    """Spec 094: classify_error must be callable."""
    from shared.messaging.retry_policy import classify_error
    assert callable(classify_error)


def test_retry_policy_has_compute_backoff():
    """Spec 094: compute_backoff_delay must be callable."""
    from shared.messaging.retry_policy import compute_backoff_delay
    delay = compute_backoff_delay(1)
    assert delay > 0


def test_retry_policy_has_should_retry():
    """Spec 094: should_retry must be callable."""
    from shared.messaging.retry_policy import should_retry
    assert callable(should_retry)


def test_dead_letter_policy_module_exists():
    """Spec 094: shared.messaging.dead_letter_policy must exist."""
    from shared.messaging import dead_letter_policy
    assert hasattr(dead_letter_policy, "DeadLetterReason")
    assert hasattr(dead_letter_policy, "compute_dlq_name")
    assert hasattr(dead_letter_policy, "DeadLetterRecord")


def test_dead_letter_policy_has_dlq_name():
    """Spec 094: compute_dlq_name must be callable."""
    from shared.messaging.dead_letter_policy import compute_dlq_name
    assert compute_dlq_name("agent.test-events") == "agent.test-events.dlq"


def test_dead_letter_policy_has_headers():
    """Spec 094: dead_letter_headers must produce valid headers."""
    from shared.messaging.dead_letter_policy import (
        DeadLetterReason,
        dead_letter_headers,
        verify_dlq_headers,
    )
    headers = dead_letter_headers(
        reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
        original_routing_key="a.b.v1",
        original_producer_module="test",
        attempts=3,
        error="err",
    )
    assert headers
    assert verify_dlq_headers(headers)


def test_dead_letter_policy_has_record():
    """Spec 094: create_dead_letter_record must return DeadLetterRecord."""
    from shared.messaging.dead_letter_policy import (
        DeadLetterReason,
        create_dead_letter_record,
    )
    record = create_dead_letter_record(
        reason=DeadLetterReason.PERMANENT_ERROR,
        original_routing_key="a.b.v1",
        original_producer_module="test",
    )
    assert record is not None


# --- Spec 095: Wire central runner to module worker registries ---


def test_worker_discovery_lives_in_process_composition_root():
    """Spec 095: concrete module discovery belongs to the worker process root."""
    shared_discovery = CORE_SRC / "shared" / "workers" / "discovery.py"
    assert not shared_discovery.exists(), (
        "shared.workers must not know concrete bounded-context module names"
    )
    assert WORKER_COMPOSITION.is_file()
    source = WORKER_COMPOSITION.read_text(encoding="utf-8")
    assert "CORE_MODULE_WORKER_REGISTRIES" in source
    assert "def discover_module_entries" in source
    assert "def build_registries" in source
    for module_name in ("agent", "core", "identity", "metering", "network", "observability"):
        assert f'"{module_name}"' in source


def test_module_worker_entry_is_neutral_shared_contract():
    """Spec 095: shared owns only the process-neutral worker contract."""
    from shared.workers.contracts import ModuleWorkerEntry

    contract_path = CORE_SRC / "shared" / "workers" / "contracts.py"
    source = contract_path.read_text(encoding="utf-8")
    assert not hasattr(ModuleWorkerEntry, "event_type")
    assert not hasattr(ModuleWorkerEntry, "routing_key")
    assert "modules." not in source
    assert "importlib" not in source


def test_worker_process_composition_imports_shared_contract_only():
    """Spec 095: process composition may discover modules through the neutral contract."""
    source = WORKER_COMPOSITION.read_text(encoding="utf-8")
    assert "from shared.workers.contracts import ModuleWorkerEntry" in source
    assert "importlib" in source


def test_worker_runner_module_exists():
    """Spec 095: WorkerRunner must exist."""
    from shared.workers.runner import WorkerRunner
    assert callable(WorkerRunner.from_registries)
    assert callable(WorkerRunner)


# --- Spec 096: Clean shared — keep only technical contracts ---


def test_shared_domain_removed():
    """Spec 096: shared/domain/ directory must not exist."""
    assert not SHARED_MESSAGING_DIR.parent.joinpath("domain").is_dir()


def test_shared_application_removed():
    """Spec 096: shared/application/ directory must not exist."""
    assert not SHARED_MESSAGING_DIR.parent.joinpath("application").is_dir()


def test_shared_workers_no_concrete():
    """Spec 096: shared/workers/ has no concrete worker implementations."""
    concrete = {"inbox_consumer.py", "inbox_dispatcher.py", "outbox_publisher.py", "discovery.py"}
    wdir = SHARED_MESSAGING_DIR.parent.joinpath("workers")
    if wdir.is_dir():
        existing = {p.name for p in wdir.iterdir() if p.suffix == ".py"}
        assert not (concrete & existing)


def test_shared_infra_errors_exists():
    """Spec 096: shared/infra/errors.py must exist (relocated from domain)."""
    assert SHARED_MESSAGING_DIR.parent.joinpath("infra", "errors.py").is_file()


def test_shared_messaging_outbox_writer_exists():
    """Spec 096: shared/messaging/outbox_writer.py must exist (relocated from domain)."""
    mod = importlib.import_module("shared.messaging.outbox_writer")
    writer_cls = getattr(mod, "OutboxEventWriter")
    assert hasattr(writer_cls.write, "__isabstractmethod__")


# --- Spec 097: Bootstrap, DI and config ---


def test_each_module_has_uow_in_database():
    """Spec 097: Every canonical module has a UoW in infra/database/unit_of_work."""
    for mod_name in MODULES:
        uow_path = f"modules.{mod_name}.infra.database.unit_of_work"
        mod = importlib.import_module(uow_path)
        uow_name = f"{mod_name.capitalize()}UnitOfWork"
        assert hasattr(mod, uow_name), f"{mod_name} missing {uow_name}"


def test_each_module_uow_has_outbox_property():
    """Spec 097: Every module UoW defines an outbox property."""
    for mod_name in MODULES:
        uow_mod = importlib.import_module(
            f"modules.{mod_name}.infra.database.unit_of_work"
        )
        uow_name = f"{mod_name.capitalize()}UnitOfWork"
        uow_cls = getattr(uow_mod, uow_name)
        assert hasattr(uow_cls, "outbox"), (
            f"{uow_name} missing outbox"
        )


def test_settings_has_required_fields():
    """Spec 097: Settings must define database_url, rabbitmq_url,
    rabbitmq_exchange, cors_origins, secret_key."""
    from shared.infra.config import Settings
    required = {"database_url", "rabbitmq_url", "rabbitmq_exchange",
                "cors_origins", "secret_key", "encryption_key"}
    existing = set(Settings.model_fields.keys())
    missing = required - existing
    assert not missing, f"Settings missing: {missing}"


# --- Spec 098: Alembic expand-migrate contract ---


def test_alembic_env_imports_canonical_modules():
    """Spec 098: env.py must import from canonical module paths."""
    env_text = (MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8")
    for mod in MODULES:
        assert f"modules.{mod}.infra.database.models" in env_text, (
            f"env.py missing {mod}"
        )


def test_alembic_env_no_legacy_schemas():
    """Spec 098: env.py must not import legacy ai/knowledge/runtime."""
    env_text = (MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8")
    for legacy in ("modules.ai", "modules.knowledge", "modules.runtime"):
        assert legacy not in env_text, (
            f"env.py still references {legacy}"
        )


def test_alembic_versions_have_upgrade_downgrade():
    """Spec 098: all migration versions define upgrade() and downgrade()."""
    versions = sorted((MIGRATIONS_DIR / "versions").glob("[0-9]*.py"))
    assert len(versions) > 0
    for v in versions:
        text = v.read_text(encoding="utf-8")
        assert "def upgrade()" in text, f"{v.name} missing upgrade()"
        assert "def downgrade()" in text, f"{v.name} missing downgrade()"


def test_alembic_no_destructive_rename():
    """Spec 098: no destructive rename_table in migrations."""
    for v in (MIGRATIONS_DIR / "versions").glob("*.py"):
        if v.name == "__init__.py":
            continue
        text = v.read_text(encoding="utf-8")
        assert "op.rename_table" not in text, f"{v.name} uses rename_table"


# --- Spec 099: Remove cross-module FKs and legacy schema refs ---


def test_no_legacy_ai_schema_in_agent_models():
    """Spec 099: agent models must not reference legacy ai schema."""
    text = (
        CORE_SRC / "modules" / "agent" / "infra" / "database" / "models.py"
    ).read_text(encoding="utf-8")
    assert '"ai.' not in text, "agent models still reference ai schema"
    assert '"knowledge.' not in text, "agent models still reference knowledge schema"
    assert '"runtime.' not in text, "agent models still reference runtime schema"


# --- Spec 100: Final layer dependency tests ---


def test_all_modules_have_canonical_layers():
    """Spec 100: every module must have domain, application, infra, presentation dirs."""
    required = {"domain", "application", "infra", "presentation"}
    for mod in MODULES:
        module_path = CORE_SRC / "modules" / mod
        present = {d.name for d in module_path.iterdir() if d.is_dir() and not d.name.startswith("_")}
        missing = required - present
        assert not missing, f"{mod}: missing canonical layer(s): {missing}"


PROJECT_ROOT_SPEC100 = PROJECT_ROOT
ALLOWLIST_FILE_SPEC100 = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"


def _relative_posix(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT_SPEC100).as_posix()
    except ValueError:
        return path.resolve().relative_to(PROJECT_ROOT_SPEC100).as_posix()


def _load_allowlist_spec100(scope: str) -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE_SPEC100.exists():
        return set()
    with open(ALLOWLIST_FILE_SPEC100, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("/", "\\").replace("\\", "/"), e.get("target_layer", ""))
        for e in entries
        if e.get("scope") == scope
    }


FORBIDDEN_WORKER_PATHS = [
    CORE_SRC / "shared" / "workers",
    PROJECT_ROOT / "packages" / "woobe-workers" / "src",
]


def test_no_concrete_workers_outside_modules():
    """Spec 100: concrete workers must only live in modules/*/infra/workers/."""
    for p in FORBIDDEN_WORKER_PATHS:
        if not p.exists():
            continue
        for py_file in p.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            if "class " in text and "async def run" in text and "abstractmethod" not in text and "Protocol" not in text:
                rel = _relative_posix(py_file)
                pytest.fail(f"Concrete worker found at {rel}")


def test_shared_infra_does_not_import_modules():
    """Spec 100: shared/ infra must not import from any module."""
    shared_infra = CORE_SRC / "shared" / "infra"
    for py_file in shared_infra.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "from modules" in text or "import modules" in text:
            pytest.fail(f"{_relative_posix(py_file)} imports from a module")


def test_shared_messaging_does_not_import_modules():
    """Spec 100: shared/ messaging must not import from any module."""
    for py_file in SHARED_MESSAGING_DIR.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "from modules" in text or "import modules" in text:
            pytest.fail(f"{_relative_posix(py_file)} imports from a module")


def test_all_layers_follow_dependency_direction():
    """Spec 100: validate layer direction rules across ALL modules via AST.

    Rules enforced:
      - domain/ may NOT import from application, infra, presentation
      - presentation/ may NOT import from infra
      - use_cases may NOT import from infra
    """
    allowlist = _load_allowlist_spec100("layer_dependencies")
    violations = []

    for mod in MODULES:
        module_path = CORE_SRC / "modules" / mod
        for py_file in module_path.rglob("*.py"):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            is_domain = "/domain/" in rel
            is_presentation = "/presentation/" in rel
            is_use_case = "/service/use_cases.py" in rel or "/application/use_cases/" in rel
            is_composer = "/composers/" in rel

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                imp_parts = node.module.split(".")
                if (len(imp_parts) >= 4 and imp_parts[0] == "modules"
                        and imp_parts[1] == mod):
                    target = imp_parts[2]
                    if target not in {"domain", "application", "service", "infra", "presentation"}:
                        continue

                    if is_composer:
                        continue
                    if is_domain and target in ("application", "service", "infra", "presentation"):
                        if (rel, target) not in allowlist:
                            violations.append(f"{rel}: domain imports from {target} ({node.module})")
                    elif is_presentation and target == "infra":
                        if (rel, target) not in allowlist:
                            violations.append(f"{rel}: presentation imports from infra ({node.module})")
                    elif is_use_case and target == "infra":
                        if (rel, target) not in allowlist:
                            violations.append(f"{rel}: use_case imports from infra ({node.module})")

    assert not violations, (
        "Layer direction violations found:\n"
        + "\n".join(f"  - {v}" for v in violations[:30])
    )
