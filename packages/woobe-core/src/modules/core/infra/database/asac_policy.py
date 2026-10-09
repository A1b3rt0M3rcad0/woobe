"""Project policy locks protect plan/apply against policy and actor changes."""
from uuid import UUID, uuid4
from sqlalchemy import select, text
from modules.core.infra.database.models import ProjectModel, OutboxEventModel
from modules.core.infra.database.asac_policy_models import ProjectLifecyclePolicyModel, ProjectLifecyclePolicyOperationModel
from shared.contracts.asac import asac_digest
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from shared.infra.admin_idempotency import principal_identity
from shared.infra.asac_lease_store import database_now, _utc
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer

async def _authorize(session, principal, project_id, permission):
    authority = TenantAuthorizer(session)
    paths = {"project_id":str(project_id)}
    if isinstance(principal, ControlPlanePrincipal):
        await authority.require_active_control(principal)
        await authority.authorize_control_key(api_key_id=principal.api_key_id,
            workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
            required_permission=permission, path_params=paths, query_params={}, body={})
    elif isinstance(principal, AuthenticatedPrincipal):
        await authority.require_active_human(principal)
        workspace_id = await authority._project_workspace_id(project_id)
        await authority.require_human_permission(user_id=principal.user_id,workspace_id=workspace_id,
            project_id=project_id,permission=permission,path_context=paths)
    else:
        raise AuthorizationError("Administrative authentication is required")

def policy_output(project_id, row):
    return {"project_id":str(project_id),"schema_version":"1.0",
        "generation":row.generation if row else 0,"managed":row.managed if row else False,
        "production_actors":sorted(row.production_actors) if row else []}

class ProjectLifecyclePolicyReader:
    async def inspect(self,session,*,project_id,resource_id=None,principal,environment):
        # Lock the Project even when no policy exists, fencing first insertion.
        project=await session.scalar(select(ProjectModel).where(ProjectModel.id==project_id)
            .with_for_update(read=True))
        if project is None:
            raise NotFoundError("Project is unavailable")
        row=await session.scalar(select(ProjectLifecyclePolicyModel).where(
            ProjectLifecyclePolicyModel.project_id==project_id).with_for_update(read=True))
        result=policy_output(project_id,row)
        if result['managed'] and environment=='production' and result['production_actors']:
            if principal_identity(principal) not in result['production_actors']:
                raise AuthorizationError("ASAC_PROJECT_PRODUCTION_ACTOR_REQUIRED")
        return result

class ProjectLifecyclePolicyService:
    def __init__(self,sessions):
        self.sessions=sessions

    async def get(self,*,project_id,principal):
        async with self.sessions() as session:
            await _authorize(session,principal,project_id,'project:read')
            project=await session.get(ProjectModel,project_id)
            if project is None: raise NotFoundError("Project is unavailable")
            row=await session.scalar(select(ProjectLifecyclePolicyModel).where(ProjectLifecyclePolicyModel.project_id==project_id))
            return policy_output(project_id,row)

    async def change(self,*,project_id,principal,request):
        # Policy authority is separate from permission to edit a resource.
        async with self.sessions.begin() as session:
            await _authorize(session,principal,project_id,'project:access:write')
            project=await session.get(ProjectModel,project_id,with_for_update=True)
            if project is None: raise NotFoundError("Project is unavailable")
            actor=principal_identity(principal)
            digest=asac_digest('project-lifecycle-policy-request',{'project_id':str(project_id),**request.model_dump(mode='json')})
            previous=await session.scalar(select(ProjectLifecyclePolicyOperationModel).where(
                ProjectLifecyclePolicyOperationModel.operation_id==request.operation_id))
            if previous is not None:
                if previous.project_id!=project_id or previous.actor!=actor or previous.request_digest!=digest:
                    raise ConflictError("ASAC_OPERATION_ID_CONFLICT")
                return previous.result
            actors=sorted(set(request.production_actors))
            if len(actors)!=len(request.production_actors) or len(request.reason.strip())<3:
                raise ValidationError("Lifecycle policy requires unique actor identities and an audit reason")
            for identity in actors:
                try: UUID(identity.split(':',1)[1])
                except ValueError: raise ValidationError("Lifecycle policy actor identity is invalid") from None
            row=await session.scalar(select(ProjectLifecyclePolicyModel).where(ProjectLifecyclePolicyModel.project_id==project_id).with_for_update())
            before=policy_output(project_id,row)
            if request.expected_generation!=before['generation']:
                raise ConflictError("ASAC_PROJECT_POLICY_STALE")
            if row is None:
                row=ProjectLifecyclePolicyModel(project_id=project_id,generation=1,managed=request.managed,production_actors=actors)
                session.add(row)
            else:
                row.generation+=1;row.managed=request.managed;row.production_actors=actors
            if session.bind.dialect.name=='postgresql':
                await session.execute(text("SELECT set_config('woobe.asac_policy_operation',:operation,true)"),{'operation':str(request.operation_id)})
            await session.flush()
            outbox_id=uuid4()
            now=await database_now(session)
            result={'schema_version':'1.0','project_id':str(project_id),'operation_id':str(request.operation_id),
                'actor':actor,'reason':request.reason,'before':before,'policy':policy_output(project_id,row),
                'outbox_id':str(outbox_id),'created_at':_utc(now).isoformat(),'clock_authority':'database','write_outcome':'committed','complete':True}
            result['receipt_digest']=asac_digest('project-lifecycle-policy-receipt',result)
            session.add(ProjectLifecyclePolicyOperationModel(project_id=project_id,operation_id=request.operation_id,
                actor=actor,request_digest=digest,reason=request.reason,result=result,outbox_id=outbox_id))
            session.add(OutboxEventModel(id=outbox_id,aggregate_type='project',aggregate_id=project_id,
                event_type='project.asac.lifecycle-policy.changed',event_version=1,
                routing_key='project.asac.lifecycle-policy.changed',payload=result,
                metadata_={'schema_version':'1.0'},idempotency_key='asac-policy:'+str(request.operation_id),
                correlation_id=request.operation_id,causation_id=outbox_id,status='pending',attempts=0))
            return result


    async def operation(self,*,project_id,principal,operation_id):
        async with self.sessions() as session:
            await _authorize(session,principal,project_id,'project:read')
            row=await session.scalar(select(ProjectLifecyclePolicyOperationModel).where(
                ProjectLifecyclePolicyOperationModel.project_id==project_id,
                ProjectLifecyclePolicyOperationModel.operation_id==operation_id))
            if row is None: raise NotFoundError("ASAC_OPERATION_UNAVAILABLE")
            return row.result
