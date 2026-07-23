from __future__ import annotations

from modules.agent.infra.llm import langchain_factory


def test_openai_compatible_factory_forwards_inference_extra_body(monkeypatch) -> None:
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(langchain_factory, "ChatOpenAI", fake_chat_openai)

    langchain_factory.create_chat_model(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        api_key="secret",
        max_tokens=3000,
        response_format={"type": "json_object"},
        extra_body={"reasoning": {"effort": "none", "exclude": True}},
    )

    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["max_tokens"] == 3000
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["extra_body"] == {
        "reasoning": {"effort": "none", "exclude": True}
    }
