"""Architecture tests for spec 052 — create shared inbox consumer base."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_inbox_consumer_base_success():
    """Verify BaseInboxConsumer exists with required abstract methods."""
    from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

    assert hasattr(BaseInboxConsumer, "run")
    assert hasattr(BaseInboxConsumer, "consume")
    assert hasattr(BaseInboxConsumer, "persist_inbox")
    assert hasattr(BaseInboxConsumer, "acknowledge")
    assert hasattr(BaseInboxConsumer, "reject")

    fields = InboxRecord.__dataclass_fields__
    assert "outbox_origin_id" in fields
    assert "event_type" in fields
    assert "payload" in fields
    assert "correlation_id" in fields


def test_create_shared_inbox_consumer_base_rejects_forbidden_dependency():
    """Verify inbox_consumer_base.py does not import any module internals."""
    source_file = ROOT / "src" / "shared" / "workers" / "inbox_consumer_base.py"
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared inbox consumer base imports module internals: {violations}"


def test_create_shared_inbox_consumer_base_inherits_base_worker():
    """Verify BaseInboxConsumer inherits from BaseWorker."""
    from shared.workers.inbox_consumer_base import BaseInboxConsumer
    from shared.workers.base_worker import BaseWorker

    assert issubclass(BaseInboxConsumer, BaseWorker)
