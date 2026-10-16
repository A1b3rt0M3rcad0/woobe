"""Metadata-only access status, using the same policy matcher as runtime."""

from collections import defaultdict

from modules.core.domain.configuration_policy import matching_policy
from modules.core.domain.project_configuration import canonical_destination
from shared.contracts.project_configuration import ConfigurationError


def public_policy(row):
    if row is None:
        return None
    return {
        "id": str(row.id),
        "consumer_kind": row.consumer_kind,
        "consumer_scope": row.consumer_scope,
        "destination": row.destination,
        "field_paths": list(row.field_paths),
        "environments": list(row.environments),
        "revision": row.revision,
        "revoked": row.revoked,
    }


def approval_metadata(reference, policies, environment):
    try:
        destination = canonical_destination(reference.destination)
    except ConfigurationError:
        return {"state": "destination_required", "policy": None, "update_policy": None}
    eligible = [
        p
        for p in policies
        if p.consumer_kind == reference.consumer_kind
        and p.consumer_scope in {"*", str(reference.consumer_id)}
    ]
    effective = matching_policy(eligible, reference, environment)
    existing = next(
        (
            p
            for p in eligible
            if p.consumer_scope == str(reference.consumer_id)
            and p.destination == destination
        ),
        None,
    )
    return {
        "state": "approved" if effective else "approval_required",
        "policy": public_policy(effective),
        "update_policy": public_policy(existing),
    }


def approval_summary(references, policies, environment):
    connections = defaultdict(list)
    for reference in references:
        connections[
            (reference.consumer_kind, reference.consumer_id, reference.destination)
        ].append(approval_metadata(reference, policies, environment)["state"])
    approved = sum(
        all(state == "approved" for state in states) for states in connections.values()
    )
    return {
        "state": "no_connections"
        if not connections
        else "approved"
        if approved == len(connections)
        else "approval_required",
        "connection_count": len(connections),
        "approved_connection_count": approved,
    }
