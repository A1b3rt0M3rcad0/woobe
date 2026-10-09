"""Short owner transactions, database clock, bounded leases and stable receipts."""
from datetime import UTC, timedelta
import json
from uuid import uuid4
from sqlalchemy import DateTime, func, select, text
from shared.contracts.asac import asac_digest
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.admin_idempotency import principal_identity


def _utc(value):
    return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)


async def database_now(session):
    expression = func.clock_timestamp() if session.bind.dialect.name == 'postgresql' else func.current_timestamp(type_=DateTime(timezone=True))
    return _utc(await session.scalar(select(expression)))


def lease_output(row, now):
    return {'schema_version':'1.0','project_id':str(row.project_id),'resource_id':str(row.resource_id),
        'scope':row.scope,'lease_id':str(row.lease_id),'workflow_id':str(row.workflow_id),
        'fencing_token':row.fencing_token,'actor':row.actor,
        'state':'expired' if row.state=='active' and _utc(row.expires_at)<=now else row.state,
        'acquired_at':_utc(row.acquired_at).isoformat(),'expires_at':_utc(row.expires_at).isoformat(),
        'maximum_expires_at':_utc(row.maximum_expires_at).isoformat(),'server_time':now.isoformat(),
        'clock_authority':'database','complete':True}


class ASaCLeaseStore:
    def __init__(self, *, drafts, leases, maximum_ttl_seconds=300, maximum_duration_seconds=900, clock=database_now):
        if not 1 <= maximum_ttl_seconds <= maximum_duration_seconds <= 86400:
            raise ValueError('Lease duration limits are invalid')
        self.drafts,self.leases,self.clock=drafts,leases,clock
        self.maximum_ttl_seconds,self.maximum_duration_seconds=maximum_ttl_seconds,maximum_duration_seconds

    async def _authorize(self, session, args, scope, *, write=False, administrative=False):
        environment=scope.scope if scope.scope in {'staging','production'} else 'draft'
        permission=self.drafts.kind.lower()+(':production' if environment=='production' else ':version' if environment=='staging' else ':write') if write else self.drafts.kind.lower()+':read'
        if administrative:
            permission='project:access:write'
        await self.drafts.owner.inspect(session,**args,kind=self.drafts.kind,
            environment=environment,required_permission=permission,lock=write)
        if scope.draft_id is not None:
            row=await session.get(self.drafts.drafts,scope.draft_id)
            if row is None or row.project_id!=args['project_id'] or row.resource_id!=args['resource_id']:
                raise NotFoundError('ASAC_DRAFT_UNAVAILABLE: lease scope is not an accessible Draft')

    async def _row(self, session, args, key):
        return await session.scalar(select(self.leases).where(self.leases.project_id==args['project_id'],
            self.leases.resource_id==args['resource_id'],self.leases.scope==key))

    def _ttl(self, request):
        if request.ttl_seconds>self.maximum_ttl_seconds:
            raise ValidationError('ASAC_LEASE_DURATION_INVALID: requested TTL exceeds the server limit')
        return timedelta(seconds=request.ttl_seconds)

    @staticmethod
    def _proof(row, principal, proof, now):
        if row is None or row.lease_id!=proof.lease_id or row.fencing_token!=proof.fencing_token:
            raise ConflictError('ASAC_LEASE_FENCED: lease identity or fencing token was superseded')
        if row.actor!=principal_identity(principal) or row.workflow_id!=proof.workflow_id:
            raise ConflictError('ASAC_LEASE_WORKFLOW_MISMATCH: credentials do not identify the reserving workflow')
        if row.state!='active' or _utc(row.expires_at)<=now:
            raise ConflictError('ASAC_LEASE_EXPIRED: an expired or released lease cannot authorize a write')

    async def acquire(self, *, project_id, resource_id, principal, request):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        ttl=self._ttl(request)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request,write=True)
            digest,replay=await self.drafts._operation(session,**args,request=request,action='lease:acquire')
            if replay is not None:
                return replay
            now=await self.clock(session)
            row=await self._row(session,args,request.key())
            if row is not None and row.state=='active' and _utc(row.expires_at)>now:
                raise ConflictError('ASAC_LEASE_HELD: use the original lease proof for renewal; credential reuse is not reentrancy')
            if row is None:
                row=self.leases(project_id=project_id,resource_id=resource_id,scope=request.key(),fencing_token=1)
                session.add(row)
            else:
                row.fencing_token+=1
            row.lease_id=uuid4();row.workflow_id=request.workflow_id;row.actor=principal_identity(principal)
            row.state='active';row.acquired_at=now;row.expires_at=now+ttl
            row.maximum_expires_at=now+timedelta(seconds=self.maximum_duration_seconds)
            await session.flush()
            result=lease_output(row,now)
            return self.drafts._receipt(session,**args,request=request,digest=digest,result=result)

    async def change(self, *, project_id, resource_id, principal, request, action):
        if action not in {'renew','release','break'}:
            raise ValidationError('ASAC_LEASE_ACTION_INVALID')
        ttl=self._ttl(request) if action=='renew' else None
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session,args,request,write=True,administrative=action=='break')
            digest,replay=await self.drafts._operation(session,**args,request=request,action='lease:'+action)
            if replay is not None:
                return replay
            now=await self.clock(session)
            row=await self._row(session,args,request.key())
            if action=='break':
                if row is None or row.lease_id!=request.lease_id or row.fencing_token!=request.fencing_token:
                    raise ConflictError('ASAC_LEASE_FENCED: refusing to break a different current lease')
                if row.state!='active':
                    raise ConflictError('ASAC_LEASE_TERMINAL: use the original break receipt')
                row.state='broken'
            else:
                self._proof(row,principal,request,now)
                if action=='renew':
                    deadline=min(now+ttl,_utc(row.maximum_expires_at))
                    if deadline<=_utc(row.expires_at):
                        raise ConflictError('ASAC_LEASE_MAXIMUM_REACHED: renewal cannot extend beyond the original maximum duration')
                    row.expires_at=deadline
                else:
                    row.state='released'
            await session.flush()
            result=lease_output(row,now)
            if action=='break':
                result.update(broken_by=principal_identity(principal),reason=request.reason)
            return self.drafts._receipt(session,**args,request=request,digest=digest,result=result)

    async def get(self, *, project_id, resource_id, principal, scope):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts._read() as session:
            await self._authorize(session,args,scope)
            row=await self._row(session,args,scope.key())
            if row is None:
                return {'schema_version':'1.0','project_id':str(project_id),'resource_id':str(resource_id),
                    'scope':scope.key(),'state':'unreserved','clock_authority':'database','complete':True}
            return lease_output(row,await self.clock(session))

    async def check(self, session, *, project_id, resource_id, principal, scope, proofs=(), required=False):
        """Call under the native root lock in the transaction that writes."""
        now=await self.clock(session)
        args=dict(project_id=project_id,resource_id=resource_id)
        rows=[await self._row(session,args,key) for key in {'resource',scope}]
        active={row.lease_id:row for row in rows if row is not None and row.state=='active' and _utc(row.expires_at)>now}
        seen=set()
        for proof in proofs:
            if proof.lease_id in seen:
                raise ValidationError('ASAC_LEASE_PROOF_INVALID: duplicate lease identity')
            seen.add(proof.lease_id)
            row=next((row for row in rows if row is not None and row.lease_id==proof.lease_id),None)
            self._proof(row,principal,proof,now)
        if required and not active:
            raise ConflictError('ASAC_LEASE_REQUIRED: acquire a current workflow lease before writing')
        if set(active)!=seen:
            raise ConflictError('ASAC_LEASE_HELD: the active reservation requires its exact workflow lease proof')
        if session.bind.dialect.name == 'postgresql':
            await session.execute(text("SELECT set_config('woobe.asac_actor',:actor,true), set_config('woobe.asac_lease_proofs',:proofs,true), set_config('woobe.asac_lease_resource',:root,true)"),
                {'actor':principal_identity(principal),'root':str(resource_id),'proofs':json.dumps([proof.model_dump(mode='json') for proof in proofs])})
