import pytest
from pydantic import ValidationError
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.dtos.runtime_dtos import AskInput, SendMessageInput, UsageInfo
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.agent.infra.execution.frozen_snapshot_runtime import _messages_to_history
from shared.contracts.errors import ValidationError as DomainValidationError
from shared.contracts.content_parts import (
    ArtifactContentPart,
    ContentParts,
    TextContentPart,
    normalize_message_parts,
    serialize_message_content_parts,
)
from modules.network.presentation.schemas import RunNetworkRequest
from modules.network.infra.services.service import _same_idempotent_input
from modules.agent.presentation.controllers.public_runtime_controllers import (
    build_internal_runtime_body,
)


def test_legacy_text_normalizes_without_changing_the_public_projection():
    message, parts = normalize_message_parts('Hello from an older client', None)
    assert message == 'Hello from an older client'
    assert parts == (TextContentPart(text='Hello from an older client'),)
    assert AskInput(project_id='7ad97368-e5ca-47ac-9182-54c804f76ff7',
        agent_id='67e4cc89-e01b-4e6f-9754-58b928b31515', message='legacy').message == 'legacy'
    assert serialize_message_content_parts('legacy', None) == [
        {'type': 'text', 'text': 'legacy'}
    ]


def test_text_and_typed_artifact_parts_roundtrip_without_bytes_or_urls():
    value = ContentParts(parts=(
        TextContentPart(text='Summarize this attachment'),
        ArtifactContentPart(type='artifact', ref={
            'artifact_id': 'artifact-1', 'revision_id': 'revision-1',
        }, media_type_hint='application/pdf'),
    ))
    encoded = [part.model_dump(mode='json') for part in value.parts]
    assert encoded == [
        {'type': 'text', 'text': 'Summarize this attachment'},
        {'type': 'artifact', 'ref': {'artifact_id': 'artifact-1', 'revision_id': 'revision-1'},
         'media_type_hint': 'application/pdf'},
    ]
    assert 'base64' not in str(encoded) and 'url' not in str(encoded)


def test_public_agent_and_network_accept_text_or_image_only_parts_but_reject_ambiguity():
    parts = ({
        'type': 'artifact',
        'ref': {'artifact_id': 'image-1', 'revision_id': 'image-revision-1'},
        'media_type_hint': 'image/png',
    },)
    agent = PublicRunRequest(content_parts=parts)
    ask = AskInput(
        project_id='7ad97368-e5ca-47ac-9182-54c804f76ff7',
        agent_id='67e4cc89-e01b-4e6f-9754-58b928b31515',
        content_parts=parts,
    )
    network = RunNetworkRequest(
        project_id='7ad97368-e5ca-47ac-9182-54c804f76ff7',
        network_session_id='b1843cf7-df0a-4b07-896c-4b12690e3a92',
        content_parts=parts,
    )
    assert agent.message == ask.message == network.message == ''
    assert ask.content_parts[0].ref.revision_id == 'image-revision-1'

    with pytest.raises(ValidationError):
        PublicRunRequest(message='legacy text', content_parts=parts)
    with pytest.raises(ValueError):
        normalize_message_parts(None, ())


def test_session_messages_persist_typed_parts_instead_of_blobs_or_urls():
    request = SendMessageInput(session_id='b1843cf7-df0a-4b07-896c-4b12690e3a92', content_parts=(
        {'type': 'artifact', 'ref': {
            'artifact_id': 'artifact-1', 'revision_id': 'revision-1',
        }},
    ))
    assert request.content == ''
    assert request.content_parts[0].type == 'artifact'


@pytest.mark.asyncio
async def test_agent_history_and_result_metadata_keep_exact_typed_references():
    runtime = object.__new__(AskAgentUseCase)
    session = SimpleNamespace(
        id=uuid4(), project_id=uuid4(), agent_id=uuid4(), last_message_at=None
    )
    agent = SimpleNamespace(id=session.agent_id)

    class _Messages:
        def __init__(self):
            self.items = []

        async def create(self, message):
            self.items.append(message)
            return message

        async def list_by_session(self, _session_id):
            return self.items

    class _Sessions:
        async def update(self, value):
            return value

    parts = (
        ArtifactContentPart(type='artifact', ref={
            'artifact_id': 'report-1', 'revision_id': 'report-revision-3',
        }),
    )
    messages = _Messages()
    user = await runtime._save_user_message(
        _Sessions(), messages, session, '', agent, parts
    )
    assistant = await runtime._do_save_assistant_message(
        messages, _Sessions(), SimpleNamespace(write=AsyncMock()), session,
        'answer', UsageInfo(), agent, content_parts=parts,
    )
    expected = [{
        'type': 'artifact',
        'ref': {'artifact_id': 'report-1', 'revision_id': 'report-revision-3'},
        'media_type_hint': None,
    }]
    assert user.content == '' and user.data['content_parts'] == expected
    assert assistant.data['input_content_parts'] == expected
    history = await runtime._load_history(messages, session)
    assert history[0].response_metadata['woobe_content_parts'] == expected
    recovered_history = _messages_to_history([user])
    assert recovered_history[0].response_metadata['woobe_content_parts'] == expected
    assert 'base64' not in str(user.data) and 'url' not in str(assistant.data)


def test_media_type_hints_and_content_budgets_are_validated():
    with pytest.raises(ValidationError):
        ArtifactContentPart(type='artifact', ref={
            'artifact_id': 'artifact-1', 'revision_id': 'revision-1',
        }, media_type_hint='not a media type')
    with pytest.raises(ValidationError):
        ContentParts(parts=tuple(TextContentPart(text='x') for _ in range(33)))
    with pytest.raises(ValidationError):
        ContentParts(parts=(TextContentPart(text=' '),))


def test_public_runtime_projection_and_idempotency_keep_legacy_clients_compatible():
    project_id, agent_id = '7ad97368-e5ca-47ac-9182-54c804f76ff7', '67e4cc89-e01b-4e6f-9754-58b928b31515'
    payload = PublicRunRequest(message='hello')
    body = build_internal_runtime_body(
        payload,
        SimpleNamespace(project_id=project_id, agent_id=agent_id, environment='staging'),
    )
    assert body['message'] == 'hello' and 'content_parts' not in body

    accepted = SimpleNamespace(
        input_message='',
        input_content_parts=[{
            'type': 'artifact',
            'ref': {'artifact_id': 'image-1', 'revision_id': 'revision-1'},
        }],
    )
    assert not _same_idempotent_input(accepted, '', [])
    accepted.input_message = 'hello'
    accepted.input_content_parts = []
    assert _same_idempotent_input(
        accepted, 'hello', [{'type': 'text', 'text': 'hello'}]
    )


@pytest.mark.asyncio
async def test_resolved_artifact_ref_is_rejected_before_unsupported_provider_call():
    runtime = object.__new__(AskAgentUseCase)
    runtime._prepare = AsyncMock(
        return_value=(
            SimpleNamespace(), None, uuid4(), None, None, {}, False, [], {}, False,
            [], [], [],
        )
    )
    runtime._fail = AsyncMock()
    runtime._execute_llm = AsyncMock(side_effect=AssertionError('provider must not run'))
    runtime._llm_factory = SimpleNamespace()
    request = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        content_parts=(
            {
                'type': 'artifact',
                'ref': {'artifact_id': 'image-1', 'revision_id': 'image-revision-1'},
                'media_type_hint': 'text/plain',
            },
        ),
    )
    request.resolved_content_parts = ({
        'artifact_id': 'image-1',
        'revision_id': 'image-revision-1',
        'content_type': 'text/plain',
        'size_bytes': 12,
        'source_sha256': 'a' * 64,
    },)

    with pytest.raises(DomainValidationError, match='cannot inspect Artifact documents'):
        await runtime._execute_phased(request, 0.0)

    runtime._fail.assert_awaited_once()
    runtime._execute_llm.assert_not_awaited()
