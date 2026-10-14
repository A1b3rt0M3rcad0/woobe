from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest
from shared.contracts.errors import AuthorizationError, NotFoundError
from modules.core.infra.services.configuration_summary import configuration_summary


def dependency(*, required=True, material='missing', code='CONFIG_VALUE_MISSING'):
    return dict(
        key='CONNECTION',
        consumer_kind='provider_credential',
        consumer_id='provider',
        field_path='/authentication/fields/api_key',
        required=required,
        material=material,
        code=code,
    )


def setup(*, complete=True):
    targets = [dict(kind='agent', id=uuid4(), selected=True), dict(kind='network', id=uuid4(), selected=True)]
    return dict(project_id=uuid4(),environment='draft',inventory=AsyncMock(return_value=dict(targets=targets,complete=complete)),
        reader=AsyncMock(return_value=dict(dependencies=[object()],unresolved=[])),
        inspect_many=AsyncMock(side_effect=lambda **kwargs: [(dict(state='blocked',dependencies=[dependency()]),[]) for _ in kwargs['groups']]),authorize=AsyncMock())


@pytest.mark.asyncio
async def test_summary_deduplicates_shared_connections_but_counts_both_affected_targets():
    args=setup()
    result=await configuration_summary(object(),**args)
    assert result['state']=='blocked' and result['complete']
    assert (result['missing_key_count'],result['affected_consumer_count'],result['affected_target_count'])==(1,1,2)
    assert args['authorize'].await_count==2
    args['inspect_many'].assert_awaited_once()
    assert len(args['inspect_many'].await_args.kwargs['groups']) == 2
    assert set(result).isdisjoint({'dependencies','values','targets','unresolved'})


@pytest.mark.asyncio
async def test_summary_authorizes_whole_observation_before_reading_connections():
    args=setup(); args['authorize'].side_effect=[None,AuthorizationError('denied')]
    with pytest.raises(AuthorizationError):
        await configuration_summary(object(),**args)
    args['reader'].assert_not_awaited(); args['inspect_many'].assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_does_not_disclose_unreadable_lookahead_through_has_next():
    args = setup(complete=False)
    args['inventory'].return_value['authorization_targets'] = [
        *args['inventory'].return_value['targets'], dict(kind='agent', id=uuid4(), selected=False)]
    args['authorize'].side_effect = [None, None, AuthorizationError('denied')]
    with pytest.raises(AuthorizationError):
        await configuration_summary(object(), **args)
    args['reader'].assert_not_awaited()
    args['inspect_many'].assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_does_not_call_unselected_environment_targets():
    args=setup(); args['inventory'].return_value['targets'][0]['selected']=False
    result=await configuration_summary(object(),**args)
    assert result['unselected_target_count']==1 and result['affected_target_count']==1
    args['reader'].assert_awaited_once()
    assert args['reader'].call_args.kwargs['environment']=='draft'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['truncated','missing_snapshot','unresolved'])
async def test_incomplete_observation_is_never_ready(failure):
    args=setup(complete=failure!='truncated')
    args['inspect_many'].side_effect=lambda **kwargs: [(dict(state='ready',dependencies=[]),[]) for _ in kwargs['groups']]
    if failure=='missing_snapshot': args['reader'].side_effect=NotFoundError('missing')
    if failure=='unresolved': args['reader'].return_value['unresolved']=[dict(code='LEGACY_REVIEW_REQUIRED')]
    result=await configuration_summary(object(),**args)
    assert result['state']=='unknown' and not result['complete']


@pytest.mark.asyncio
async def test_optional_dependency_cannot_overwrite_required_shared_dependency():
    args=setup()
    args['inspect_many'].side_effect=None
    args['inspect_many'].return_value=[(dict(state='blocked',dependencies=[dependency()]),[]),
        (dict(state='ready_with_notices',dependencies=[dependency(required=False)]),[])]
    result=await configuration_summary(object(),**args)
    assert result['state']=='blocked' and result['required_key_count']==1


@pytest.mark.asyncio
async def test_last_page_is_not_mistaken_for_complete_project_evidence():
    args = setup()
    args['inspect_many'].side_effect = lambda **kwargs: [(dict(state='ready', dependencies=[]), []) for _ in kwargs['groups']]
    result = await configuration_summary(object(), **args, limit=1, cursor='previous-page')
    assert result['scope'] == 'current_selections_page'
    assert result['state'] == 'unknown' and not result['complete']
    assert result['page_state'] == 'ready' and result['page_complete']
    assert not result['has_next'] and result['next_cursor'] is None
    args['inventory'].assert_awaited_once_with(ANY,
        project_id=args['project_id'], environment='draft', limit=1, cursor='previous-page')


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', [0, 201, True, '2'])
async def test_invalid_inventory_bound_rejected_before_any_query(limit):
    from shared.contracts.project_configuration import ConfigurationError
    args = setup()
    with pytest.raises(ConfigurationError):
        await configuration_summary(object(), **args, limit=limit)
    args['inventory'].assert_not_awaited()
