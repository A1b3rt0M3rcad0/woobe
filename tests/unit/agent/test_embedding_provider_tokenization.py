from modules.agent.infra.models.embedding_providers import (
    build_embedding_provider_registry,
)


def test_compatible_embedding_servers_receive_author_text_without_openai_tokenization(
    monkeypatch,
):
    created = []
    monkeypatch.setattr(
        "modules.agent.infra.models.embedding_providers.OpenAIEmbeddings",
        lambda **kwargs: created.append(kwargs) or kwargs,
    )
    registry = build_embedding_provider_registry()
    for provider, local_tokenizer in (
        ("openai", True),
        ("custom", False),
        ("openrouter", False),
    ):
        client = registry.resolve(provider).create(
            model="author-model",
            api_key="fixture",
            base_url="https://embedding.test/v1",
        )
        assert client["check_embedding_ctx_length"] is local_tokenizer
        assert client["base_url"] == "https://embedding.test/v1"
        assert client["model"] == "author-model"
