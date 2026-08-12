from pathlib import Path


def test_network_module_does_not_expose_openai_compatible_routes() -> None:
    root = Path("src/modules/network")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "/v1/chat/completions" not in source
    assert "/v1/responses" not in source
    assert "/v1/models" not in source
