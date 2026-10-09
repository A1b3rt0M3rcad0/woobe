"""Project policy authority has a fixed CAS base and canonical stable actors."""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from modules.core.application.dtos.asac_policy import ChangeProjectLifecyclePolicy
from modules.core.infra.database.asac_policy import policy_output


def request(**changes):
    return {'operation_id':str(uuid4()),'expected_generation':0,'managed':True,
        'production_actors':[],'reason':'Enable qualified lifecycle',**changes}

@pytest.mark.parametrize('changes',[
    {'expected_generation':-1},{'expected_generation':True},{'managed':'true'},
    {'reason':'  '},{'reason':' a '},{'production_actors':['control:not-a-uuid']},
    {'production_actors':['control:'+'-'*36]}, {'force':True},
])
def test_policy_cannot_omit_or_weaken_authority_inputs(changes):
    with pytest.raises(ValidationError):
        ChangeProjectLifecyclePolicy.model_validate(request(**changes))


def test_policy_canonicalizes_stable_actor_uuid_and_audit_reason():
    identifier=uuid4()
    change=ChangeProjectLifecyclePolicy.model_validate(request(
        production_actors=['control:'+str(identifier).upper()],reason='  Reviewed lifecycle gate  '))
    assert change.production_actors==['control:'+str(identifier)]
    assert change.reason=='Reviewed lifecycle gate'
    with pytest.raises(ValidationError):
        ChangeProjectLifecyclePolicy.model_validate(request(production_actors=[
            'control:'+str(identifier),'control:'+str(identifier).upper()]))


def test_absent_policy_remains_explicit_legacy_generation_zero():
    project=uuid4()
    assert policy_output(project,None)=={'project_id':str(project),'schema_version':'1.0',
        'generation':0,'managed':False,'production_actors':[]}
