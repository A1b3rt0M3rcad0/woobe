"""Shared persistence mechanics executed through each native lifecycle owner."""
from uuid import UUID, uuid5
from shared.contracts.asac import asac_digest
from shared.contracts.asac_requests import RegisterASaCRevision
from shared.contracts.errors import ConflictError
from shared.infra.asac_lease_errors import asac_lease_database_errors


class ASaCWorkbench:
    async def editor_source(self, *, project_id,resource_id,draft_id,principal):
        line=await self.get_draft(project_id=project_id,resource_id=resource_id,draft_id=draft_id,principal=principal)
        if line['artifact_id'] is None:
            raise ConflictError('ASAC_DRAFT_UNSEALED: Open a closed isolated Draft before editing')
        source=await self.artifacts.editor_source(project_id=project_id,principal=principal,artifact_id=line['artifact_id'])
        current=await self.get_draft(project_id=project_id,resource_id=resource_id,draft_id=draft_id,principal=principal)
        if current['generation']!=line['generation'] or current['artifact_id']!=line['artifact_id']:
            raise ConflictError('ASAC_DRAFT_CHANGED: Draft changed during editor capture')
        return {**source,'draft':line,'production_changed':False,'semantic_validation':'stage_required'}

    @asac_lease_database_errors
    async def edit_author_files(self, *, project_id,resource_id,draft_id,principal,request):
        from shared.infra.asac_draft_store import draft_output
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.transactions.begin() as session:
            await self._authorize(session,**args,write=True,lock=True)
            digest,replay=await self._operation(session,**args,request=request,action='edit:'+str(draft_id))
            if replay is not None:
                return replay
            await self._check_leases(session,**args,request=request,scope='draft:'+str(draft_id))
            line=await self._line(session,project_id,resource_id,draft_id)
            if line.generation!=request.expected_generation or line.artifact_id is None:
                raise ConflictError('ASAC_DRAFT_CHANGED: Editor generation is stale or unsealed')
            original=line.artifact_id
        artifact=await self.artifacts.retain_edits(project_id=project_id,principal=principal,
            artifact_id=original,files=[item.model_dump() for item in request.files])
        if artifact['manifest']['spec']['entrypoint']['kind']!=self.kind:
            raise ConflictError('ASAC_KIND_MISMATCH: Editor cannot change native owner kind')
        async with self.transactions.begin() as session:
            await self._authorize(session,**args,write=True,lock=True)
            digest,replay=await self._operation(session,**args,request=request,action='edit:'+str(draft_id))
            if replay is not None:
                return replay
            await self._check_leases(session,**args,request=request,scope='draft:'+str(draft_id))
            line=await self._line(session,project_id,resource_id,draft_id)
            if line.generation!=request.expected_generation or line.artifact_id!=original:
                raise ConflictError('ASAC_DRAFT_CHANGED: Editor lost its write precondition')
            line.artifact_id=UUID(artifact['artifact_id'])
            if line.definition_digest!=artifact['definition_digest']:
                line.working_revision_id=None
            line.definition_digest=artifact['definition_digest'];line.generation+=1
            return self._receipt(session,**args,request=request,digest=digest,result=draft_output(line))

    async def checkpoint_editor(self, *, project_id,resource_id,draft_id,principal,request):
        from sqlalchemy import select
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.transactions.begin() as session:
            await self._authorize(session,**args,write=True)
        # Consult the original owner operation before deriving a new record.
        original=await self.operation(**args,operation_id=request.operation_id)
        if original.get('state')=='committed':
            result=original['result'];record=result.get('record',{})
            if (record.get('revision_id')!=request.revision_id or record.get('message')!=request.message
                or record.get('parents')!=request.parents or result.get('draft_id')!=str(draft_id)
                or result.get('generation')!=request.expected_generation):
                raise ConflictError('ASAC_OPERATION_CONFLICT: Checkpoint operation has another payload')
            async with self._read() as session:
                await self._authorize(session,**args,write=True)
                revision=await session.scalar(select(self.revisions).where(
                    self.revisions.project_id==project_id,self.revisions.resource_id==resource_id,
                    self.revisions.revision_id==request.revision_id))
                if revision is None:
                    raise ConflictError('ASAC_REVISION_UNAVAILABLE')
                component_uids=dict(revision.component_uids or {})
                provider_uids=dict(revision.provider_uids or {})
            return await self.register_revision(**args,request=RegisterASaCRevision(
                operation_id=request.operation_id,draft_id=draft_id,expected_generation=request.expected_generation,
                record=record,component_uids=component_uids,provider_uids=provider_uids,leases=request.leases))
        line=await self.get_draft(**args,draft_id=draft_id)
        if line['generation']!=request.expected_generation or line['artifact_id'] is None:
            raise ConflictError('ASAC_DRAFT_CHANGED: Save this editor generation before checkpointing')
        artifact=await self.artifacts.get(project_id=project_id,principal=principal,artifact_id=line['artifact_id'])
        namespace=UUID(line['resource_uid']);entry=artifact['manifest']['spec']['entrypoint']['ref']
        uids={key:str(uuid5(namespace,'component:'+key)) for key in artifact['component_digests']}
        uids[entry]=line['resource_uid']
        providers={key:uuid5(namespace,'provider:'+key) for key in artifact['provider_digests']}
        record={'format':'woobe-revision','schema_version':'1.0','revision_id':request.revision_id,
            'resource_uid':line['resource_uid'],'kind':self.kind,'parents':request.parents,'message':request.message,
            'artifact_digest':artifact['artifact_digest'],'definition_digest':artifact['definition_digest'],
            'definition_digest_scope':artifact['definition_digest_scope'],
            'component_digests':{uids[key]:value for key,value in artifact['component_digests'].items()}}
        record['component_digests'].update({str(providers[key]):value for key,value in artifact['provider_digests'].items()})
        record['record_digest']=asac_digest('record',record)
        return await self.register_revision(**args,request=RegisterASaCRevision(
            operation_id=request.operation_id,draft_id=draft_id,expected_generation=request.expected_generation,
            record=record,component_uids=uids,provider_uids=providers,leases=request.leases))
