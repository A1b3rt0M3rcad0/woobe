"""Unified delivery acceptance against real owners, leases and provider workers.

The fixture uses disposable credentials/resources. It qualifies orchestration,
not customer Production, cross-machine load or external-provider reliability.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import yaml

from tests.integration.cli.retest_operational import (
    assert_deployment_count,
    lose_committed_response,
)


async def exercise_unified_deployment(cli, kind, resource_id, previous):
    lower = kind.lower()
    base = f"/projects/{cli.project_id}/{lower}s/{resource_id}/asac"
    release = previous['publication']['release_id']
    clean = cli.directory / ('unified-native-' + lower)
    clean.mkdir()
    assert not (clean / '.woobe-config').exists()
    before = (await cli.run(lower, resource_id, 'deploy', 'inspect', cwd=clean))['data']
    preflight = (await cli.run(lower, resource_id, 'deploy', '--from', 'release',
                               '--release', release, '--notes', 'Read only preflight',
                               '--plan-only', cwd=clean))['data']
    assert not preflight['executed'] and preflight['server_qualification'] == 'not_evaluated'
    assert (await cli.run(lower, resource_id, 'deploy', 'inspect', cwd=clean))['data']['environment_generation'] == before['environment_generation']

    registry = cli.directory / ('unified-author-' + lower)
    registry.mkdir()
    await cli.run('init', '--root', '.woobe', cwd=registry)
    await cli.run(lower, resource_id, 'pull', '--alias', 'delivery', '--env', 'production', cwd=registry)
    config = yaml.safe_load((registry / '.woobe-config').read_text())
    credentials = {item['credential_id'] for item in previous['binding_spec']['credentials'].values()}
    assert len(credentials) == 1, 'This disposable fixture uses one Provider credential'
    for provider in (item for item in config['resources'] if item['kind'] == 'Provider'):
        await cli.run('resources', 'bind', 'provider', '@' + provider['alias'], next(iter(credentials)), cwd=registry)
    initial_suite=registry/'initial-suite.yaml'
    initial_suite.write_text(yaml.safe_dump({'schema_version':'1.0','suite_id':'preflight',
                                           'suite_version':'1','dataset_version':'1',
                                           'cases':[{'id':'preflight','message':'Hello'}]}))
    drafts_before=await cli.data('request','GET',base+'/drafts')
    await cli.run(lower,'@delivery','deploy','--from','local','--suite',str(initial_suite),
                  '--notes','Reject unaccepted registry','--plan-only',cwd=registry,expected=9)
    drafts_after=await cli.data('request','GET',base+'/drafts')
    assert {item['draft_id'] for item in drafts_before['drafts']}=={item['draft_id'] for item in drafts_after['drafts']}
    # Captured identities are not an accepted registry. Establish closure
    # explicitly; unified delivery must not silently import/push to repair it.
    await cli.run(lower, '@delivery', 'push', cwd=registry)
    resource = next(item for item in config['resources'] if item['kind'] == kind and item['alias'] == 'delivery')
    descriptor = registry / config['root'] / resource['path']
    if descriptor.suffix not in {'.yaml', '.yml', '.json'}:
        descriptor /= lower + '.yaml'
    document = yaml.safe_load(descriptor.read_text())
    if kind == 'Agent':
        if document['spec'].get('behavior') is not None:
            document['spec']['behavior']['objective'] += ' Unified immutable delivery.'
        else:
            document['spec']['legacy_system_prompt'] += ' Unified immutable delivery.'
    else:
        document['spec']['settings']['max_invocations'] = 59
    descriptor.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    suite = registry / 'deploy-evaluation.yaml'
    suite.write_text(yaml.safe_dump({'schema_version':'1.0', 'suite_id':'unified-deploy',
                                   'suite_version':'1', 'dataset_version':'1',
                                   'cases':[{'id':'delivery', 'message':'Hello unified delivery'}]}))
    delivered = (await cli.run(lower, '@delivery', 'deploy', '--from', 'local',
                              '--suite', str(suite), '--notes', 'Deliver accepted author closure',
                              cwd=registry))['data']
    assert delivered['status'] == 'completed' and delivered['observed_current_matches']
    assert delivered['release_id'] != release
    assert delivered['generation_after'] == before['environment_generation'] + 1
    assert delivered['publication_id'] and delivered['evaluation_id'] and delivered['candidate_id']
    assert_deploy = delivered['operations']['apply:production']['operation_id']
    await assert_deployment_count(kind, assert_deploy)
    resumed = (await cli.run(lower, resource_id, 'deploy', 'resume', '--intent', delivered['intent_id'], cwd=clean))['data']
    assert resumed == delivered
    await assert_deployment_count(kind, assert_deploy)
    native = (await cli.run(lower, resource_id, 'deploy', '--from', 'release',
                           '--release', delivered['release_id'], '--notes', 'Observe selected qualified release', cwd=clean))['data']
    assert native['status'] == 'already_selected' and native['observed_current_matches']
    assert native['generation_after'] == delivered['generation_after']

    staged = (await cli.run(lower, resource_id, 'deploy', '--from', 'release',
                           '--release', delivered['release_id'], '--env', 'staging',
                           '--notes', 'Select same qualified Release in Staging', cwd=clean))['data']
    assert staged['release_id'] == delivered['release_id']
    rolled = (await cli.run(lower, resource_id, 'deploy', '--from', 'release', '--release', release,
                           '--action', 'rollback', '--notes', 'Explicit qualified rollback', cwd=clean))['data']
    assert rolled['release_id'] == release and rolled['generation_after'] > delivered['generation_after']
    promoted = (await cli.run(lower, resource_id, 'deploy', '--from', 'staging',
                             '--notes', 'Promote exact observed Staging', cwd=clean))['data']
    assert promoted['release_id'] == staged['release_id'] and promoted['status'] == 'completed'

    _, runtime_key = await cli.issue('project', 'runtime-key', 'create', body={
        'project_id':cli.project_id, 'name':'Unified Production proof', 'target_type':lower,
        'target_id':resource_id, 'environment':'production', 'interfaces':['http', 'stream'],
        'expires_at':(datetime.now(UTC)+timedelta(hours=1)).isoformat()})
    result = await cli.run('runtime', 'target', 'run', 'unified-qualified', '--target-kind', lower,
                           body={'input':'Hello unified Release'}, runtime_key=runtime_key)
    identity = result['data']['data']['runtime_identity']
    assert identity['snapshot_id'] == promoted['release_id']
    assert identity['asac']['publication_id'] == delivered['publication_id']
    # A synchronous completion must reattach as one terminal frame, not a
    # stale Redis running projection followed by a client deadline.
    run_data = result['data']['data']
    run_id = run_data.get('run_id') or run_data.get('execution_id')
    assert run_id
    observed = await cli.run('runtime', 'target', 'observe', 'unified-qualified', run_id,
                             '--target-kind', lower, '--output', 'jsonl', '--timeout', '5s',
                             runtime_key=runtime_key)
    assert observed['payload']['status'] == 'completed'
    assert observed['payload']['output'] == run_data['answer']
    assert observed['payload']['sequence'] is None

    # Keep API namespace stable during response loss and reconciliation. The
    # checkpoint and deterministic operation must survive an independent process.
    async with lose_committed_response(cli.origin, base + '/deployments') as (origin, accepted):
        fault = type(cli)(cli.binary, origin, cli.workspace_id, cli.credential, clean)
        fault.project_id, fault.secret_values = cli.project_id, cli.secret_values
        intent = str(uuid4())
        lost = await fault.run(lower, resource_id, 'deploy', '--from', 'release', '--release', release,
                               '--action', 'rollback', '--notes', 'Recover original committed apply',
                               '--intent', intent, cwd=clean, expected=(8, 9))
        assert accepted and not lost['success']
        recovered = (await fault.run(lower, resource_id, 'deploy', 'resume', '--intent', intent, cwd=clean))['data']
        assert recovered['deployment_id'] == accepted[0]['deployment_id']
        assert recovered['release_id'] == release and recovered['observed_current_matches']
        await assert_deployment_count(kind, accepted[0]['operation_id'])
    # Documentary status does not mutate remote environments.
    assert not (clean / '.woobe-config').exists()
    reads = ['project:read','agent:read','network:read','provider:read','model:read',
             'tool:read','skill:read','knowledge:read','secret:read','project:environment:read']
    deployer, deploy_key = await cli.issue('workspace', 'control-key', 'create', body={
        'name':'Unified deploy-only ' + kind, 'permissions':[], 'on_project_create_permissions':[],
        'expires_at':(datetime.now(UTC)+timedelta(hours=1)).isoformat(),
        'project_grants':[{'project_id':cli.project_id,'permissions':reads+[lower+':production'],
                           'conditions':{'environments':['staging','production'],'target_types':[lower],'target_ids':[resource_id]}}]})
    # Authorization preflight consumes the same verified target and environment.
    access = await cli.data('request','POST','/identity/access/check',body={
        'method':'GET','path':base+'/operations/'+str(uuid4()),
        'query':{'environment':'production'},'body':{}},key=deploy_key)
    assert access['allowed']
    # Production grants do not bypass the managed actor restriction.
    await cli.run(lower, resource_id, 'deploy', '--from', 'release', '--release', release,
                  '--notes', 'Denied unlisted actor', cwd=clean, key=deploy_key, expected=4)
    policy = await cli.data('project', 'lifecycle', 'show')
    await cli.data('project', 'lifecycle', 'update', body={
        'operation_id':str(uuid4()),'expected_generation':policy['generation'],'managed':True,
        'production_actors':policy['production_actors']+['control:'+deployer['credential_id']],
        'reason':'Allow explicit deploy-only delivery actor'})
    controlled = (await cli.run(lower, resource_id, 'deploy', '--from', 'release', '--release', delivered['release_id'],
                                '--notes', 'Qualified dedicated deploy-only delivery', cwd=clean, key=deploy_key))['data']
    assert controlled['actor'] == 'control:' + deployer['credential_id']
    assert controlled['release_id'] == delivered['release_id'] and controlled['observed_current_matches']
    read_stage = (await cli.run(lower,resource_id,'deploy','--from','staging',
                               '--notes','Promote with Production-only grant',cwd=clean,key=deploy_key))['data']
    assert read_stage['release_id']==delivered['release_id']
    await cli.run(lower,resource_id,'deploy','--from','release','--release',release,'--env','staging',
                  '--notes','Deny Staging write without version grant',cwd=clean,key=deploy_key,expected=4)
    # Raw owner endpoints must also reject attempts outside the deployer's role.
    await cli.run('request','POST',base+'/drafts',body={
        'operation_id':str(uuid4()),'resource_uid':resource['uid'],'name':'forbidden',
        'source_export_id':str(uuid4())},key=deploy_key,expected=4)
    await cli.run('request','POST',base+'/publications',body={
        'operation_id':str(uuid4()),'candidate_id':delivered['candidate_id'],
        'evaluation_id':delivered['evaluation_id'],'reason':'Forbidden publication'},key=deploy_key,expected=4)
    _, staging_key = await cli.issue('project','runtime-key','create',body={
        'project_id':cli.project_id,'name':'Separate unified Staging smoke', 'target_type':lower,
        'target_id':resource_id,'environment':'staging','interfaces':['http'],
        'expires_at':(datetime.now(UTC)+timedelta(hours=1)).isoformat()})
    smoke = registry / 'staging-smoke.yaml'
    smoke_body = {'schema_version':'1.0','target_alias':'unified-smoke',
                  'request':{'input':'Hello unified Release'},
                  'expected_output':result['data']['data']['answer']}
    smoke.write_text(yaml.safe_dump(smoke_body))
    def change_author(marker, invocations):
        document = yaml.safe_load(descriptor.read_text())
        if kind == 'Agent':
            if document['spec'].get('behavior') is not None:
                document['spec']['behavior']['objective'] += marker
            else:
                document['spec']['legacy_system_prompt'] += marker
        else:
            document['spec']['settings']['max_invocations'] = invocations
        descriptor.write_text(yaml.safe_dump(document,sort_keys=False,allow_unicode=True))
    change_author(' Verify Staging before Production.', 58)
    via = (await cli.run(lower,'@delivery','deploy','--from','local','--suite',str(suite),
                        '--via-staging','--smoke',str(smoke),'--notes','Verify exact Staging runtime',
                        cwd=registry,runtime_key=staging_key))['data']
    assert via['status']=='completed' and via['local']['smoke_status']=='passed'
    staged_now=(await cli.run(lower,resource_id,'deploy','inspect','--env','staging'))['data']
    assert staged_now['snapshot_id']==via['release_id']
    change_author(' Reject failing Staging assertion.', 57)
    smoke_body['expected_output']='An intentionally impossible smoke assertion'
    smoke.write_text(yaml.safe_dump(smoke_body))
    failed = await cli.run(lower,'@delivery','deploy','--from','local','--suite',str(suite),
                          '--via-staging','--smoke',str(smoke),'--notes','Reject negative smoke',
                          cwd=registry,runtime_key=staging_key,expected=11)
    assert failed['data']['local']['smoke_status']=='failed'
    unchanged=(await cli.run(lower,resource_id,'deploy','inspect'))['data']
    assert unchanged['snapshot_id']==via['release_id'] and unchanged['environment_generation']==via['generation_after']
    from sqlalchemy import text
    from shared.infra.config import Settings
    from shared.infra.database.session import create_engine, create_session_factory
    from uuid import UUID
    engine=create_engine(Settings())
    try:
        async def publication_count():
            async with create_session_factory(engine)() as session:
                return await session.scalar(text(f'SELECT count(*) FROM {lower}.asac_publications WHERE resource_id=:target'),{'target':UUID(resource_id)})
        count=await publication_count()
        change_author(' Reject a failed Candidate evaluation.', 56)
        bad_suite=yaml.safe_load(suite.read_text())
        bad_suite['cases'][0]['expected_output']={'answer':'An intentionally impossible evaluation assertion'}
        suite.write_text(yaml.safe_dump(bad_suite))
        failed_evaluation=await cli.run(lower,'@delivery','deploy','--from','local','--suite',str(suite),
                                       '--notes','Reject negative evaluation',cwd=registry,expected=6)
        assert 'publication' not in failed_evaluation['data']['operations']
        assert await publication_count()==count
        await cli.run(lower,'@delivery','deploy','resume','--intent',failed_evaluation['data']['intent_id'],
                      cwd=registry,expected=6)
        assert await publication_count()==count
        still=(await cli.run(lower,resource_id,'deploy','inspect'))['data']
        assert still['snapshot_id']==via['release_id'] and still['environment_generation']==via['generation_after']
    finally:
        await engine.dispose()
    cli.evidence.append({'unified_deploy':kind, 'local_release':delivered['release_id'],
                         'runtime_snapshot':identity['snapshot_id'], 'response_loss_recovered':True})
