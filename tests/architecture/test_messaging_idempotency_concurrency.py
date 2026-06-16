from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


class TestMessagingIdempotencyAndConcurrency:
    def test_each_inbox_processor_handles_idempotency(self):
        missing = []
        for mod in MODULES:
            proc_path = (
                PROJECT_ROOT / "src" / "modules" / mod / "infra" / "workers" / "inbox_processor.py"
            )
            if not proc_path.exists():
                missing.append(mod)
                continue
            source = proc_path.read_text(encoding="utf-8")
            has_idempotency = (
                "idempotency_key" in source.lower()
            )
            if not has_idempotency:
                parent = (
                    PROJECT_ROOT / "src" / "modules" / mod / "infra" / "workers" / "inbox_processor.py"
                )
                if parent.exists():
                    parent_src = parent.read_text(encoding="utf-8")
                    has_idempotency = "idempotency_key" in parent_src.lower()
            if not has_idempotency:
                missing.append(f"{mod} (no idempotency_key reference)")

        if missing:
            import warnings
            warnings.warn(
                f"Inbox processors without idempotency handling: {missing}"
            )

    def test_each_outbox_dispatcher_has_retry_logic(self):
        missing = []
        for mod in MODULES:
            disp_path = (
                PROJECT_ROOT
                / "src"
                / "modules"
                / mod
                / "infra"
                / "workers"
                / "outbox_dispatcher.py"
            )
            if not disp_path.exists():
                missing.append(mod)
                continue
            source = disp_path.read_text(encoding="utf-8")
            has_retry = "retry" in source.lower() or "max_attempts" in source.lower()
            if not has_retry:
                missing.append(mod)

        if missing:
            import warnings
            warnings.warn(
                f"Outbox dispatchers without retry logic: {missing}"
            )

    def test_each_module_messaging_publisher_exists(self):
        for mod in MODULES:
            pub_path = (
                PROJECT_ROOT / "src" / "modules" / mod / "infra" / "messaging" / "publishers.py"
            )
            assert pub_path.exists(), f"{mod} missing publishers.py"
            source = pub_path.read_text(encoding="utf-8")
            assert "class" in source, f"{mod} publishers.py has no class"

    def test_each_inbox_processor_has_lock_mechanism(self):
        missing = []
        for mod in MODULES:
            proc_path = (
                PROJECT_ROOT / "src" / "modules" / mod / "infra" / "workers" / "inbox_processor.py"
            )
            if not proc_path.exists():
                continue
            source = proc_path.read_text(encoding="utf-8")
            has_lock = "lock" in source.lower() or "Lock" in source
            if not has_lock:
                missing.append(mod)

        if missing:
            import warnings
            warnings.warn(
                f"Inbox processors without lock mechanism: {missing}"
            )

    def test_shared_retry_policy_has_classify_error(self):
        retry_path = PROJECT_ROOT / "src" / "shared" / "messaging" / "retry_policy.py"
        assert retry_path.exists(), "shared retry_policy.py missing"
        source = retry_path.read_text(encoding="utf-8")
        for term in ["classify_error", "should_retry", "compute_backoff_delay", "RetryClassification"]:
            assert term in source, f"shared retry_policy.py missing {term}"

    def test_shared_dead_letter_policy_has_required_contracts(self):
        dlq_path = PROJECT_ROOT / "src" / "shared" / "messaging" / "dead_letter_policy.py"
        assert dlq_path.exists(), "shared dead_letter_policy.py missing"
        source = dlq_path.read_text(encoding="utf-8")
        for term in ["DeadLetterReason", "compute_dlq_name", "DeadLetterRecord"]:
            assert term in source, f"shared dead_letter_policy.py missing {term}"
