from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from modules.agent.infra.llm.langchain_factory import create_chat_model


def _model(name: str = "deepseek-v4-flash"):
    return create_chat_model(
        provider="custom",
        model=name,
        api_key="test-key",
        base_url="http://localhost:9999/v1",
        streaming=True,
    )


def test_deepseek_request_replays_reasoning_content() -> None:
    model = _model()
    messages = [
        HumanMessage(content="Investigate"),
        AIMessage(
            content="",
            additional_kwargs={"reasoning_content": "private reasoning"},
        ),
    ]

    payload = model._get_request_payload(messages)

    assert payload["messages"][1]["role"] == "assistant"
    assert payload["messages"][1]["reasoning_content"] == "private reasoning"


def test_deepseek_request_keeps_empty_reasoning_field_when_missing() -> None:
    model = _model()
    messages = [
        HumanMessage(content="Investigate"),
        AIMessage(content="No public reasoning"),
    ]

    payload = model._get_request_payload(messages)

    assert payload["messages"][1]["reasoning_content"] == ""


def test_deepseek_non_streaming_response_preserves_reasoning_content() -> None:
    model = _model()
    result = model._create_chat_result(
        {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "answer",
                        "reasoning_content": "private reasoning",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    )

    message = result.generations[0].message
    assert message.additional_kwargs["reasoning_content"] == "private reasoning"


def test_deepseek_stream_chunk_preserves_reasoning_content() -> None:
    model = _model()
    generation = model._convert_chunk_to_generation_chunk(
        {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "private ",
                    },
                    "finish_reason": None,
                }
            ],
        },
        AIMessageChunk,
        {},
    )

    assert generation is not None
    assert generation.message.additional_kwargs["reasoning_content"] == "private "


def test_non_deepseek_openai_compatible_model_does_not_inject_reasoning_content() -> None:
    model = _model("gpt-compatible")
    messages = [
        HumanMessage(content="Hello"),
        AIMessage(
            content="Answer",
            additional_kwargs={"reasoning_content": "provider-specific"},
        ),
    ]

    payload = model._get_request_payload(messages)

    assert "reasoning_content" not in payload["messages"][1]
