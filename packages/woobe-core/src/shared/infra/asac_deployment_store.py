"""Exact owner selections, immutable plans/receipts and transactional outbox."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
from sqlalchemy import select, text
from shared.contracts.asac import asac_digest
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.admin_idempotency import principal_identity
from shared.infra.asac_lease_store import database_now, _utc
from shared.infra.asac_lease_errors import asac_lease_database_errors


def plan_output(row):
    data={'schema_version':'1.0','plan_id':str(row.id),'project_id':str(row.project_id),
        'resource_id':str(row.resource_id),'publication_id':str(row.publication_id),
        'release_id':str(row.release_id),'environment':row.environment,'expected_generation':row.expected_generation,
        'previous_release_id':str(row.previous_release_id) if row.previous_release_id else None,
        'previous_fingerprint':row.previous_fingerprint,'actor':row.actor,'operation_id':str(row.operation_id),
        'action':row.action,'reason':row.reason,'expires_at':_utc(row.expires_at).isoformat(),
        'created_at':_utc(row.created_at).isoformat(),'state':'planned','executed':False,
        'write_outcome':'committed','complete':True,**row.evidence}
    data['plan_digest']=asac_digest('deployment-plan',data)
    return data


def deployment_output(row):
    data={'schema_version':'1.0','deployment_id':str(row.id),'plan_id':str(row.plan_id),
        'project_id':str(row.project_id),'resource_id':str(row.resource_id),
        'publication_id':str(row.publication_id),'release_id':str(row.release_id),
        'previous_release_id':str(row.previous_release_id) if row.previous_release_id else None,
        'environment':row.environment,'generation_before':row.generation_before,'generation_after':row.generation_after,
        'actor':row.actor,'operation_id':str(row.operation_id),'action':row.action,'reason':row.reason,
        'selection_changed':row.selection_changed,'outbox_id':str(row.outbox_id),
        'created_at':_utc(row.created_at).isoformat(),'state':'committed','write_outcome':'committed',
        'complete':True,**row.evidence}
    data['receipt_digest']=asac_digest('deployment-receipt',data)
    return data


class ASaCDeploymentStore:
    def __init__(self,*,publications,plans,deployments,selections,selector,outbox,bindings,policy=None,maximum_plan_seconds=300):
        if not 1 <= maximum_plan_seconds <= 3600:
            raise ValueError('Deployment plan duration is invalid')
        self.publications,self.plans,self.deployments=publications,plans,deployments
        self.drafts=publications.drafts
        self.selections,self.selector,self.outbox,self.bindings=selections,selector,outbox,bindings
        self.policy,self.maximum_plan_seconds=policy,maximum_plan_seconds

    async def _authorize(self,session,args,environment,*,write=False):
        await self.drafts.owner.inspect(session,**args,kind=self.drafts.kind,environment=environment,lock=write,
            required_permission=self.drafts.kind.lower()+(':production' if environment=='production' and write else ':version' if write else ':read'))

    async def _selection(self,session,args,environment):
        row=await session.scalar(select(self.selections).where(self.selections.project_id==args['project_id'],
            self.selections.resource_id==args['resource_id'],self.selections.environment==environment))
        if row is None:
            raise ConflictError('ASAC_SELECTION_INCONSISTENT: missing monotonic environment selection')
        await self.selector.check_selection(session,**args,selection=row)
        return row

    @staticmethod
    def _cas(selection,generation,previous=None,fingerprint=None,*,exact=False):
        if selection.generation!=generation or exact and (selection.snapshot_id!=previous or selection.execution_fingerprint!=fingerprint):
            raise ConflictError('ASAC_DEPLOYMENT_STALE: environment changed since the expected selection')

    async def _qualification(self,session,args,release_id,publication_id=None):
        pub=await session.get(self.publications.publications,publication_id) if publication_id else await session.scalar(
            select(self.publications.publications).where(self.publications.publications.project_id==args['project_id'],
                self.publications.publications.resource_id==args['resource_id'],self.publications.publications.release_id==release_id)
            .order_by(self.publications.publications.created_at.desc(),self.publications.publications.id.desc()).limit(1))
        if pub is None or pub.project_id!=args['project_id'] or pub.resource_id!=args['resource_id'] or pub.release_id!=release_id:
            raise ConflictError('ASAC_DEPLOYMENT_QUALIFICATION_REQUIRED: exact Release needs retained evaluated publication evidence')
        candidate,evaluation,record=await self.publications._proof(session,args['project_id'],args['resource_id'],
            SimpleNamespace(candidate_id=pub.candidate_id,evaluation_id=pub.evaluation_id))
        native=await self.selector.inspect(session,**args,release_id=release_id)
        if native['runtime_digest']!=candidate.runtime_digest or pub.evidence['runtime_digest']!=candidate.runtime_digest:
            raise ConflictError('ASAC_DEPLOYMENT_RUNTIME_CHANGED: Release differs from the evaluated publication')
        return pub,candidate,evaluation,record,native

    async def _policy(self,session,args,environment):
        if self.policy is None:
            value={'managed':False,'generation':0}
        else:
            value=await self.policy.inspect(session,**args,environment=environment)
        return {'policy':value,'project_policy_digest':asac_digest('project-lifecycle-policy',value)}

    async def plan(self,*,project_id,resource_id,principal,request):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request.environment,write=True)
            digest,replay=await self.drafts._operation(session,**args,request=request,action='deployment:plan')
            if replay is not None: return replay
            selection=await self._selection(session,args,request.environment)
            self._cas(selection,request.expected_generation)
            pub,candidate,evaluation,record,native=await self._qualification(session,args,request.release_id,request.publication_id)
        fingerprints=await self.publications.evaluations._bindings(candidate,project_id,principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request.environment,write=True)
            digest,replay=await self.drafts._operation(session,**args,request=request,action='deployment:plan')
            if replay is not None: return replay
            selection=await self._selection(session,args,request.environment)
            self._cas(selection,request.expected_generation)
            pub,current,evaluation,record,native=await self._qualification(session,args,request.release_id,pub.id)
            if fingerprints!=current.runtime_fingerprints:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED')
            await self.bindings.verify(session,**args,environment=request.environment,expected=fingerprints)
            policy=await self._policy(session,args,request.environment)
            now=await database_now(session)
            row=self.plans(project_id=project_id,resource_id=resource_id,publication_id=pub.id,release_id=request.release_id,
                environment=request.environment,expected_generation=selection.generation,previous_release_id=selection.snapshot_id,
                previous_fingerprint=selection.execution_fingerprint,actor=principal_identity(principal),operation_id=request.operation_id,
                request_digest=digest,action=request.action,reason=request.reason,expires_at=now+timedelta(seconds=self.maximum_plan_seconds),
                evidence={'kind':self.drafts.kind,'runtime_digest':current.runtime_digest,'runtime_digest_scope':current.runtime_digest_scope,
                    'record_digest':current.record_digest,'binding_digest':evaluation.binding_digest,
                    'runtime_fingerprints':fingerprints,'evaluation_id':str(evaluation.id),'candidate_id':str(current.id),
                    'native_fingerprint':native['fingerprint'],'clock_authority':'database',**policy})
            session.add(row); await session.flush()
            return self.drafts._receipt(session,**args,request=request,digest=digest,result=plan_output(row))

    async def _plan(self,session,args,plan_id):
        row=await session.get(self.plans,plan_id)
        if row is None or row.project_id!=args['project_id'] or row.resource_id!=args['resource_id']:
            raise NotFoundError('ASAC_DEPLOYMENT_PLAN_UNAVAILABLE')
        return row

    @asac_lease_database_errors
    async def apply(self,*,project_id,resource_id,principal,request):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request.environment,write=True)
            plan=await self._plan(session,args,request.plan_id)
            if plan.environment != request.environment: raise ConflictError('ASAC_DEPLOYMENT_PLAN_SCOPE_MISMATCH')
            digest,replay=await self.drafts._operation(session,**args,request=request,action='deployment:apply')
            if replay is not None: return replay
            pub,candidate,evaluation,record,native=await self._qualification(session,args,plan.release_id,plan.publication_id)
        fingerprints=await self.publications.evaluations._bindings(candidate,project_id,principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request.environment,write=True)
            plan=await self._plan(session,args,request.plan_id)
            if plan.environment != request.environment: raise ConflictError('ASAC_DEPLOYMENT_PLAN_SCOPE_MISMATCH')
            digest,replay=await self.drafts._operation(session,**args,request=request,action='deployment:apply')
            if replay is not None: return replay
            if await session.scalar(select(self.deployments.id).where(self.deployments.plan_id==plan.id)):
                raise ConflictError('ASAC_DEPLOYMENT_PLAN_ALREADY_APPLIED: reconcile the original deployment')
            if _utc(plan.expires_at)<=await database_now(session):
                raise ConflictError('ASAC_DEPLOYMENT_PLAN_EXPIRED: create an explicit new plan')
            selection=await self._selection(session,args,plan.environment)
            self._cas(selection,plan.expected_generation,plan.previous_release_id,plan.previous_fingerprint,exact=True)
            pub,candidate,evaluation,record,native=await self._qualification(session,args,plan.release_id,plan.publication_id)
            if fingerprints!=candidate.runtime_fingerprints or asac_digest('runtime-bindings',fingerprints)!=plan.evidence['binding_digest'] or native['fingerprint']!=plan.evidence['native_fingerprint']:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: requalify an altered executable destination')
            policy=await self._policy(session,args,plan.environment)
            if policy['project_policy_digest']!=plan.evidence['project_policy_digest']:
                raise ConflictError('ASAC_DEPLOYMENT_POLICY_CHANGED: create a plan under the current policy')
            await self.bindings.verify(session,**args,environment=plan.environment,expected=fingerprints)
            await self.drafts.leases.check(session,**args,scope=plan.environment,proofs=request.leases,required=True)
            identifier,outbox_id=uuid4(),uuid4()
            if session.bind.dialect.name=='postgresql':
                await session.execute(text("SELECT set_config('woobe.asac_deployment_id',:id,true)"),{'id':str(identifier)})
            previous,generation=selection.snapshot_id,selection.generation
            changed=previous!=plan.release_id or selection.execution_fingerprint!=native['fingerprint']
            await self.selector.apply(session,**args,environment=plan.environment,release_id=plan.release_id,
                previous_release_id=previous,action=plan.action,reason=plan.reason,changed=changed)
            selection.snapshot_id,selection.execution_fingerprint=plan.release_id,native['fingerprint']
            selection.selection_authority='asac'
            selection.generation=generation+int(changed)
            row=self.deployments(id=identifier,project_id=project_id,resource_id=resource_id,plan_id=plan.id,
                publication_id=pub.id,release_id=plan.release_id,previous_release_id=previous,environment=plan.environment,
                generation_before=generation,generation_after=selection.generation,actor=principal_identity(principal),
                operation_id=request.operation_id,request_digest=digest,action=plan.action,reason=plan.reason,
                selection_changed=changed,outbox_id=outbox_id,evidence={**plan.evidence,'plan_digest':plan_output(plan)['plan_digest'],
                    'leases':[proof.model_dump(mode='json') for proof in request.leases]})
            session.add(row); await session.flush()
            result=deployment_output(row)
            self.selector.add_outbox(session,model=self.outbox,identifier=outbox_id,resource_id=resource_id,
                operation_id=request.operation_id,receipt=result)
            return self.drafts._receipt(session,**args,request=request,digest=digest,result=result)

    async def get(self,*,project_id,resource_id,principal,identifier,plan=False,environment='production'):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts._read() as session:
            await self._authorize(session,args,environment)
            row=await session.get(self.plans if plan else self.deployments,identifier)
            if row is None or row.project_id!=project_id or row.resource_id!=resource_id or row.environment!=environment:
                raise NotFoundError('ASAC_DEPLOYMENT_UNAVAILABLE')
            return plan_output(row) if plan else deployment_output(row)
