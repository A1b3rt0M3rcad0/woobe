"""Public revision evidence for a vector build's selected Model and connection."""
from shared.contracts.errors import ConflictError


def vector_configuration_identity(model, credential):
    revision = getattr(model, "updated_at", None)
    return {"provider_credential_id": str(model.provider_credential_id),
        "credential_binding_revision": int(getattr(credential, "binding_revision", 1)),
        "provider_model_revision": revision.isoformat() if revision else None}


def verify_vector_configuration(snapshot, model, credential):
    if (str(getattr(credential.provider, "value", credential.provider)) != snapshot.embedding_provider
            or model.model != snapshot.embedding_model):
        raise ConflictError("Vector preparation Model changed; create a new snapshot version")
    evidence = (snapshot.build_config or {}).get("embedding", {})
    # Existing immutable snapshots predate these fields. Preserve their declared
    # model selection; new snapshots pin every available public revision.
    for field, value in vector_configuration_identity(model, credential).items():
        if field in evidence and evidence[field] != value:
            raise ConflictError("Vector preparation binding changed; create a new snapshot version")
