from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKERS_DIR = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "workers"
MESSAGING_DIR = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "messaging"

REQUIRED_WORKER_FILES = [
    "__init__.py",
    "ask_job_worker.py",
    "inbox_consumer.py",
    "inbox_processor.py",
    "outbox_dispatcher.py",
    "registry.py",
]

EXPECTED_WORKER_CLASSES = {
    "inbox_consumer.py": "AgentInboxConsumerWorker",
    "inbox_processor.py": "AgentInboxProcessorWorker",
    "outbox_dispatcher.py": "AgentOutboxDispatcherWorker",
    "registry.py": "AgentWorkerRegistry",
    "ask_job_worker.py": "AskJobWorker",
}


class TestNormalizeAgentWorkersAndRegistry:
    def test_workers_directory_exists(self):
        assert WORKERS_DIR.is_dir()

    def test_all_required_worker_files_exist(self):
        for name in REQUIRED_WORKER_FILES:
            file_path = WORKERS_DIR / name
            assert file_path.is_file(), f"Missing worker file: {name}"

    def test_all_worker_files_have_expected_classes(self):
        for filename, expected_class in EXPECTED_WORKER_CLASSES.items():
            content = (WORKERS_DIR / filename).read_text(encoding="utf-8")
            assert f"class {expected_class}" in content, \
                f"{filename} missing class {expected_class}"

    def test_outbox_dispatcher_is_populated(self):
        content = (WORKERS_DIR / "outbox_dispatcher.py").read_text(encoding="utf-8")
        assert "class AgentOutboxDispatcherWorker" in content
        assert "def claim_pending" in content
        assert "def publish" in content
        assert "def mark_published" in content

    def test_inbox_consumer_is_populated(self):
        content = (WORKERS_DIR / "inbox_consumer.py").read_text(encoding="utf-8")
        assert "class AgentInboxConsumerWorker" in content
        assert "def consume" in content
        assert "def _on_message" in content

    def test_inbox_processor_is_populated(self):
        content = (WORKERS_DIR / "inbox_processor.py").read_text(encoding="utf-8")
        assert "class AgentInboxProcessorWorker" in content
        assert "def process" in content
        assert "def claim_pending" in content

    def test_registry_is_populated(self):
        content = (WORKERS_DIR / "registry.py").read_text(encoding="utf-8")
        assert "class AgentWorkerRegistry" in content
        assert "def register_agent_workers" in content
        assert "AgentInboxConsumerWorker" in content
        assert "AgentInboxProcessorWorker" in content
        assert "AgentOutboxDispatcherWorker" in content

    def test_registry_registers_all_workers(self):
        content = (WORKERS_DIR / "registry.py").read_text(encoding="utf-8")
        assert "registry.register(outbox_dispatcher)" in content
        assert "registry.register(inbox_consumer)" in content
        assert "registry.register(inbox_processor)" in content

    def test_no_legacy_imports_in_worker_canonical_files(self):
        canonical = ["inbox_consumer.py", "inbox_processor.py", "outbox_dispatcher.py", "registry.py"]
        legacy_patterns = ["modules.ai", "modules.knowledge", "modules.runtime"]
        for filename in canonical:
            content = (WORKERS_DIR / filename).read_text(encoding="utf-8")
            for pattern in legacy_patterns:
                assert pattern not in content, \
                    f"{filename} contains legacy import: {pattern}"

    def test_ask_job_worker_uses_postgres_unit_of_work(self):
        content = (WORKERS_DIR / "ask_job_worker.py").read_text(encoding="utf-8")
        assert "PostgresUnitOfWork" in content, \
            "ask_job_worker still uses PostgresUnitOfWork (will be migrated in later spec)"

    def test_registry_exposes_worker_protocol(self):
        content = (WORKERS_DIR / "registry.py").read_text(encoding="utf-8")
        assert "WorkerProtocol" in content
        assert "WorkerRegistryProtocol" in content
        assert "def iter_workers" in content
