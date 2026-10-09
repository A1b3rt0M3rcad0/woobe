"""Run identity is derived from accepted frozen content, never current Production."""
from copy import deepcopy
from uuid import uuid4
from modules.agent.application.interfaces.runtime_identity import accepted_agent_identity, output_runtime_identity
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context


def test_identity_pins_accepted_release_and_scoped_digest_without_author_or_secrets():
    snapshot={'release':{'id':str(uuid4()),'version':'1.2.0'},'agent':{'system_prompt':'private-author-text'},
        'continuity_policy':'pinned_first_accepted_run','asac':{'revision_id':'rv_'+str(uuid4()),'runtime_digest':'sha256:'+'a'*64}}
    original=deepcopy(snapshot)
    args=dict(project_id=uuid4(),agent_id=uuid4(),session_id=uuid4(),environment='production',
              snapshot=snapshot,continuity_policy=snapshot['continuity_policy'])
    first=accepted_agent_identity(**args)
    assert first['snapshot_id']==snapshot['release']['id']
    assert first['admission_digest_scope']=='agent-run-admission@1'
    assert first['asac']['runtime_digest']=='sha256:'+'a'*64
    assert 'private-author-text' not in str(first)
    assert snapshot==original
    first['asac']['revision_id']='changed-projection'
    assert snapshot==original
    later={**snapshot,'release':{'id':str(uuid4()),'version':'1.3.0'}}
    assert accepted_agent_identity(**{**args,'snapshot':later})['admission_digest']!=first['admission_digest']
    assert accepted_agent_identity(**args)['snapshot_id']==original['release']['id']


def test_output_identity_is_scoped_to_exact_run_and_copied():
    context=new_execution_context();context.run_id=uuid4();context.runtime_identity={'snapshot_id':'accepted'}
    token=current_execution.set(context)
    try:
        assert output_runtime_identity(uuid4()) is None
        result=output_runtime_identity(context.run_id);result['snapshot_id']='changed'
        assert context.runtime_identity['snapshot_id']=='accepted'
    finally:
        current_execution.reset(token)
    assert output_runtime_identity(context.run_id) is None


def test_provider_rotation_changes_admitted_binding_identity_without_exposing_values():
    snapshot={"release":{"id":str(uuid4())}, "binding_revisions":{"primary":{"credential_id":str(uuid4()),"revision":"2026-10-09T00:00:00Z"}}}
    args=dict(project_id=uuid4(),agent_id=uuid4(),session_id=uuid4(),environment="production",continuity_policy="follow_selection_between_runs")
    original=accepted_agent_identity(**args,snapshot=snapshot)
    rotated=deepcopy(snapshot);rotated["binding_revisions"]["primary"]["revision"]="2026-10-09T00:01:00Z"
    changed=accepted_agent_identity(**args,snapshot=rotated)
    assert changed["snapshot_id"]==original["snapshot_id"]
    assert changed["runtime_binding_digest"]!=original["runtime_binding_digest"]
    assert changed["admission_digest"]!=original["admission_digest"]
