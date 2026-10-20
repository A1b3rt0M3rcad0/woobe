import subprocess
import sys

import pytest


@pytest.mark.parametrize('first', ['identity', 'artifacts'])
def test_identity_and_artifact_workspace_mappers_coexist_in_both_import_orders(first):
    second = 'artifacts' if first == 'identity' else 'identity'
    script = f'''
import importlib
importlib.import_module('modules.{first}.infra.database.models')
importlib.import_module('modules.{second}.infra.database.models')
from modules.identity.infra.database.models import WorkspaceModel as IdentityWorkspace
from modules.artifacts.infra.database.models import WorkspaceModel as ArtifactWorkspace
identity = IdentityWorkspace(name='Existing identity', slug='existing')
artifact = ArtifactWorkspace(id='artifact-workspace', name='Independent files')
assert IdentityWorkspace.members.property.mapper.relationships['workspace'].mapper.class_ is IdentityWorkspace
assert identity.__table__.schema == 'identity'
assert artifact.__table__.schema == 'artifacts'
assert IdentityWorkspace is not ArtifactWorkspace
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
