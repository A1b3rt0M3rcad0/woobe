"""Owner-injected read adapter: immutable origin of the admitted native snapshot."""
from sqlalchemy import select

async def admitted_publication(session, *, publications, selections, deployments,
                               project_id, resource_id, snapshot_id, environment):
    selection = await session.scalar(select(selections).where(
        selections.project_id == project_id, selections.resource_id == resource_id,
        selections.environment == environment, selections.snapshot_id == snapshot_id))
    deployment = None
    if selection is not None and selection.selection_authority == 'asac':
        deployment = await session.scalar(select(deployments).where(
            deployments.project_id == project_id, deployments.resource_id == resource_id,
            deployments.environment == environment, deployments.release_id == snapshot_id,
            deployments.generation_after == selection.generation,
        ).order_by(deployments.created_at.desc(), deployments.id.desc()).limit(1))
    if deployment is not None:
        publication = await session.get(publications, deployment.publication_id)
        if (publication is None or publication.project_id != project_id
            or publication.resource_id != resource_id or publication.release_id != snapshot_id):
            return {'provenance_status': 'publication_unavailable'}
    else:
        matches = (await session.scalars(select(publications).where(
            publications.project_id == project_id, publications.resource_id == resource_id,
            publications.release_id == snapshot_id).limit(2))).all()
        if len(matches) != 1:
            return {'provenance_status': 'publication_ambiguous' if matches else 'unknown_origin'}
        publication = matches[0]
    evidence = publication.evidence
    return {'provenance_status': 'publication_verified',
        'verification_scope': 'published_snapshot_evidence_not_live_external_response',
        'publication_id': str(publication.id), 'resource_uid': str(publication.resource_uid),
        'revision_id': publication.revision_id, 'record_digest': evidence['record_digest'],
        'definition_digest': evidence['definition_digest'], 'runtime_digest': evidence['runtime_digest'],
        'selection_generation_at_admission': selection.generation if selection is not None else None,
        'deployment_id': str(deployment.id) if deployment is not None else None,
        'selection_relation': 'matches_at_admission' if selection is not None else 'pinned_snapshot'}
