from typing import Any, Mapping

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.context_managers.standard import (
    _messages_with_bound_capability_authority,
)


class _MessageAdapter:
    def is_system(self, message: Any) -> bool:
        return isinstance(message, SystemMessage)

    def replace_content(self, message: Any, content: Any) -> Any:
        return message.model_copy(update={"content": content})

    def system_message(
        self,
        content: Any,
        *,
        context_metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        return SystemMessage(
            content=content,
            additional_kwargs=(
                {"woobe_context": dict(context_metadata)}
                if context_metadata is not None
                else {}
            ),
        )


_ADAPTER = _MessageAdapter()


def test_capability_authority_merges_into_existing_leading_system_message() -> None:
    messages = [
        SystemMessage(content="You are a support Agent."),
        HumanMessage(content="Help me with this request."),
    ]

    result = _messages_with_bound_capability_authority(
        messages,
        has_tools=True,
        adapter=_ADAPTER,
    )

    assert len(result) == 2
    assert isinstance(result[0], SystemMessage)
    assert result[0].content.startswith("You are a support Agent.")
    assert "complete and authoritative" in result[0].content
    assert isinstance(result[1], HumanMessage)


def test_capability_authority_is_prefixed_when_no_system_message_exists() -> None:
    messages = [HumanMessage(content="Help me with this request.")]

    result = _messages_with_bound_capability_authority(
        messages,
        has_tools=True,
        adapter=_ADAPTER,
    )

    assert len(result) == 2
    assert isinstance(result[0], SystemMessage)
    assert "complete and authoritative" in result[0].content
    assert result[1] is messages[0]


def test_capability_authority_does_not_change_messages_without_tools() -> None:
    messages = [HumanMessage(content="Answer directly.")]

    result = _messages_with_bound_capability_authority(
        messages,
        has_tools=False,
        adapter=_ADAPTER,
    )

    assert result == messages
    assert result is not messages
