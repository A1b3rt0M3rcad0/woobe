import json
from types import SimpleNamespace

import pytest

from modules.artifacts.application.contracts.document_models import DocumentModelFragment, DocumentModelUsage
from modules.artifacts.application.services.document_models import model_input, validate_model_output
from modules.artifacts.domain.models import ArtifactError


def request(operation='summarize'):
    return SimpleNamespace(operation=operation, max_output_tokens=64, timeout_seconds=30,
        fragments=tuple(DocumentModelFragment(id=name, text='Untrusted 😀 '+name,
            source={'artifact_id': 'artifact', 'revision_id': 'revision', 'source_sha256': 'a'*64})
            for name in ('one', 'two')))


def test_payload_is_deterministic_and_explicitly_untrusted():
    first = request()
    encoded, fingerprint = model_input(first)
    assert (encoded, fingerprint) == model_input(request())
    assert len(fingerprint) == 64
    assert all(item['trust'] == 'untrusted_document' for item in json.loads(encoded)['fragments'])
    output = validate_model_output(json.dumps({'summaries': [{'text': 'Inferred', 'fragment_ids': ['two']}]}), first)
    assert output.summaries[0].fragment_ids == ('two',)


@pytest.mark.parametrize('payload', [
    '{}', '{"summaries":[],"summaries":[]}', '{"surprise":"secret"}',
    '{"summaries":[{"text":"  ","fragment_ids":["one"]}]}',
    '{"summaries":[{"text":"x","fragment_ids":["foreign"]}]}',
    '{"summaries":[{"text":"x","fragment_ids":["one","one"]}]}',
    '{"summaries":[{"text":"\\ud800","fragment_ids":["one"]}]}',
    '{"summaries":NaN}', 'x'*65537,
])
def test_invalid_or_foreign_model_output_is_typed_and_never_reflected(payload):
    with pytest.raises(ArtifactError) as error:
        validate_model_output(payload, request())
    assert error.value.code == 'MODEL_OUTPUT_INVALID'
    assert str(error.value) == 'Model output violates its document-scoped schema'


def test_refinement_must_follow_supplied_source_order_and_cannot_replace_summary_contract():
    valid = {'sections': [{'title': 'Inferred', 'start_fragment_id': 'one', 'end_fragment_id': 'two'}]}
    assert validate_model_output(json.dumps(valid), request('refine_structure')).sections
    with pytest.raises(ArtifactError):
        validate_model_output(json.dumps(valid), request())
    valid['sections'][0]['start_fragment_id'] = 'two'
    valid['sections'][0]['end_fragment_id'] = 'one'
    with pytest.raises(ArtifactError):
        validate_model_output(json.dumps(valid), request('refine_structure'))


def test_budget_counts_utf8_payload_schema_and_controls_and_rejects_duplicate_sources():
    value = request()
    value.fragments = (value.fragments[0], value.fragments[0])
    with pytest.raises(ArtifactError):
        model_input(value)
    value = request()
    value.fragments = tuple(fragment.model_copy(update={'text': '😀'*8192}) for fragment in value.fragments)
    with pytest.raises(ArtifactError) as error:
        model_input(value)
    assert error.value.code == 'MODEL_BUDGET_EXCEEDED'


@pytest.mark.parametrize('values', [{'input_tokens': -1}, {'output_tokens': True}, {'cost_usd': float('nan')},
                                   {'cost_usd': -1}, {'cost_status': 'invented'}])
def test_unknown_usage_remains_unknown_and_invalid_usage_cannot_be_recorded(values):
    assert DocumentModelUsage().input_tokens is None
    with pytest.raises(ValueError):
        DocumentModelUsage(**values)
