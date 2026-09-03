from types import SimpleNamespace

import worker_main


def test_worker_bootstrap_configures_one_bounded_http_executor(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeExecutor:
        def __init__(self, **kwargs) -> None:
            captured["kwargs"] = kwargs

    def configure(executor) -> None:
        captured["executor"] = executor

    monkeypatch.setattr(worker_main, "HttpToolExecutor", FakeExecutor)
    monkeypatch.setattr(worker_main, "configure_http_tool_executor", configure)
    settings = SimpleNamespace(
        http_tool_timeout_max_ms=12_000,
        http_tool_response_max_bytes=262_144,
        http_tool_allow_local_networks=False,
    )

    executor = worker_main._configure_http_tool_runtime(settings)

    assert executor is captured["executor"]
    assert captured["kwargs"] == {
        "default_timeout_ms": 12_000,
        "max_timeout_ms": 12_000,
        "max_response_bytes": 262_144,
        "allow_local_networks": False,
    }
