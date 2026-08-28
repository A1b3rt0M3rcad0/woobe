from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.infra.execution.instrumented_execution_runner import (
    _messages_with_bound_capability_authority,
)


def test_capability_authority_merges_into_existing_leading_system_message() -> None:
    messages = [
        SystemMessage(content="You are a support Agent."),
        HumanMessage(content="Help me with this request."),
    ]

    result = _messages_with_bound_capability_authority(messages, has_tools=True)

    assert len(result) == 2
    assert isinstance(result[0], SystemMessage)
    assert result[0].content.startswith("You are a support Agent.")
    assert "complete and authoritative" in result[0].content
    assert isinstance(result[1], HumanMessage)


def test_capability_authority_is_prefixed_when_no_system_message_exists() -> None:
    messages = [HumanMessage(content="Help me with this request.")]

    result = _messages_with_bound_capability_authority(messages, has_tools=True)

    assert len(result) == 2
    assert isinstance(result[0], SystemMessage)
    assert "complete and authoritative" in result[0].content
    assert result[1] is messages[0]


def test_capability_authority_does_not_change_messages_without_tools() -> None:
    messages = [HumanMessage(content="Answer directly.")]

    result = _messages_with_bound_capability_authority(messages, has_tools=False)

    assert result == messages
    assert result is not messages
