from uuid import uuid4
import pytest

from modules.agent.application.dtos import CreatePromptInput
from modules.agent.application.use_cases.ai_prompt_cases import CreatePromptUseCase
from modules.agent.presentation.mappers import prompt_to_response


@pytest.mark.asyncio
async def test_native_prompt_creation_preserves_response_content_hash():
    class Repository:
        async def save(self, prompt):
            return prompt

    result = await CreatePromptUseCase(Repository()).execute(
        CreatePromptInput(
            project_id=uuid4(),
            agent_id=uuid4(),
            version="1.0.0",
            name="Instructions",
            content="Portable prompt",
            content_hash="frozen-prompt-hash",
        )
    )
    assert result.content_hash == "frozen-prompt-hash"
    assert prompt_to_response(result).content_hash == "frozen-prompt-hash"
