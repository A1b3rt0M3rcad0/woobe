"""Append-only independent Git receipts through the lifecycle owner."""
from sqlalchemy import select
from shared.contracts.asac import asac_digest
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.asac_lease_store import database_now


class ASaCGitStore:
    def __init__(self, publications, verifier):
        self.publications,self.verifier=publications,verifier
        self.drafts=publications.drafts

    async def accept(self, *, project_id,resource_id,principal,request):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        publication_id=request.attestation.payload.publication_id
        async with self.drafts.transactions.begin() as session:
            await self.publications._authorize(session,**args,write=True)
            digest,replay=await self.drafts._operation(session,**args,request=request,action='git-attestation')
            if replay is not None:
                return replay
            publication=await session.get(self.publications.publications,publication_id)
            if publication is None or publication.project_id!=project_id or publication.resource_id!=resource_id:
                raise NotFoundError('ASAC_PUBLICATION_UNAVAILABLE')
            revision=await session.scalar(select(self.drafts.revisions).where(
                self.drafts.revisions.project_id==project_id,self.drafts.revisions.resource_id==resource_id,
                self.drafts.revisions.revision_id==publication.revision_id))
            if revision is None or not revision.author_artifact_id:
                raise ConflictError('ASAC_GIT_SOURCE_UNAVAILABLE: Publication requires retained compiler-verified author source')
            now=await database_now(session)
            payload=self.verifier.verify(signed=request.attestation,principal=principal,now=int(now.timestamp()))
            if (payload['project_id']!=str(project_id) or payload['resource_id']!=str(resource_id)
                or payload['kind']!=self.drafts.kind or payload['revision_id']!=publication.revision_id
                or payload['record_digest']!=publication.evidence['record_digest']
                or payload['definition_digest']!=publication.evidence['definition_digest']
                or payload['author_artifact_digest']!=revision.document.get('author_artifact_digest')):
                raise ConflictError('ASAC_GIT_CONTENT_MISMATCH: Pipeline evidence names another sealed publication')
            receipt={'schema_version':'1.0','attestation_id':str(request.operation_id),
                'publication_id':str(publication_id),'project_id':str(project_id),'resource_id':str(resource_id),
                'kind':self.drafts.kind,'git':{'status':'verified','repository':payload['repository'],
                    'commit':payload['commit'],'issuer':payload['issuer'],'workflow_run':payload['workflow_run']},
                'attestation':request.attestation.model_dump(mode='json'),'verified_at':now.isoformat(),
                'verification_scope':'trusted_pipeline_at_acceptance','published':False,'production_changed':False,
                'original_publication_unchanged':True,'complete':True}
            receipt['receipt_digest']=asac_digest('git-attestation-receipt',receipt)
            return self.drafts._receipt(session,**args,request=request,digest=digest,result=receipt)

    async def get(self, *, project_id,resource_id,principal,attestation_id):
        args=dict(project_id=project_id,resource_id=resource_id,principal=principal)
        async with self.drafts._read() as session:
            await self.publications._authorize(session,**args)
            rows=(await session.scalars(select(self.drafts.operations).where(
                self.drafts.operations.project_id==project_id,self.drafts.operations.resource_id==resource_id,
                self.drafts.operations.operation_id==attestation_id))).all()
            matches=[row.result for row in rows if row.result.get('attestation_id')==str(attestation_id)]
            if len(matches)!=1:
                raise NotFoundError('ASAC_GIT_ATTESTATION_UNAVAILABLE')
            return matches[0]
