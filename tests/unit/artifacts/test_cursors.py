import pytest

from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.domain.models import ArtifactError


def test_cursor_is_signed_and_bound_to_principal_query_and_purpose():
    codec = CursorCodec(b'f' * 32)
    fingerprint = codec.fingerprint({'project': 'p', 'principal': 'user-a', 'namespace': 'n'})
    data = CursorEnvelope(scope_fingerprint=fingerprint, last_id='workspace-1',
                          catalog_version=0, purpose='workspaces')
    token = codec.encode(data)
    assert codec.decode(token, fingerprint=fingerprint, purpose='workspaces') == data
    tampered = ('A' if token[0] != 'A' else 'B') + token[1:]
    for candidate, context, purpose in [
        (tampered, fingerprint, 'workspaces'),
        (token, codec.fingerprint({'project': 'p', 'principal': 'user-b', 'namespace': 'n'}), 'workspaces'),
        (token, fingerprint, 'artifacts'),
        ('invalid', fingerprint, 'workspaces'),
        ('x' * 4097, fingerprint, 'workspaces'),
    ]:
        with pytest.raises(ArtifactError) as failure:
            codec.decode(candidate, fingerprint=context, purpose=purpose)
        assert failure.value.code == 'ARTIFACT_INVALID_CURSOR'


def test_cursor_context_order_is_not_significant_and_weak_keys_are_rejected():
    assert CursorCodec.fingerprint({'a': 1, 'b': 2}) == CursorCodec.fingerprint({'b': 2, 'a': 1})
    with pytest.raises(ValueError):
        CursorCodec(b'short')
