"""Public identity of the accepted Run, never a lookup of current Production."""
from copy import deepcopy
from shared.contracts.asac import asac_digest


def accepted_agent_identity(*, project_id, agent_id, session_id, environment, snapshot, continuity_policy):
    release = snapshot.get('release') or {}
    identity = {
        'schema_version':'1.0','target_type':'agent','project_id':str(project_id),
        'target_id':str(agent_id),'session_id':str(session_id) if session_id else None,'environment':environment,
        'snapshot_id':release.get('id'),'snapshot_version':release.get('version'),
        'admission_digest':asac_digest('agent-run-admission',snapshot),
        'admission_digest_scope':'agent-run-admission@1',
        'continuity_policy':continuity_policy,
        'external_dependencies':'versioned_references_not_reproducible_responses',
    }
    versions = snapshot.get('binding_revisions')
    if isinstance(versions, dict):
        identity['runtime_binding_digest'] = asac_digest('agent-run-binding-revisions', versions)
        identity['runtime_binding_digest_scope'] = 'agent-run-binding-revisions@1'
    provenance = snapshot.get('asac')
    if isinstance(provenance, dict):
        identity['asac'] = deepcopy(provenance)
    return identity


def output_runtime_identity(run_id):
    from modules.agent.application.interfaces.execution_context import current_execution
    context=current_execution.get()
    if context is None or context.run_id!=run_id:
        return None
    return deepcopy(context.runtime_identity)
