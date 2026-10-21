"""Pure destination and use-policy matching shared by runtime and metadata."""

from urllib.parse import urlsplit, urlunsplit

from modules.core.domain.project_configuration import canonical_destination


def destination_matches(approved: str, actual: str) -> bool:
    # Grants describe scheme/host/port/path. Query parameters belong to the
    # operation, never to credential delivery or the approved origin identity.
    parsed = urlsplit(actual)
    actual = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, "", parsed.fragment)
    )
    approved, actual = canonical_destination(approved), canonical_destination(actual)
    return actual == approved or actual.startswith(approved.rstrip("/") + "/")


def matching_policy(policies, dep, environment):
    matches = [
        p
        for p in policies
        if p.consumer_kind == dep.consumer_kind
        and p.consumer_scope in {"*", str(dep.consumer_id)}
        and environment in p.environments
        and dep.field_path in p.field_paths
        and not p.revoked
        and destination_matches(p.destination, dep.destination)
    ]
    # An exact consumer policy takes precedence. Stable ordering makes the
    # selected evidence independent of the database's row order.
    return (
        sorted(
            matches,
            key=lambda p: (p.consumer_scope == "*", -len(p.destination), str(p.id)),
        )[0]
        if matches
        else None
    )
