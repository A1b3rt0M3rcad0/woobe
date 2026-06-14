"""Architecture tests for spec 051 — create shared outbox dispatcher base."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_outbox_dispatcher_base_success():
    """Verify BaseOutboxDispatcher exists with required abstract methods."""
    from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord

    assert hasattr(BaseOutboxDispatcher, "run")
    assert hasattr(BaseOutboxDispatcher, "claim_pending")
    assert hasattr(BaseOutboxDispatcher, "publish")
    assert hasattr(BaseOutboxDispatcher, "mark_published")
    assert hasattr(BaseOutboxDispatcher, "mark_failed")
    assert hasattr(BaseOutboxDispatcher, "mark_dead")
    assert hasattr(BaseOutboxDispatcher, "mark_retryable")

    fields = OutboxRecord.__dataclass_fields__
    assert "id" in fields
    assert "event_type" in fields
    assert "payload" in fields
    assert "attempts" in fields


def test_create_shared_outbox_dispatcher_base_rejects_forbidden_dependency():
    """Verify outbox_dispatcher_base.py does not import any module internals."""
    source_file = ROOT / "src" / "shared" / "workers" / "outbox_dispatcher_base.py"
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared outbox dispatcher base imports module internals: {violations}"


def test_create_shared_outbox_dispatcher_base_inherits_base_worker():
    """Verify BaseOutboxDispatcher inherits from BaseWorker."""
    from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher
    from shared.workers.base_worker import BaseWorker

    assert issubclass(BaseOutboxDispatcher, BaseWorker)
