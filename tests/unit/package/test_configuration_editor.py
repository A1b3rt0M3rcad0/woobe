from copy import deepcopy
from uuid import uuid4

import pytest

from modules.package.application.validation import validate_document
from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import snapshot_directory, receive_archive
from modules.package.infra.editor_artifacts import editor_binding_document, editor_files, edited_archive
from tests.unit.package.test_configuration_package_v2 import package


def test_remote_configuration_editor_preserves_reference_identity_and_schema(tmp_path):
    documents = package(tmp_path)
    manifest = documents['woobe.yaml']
    identifier = str(uuid4())
    bindings = editor_binding_document(manifest, {'primary': identifier})
    validate_document(bindings)
    assert bindings['schema_version'] == '2.0'
    assert bindings['spec']['credentials'] == {'primary': {'credential_id': identifier}}
    assert bindings['spec']['project_environment'] == {'PRIMARY_KEY': {'existing_key': 'PRIMARY_KEY'}}
    assert 'secrets' not in bindings['spec']
    bundle = snapshot_directory(tmp_path)
    view = editor_files(bundle)
    assert view['requirements']['configuration']['PRIMARY_KEY']['kind'] == 'secret'
    assert next(row for row in view['files'] if row['path'] == 'woobe.yaml')['editable'] is False
    agent = next(row for row in view['files'] if row['path'] == 'agent.yaml')
    with edited_archive(bundle, [{'path': 'agent.yaml', 'content': agent['content'].replace('Help', 'Updated objective')}]) as archive:
        with receive_archive(archive, locked=True) as updated:
            assert updated.graph.manifest == manifest
            assert updated.graph.components['agent']['spec']['legacy_system_prompt'] == 'Updated objective'


def test_remote_web_editor_never_creates_missing_providers_or_drops_external_knowledge(tmp_path):
    manifest = package(tmp_path)['woobe.yaml']
    with pytest.raises(PackageError) as error:
        editor_binding_document(manifest, {})
    assert error.value.code == 'ASAC_EDITOR_BINDING_UNAVAILABLE'
    manifest = deepcopy(manifest)
    manifest['spec']['requires'] = {'knowledge': [{'ref':'retained-index'}]}
    with pytest.raises(PackageError) as error:
        editor_binding_document(manifest, {'primary':str(uuid4())})
    assert error.value.code == 'ASAC_EDITOR_BINDING_UNAVAILABLE'
