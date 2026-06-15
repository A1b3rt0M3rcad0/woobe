"""Architecture tests for spec 053 — create shared inbox processor base."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_inbox_processor_base_success():
    """Verify BaseInboxProcessor exists with required abstract methods."""
    from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

    assert hasattr(BaseInboxProcessor, "run")
    assert hasattr(BaseInboxProcessor, "claim_pending")
    assert hasattr(BaseInboxProcessor, "process")
    assert hasattr(BaseInboxProcessor, "mark_processed")
    assert hasattr(BaseInboxProcessor, "mark_failed")
    assert hasattr(BaseInboxProcessor, "mark_dead")
    assert hasattr(BaseInboxProcessor, "mark_retryable")

    fields = InboxProcessingRecord.__dataclass_fields__
    assert "id" in fields
    assert "event_type" in fields
    assert "payload" in fields
    assert "attempts" in fields


def test_create_shared_inbox_processor_base_rejects_forbidden_dependency():
    """Verify inbox_processor_base.py does not import any module internals."""
    source_file = ROOT / "src" / "shared" / "workers" / "inbox_processor_base.py"
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared inbox processor base imports module internals: {violations}"


def test_create_shared_inbox_processor_base_inherits_base_worker():
    """Verify BaseInboxProcessor inherits from BaseWorker."""
    from shared.workers.inbox_processor_base import BaseInboxProcessor
    from shared.workers.base_worker import BaseWorker

    assert issubclass(BaseInboxProcessor, BaseWorker)
