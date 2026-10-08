"""Compare author definitions independently of package keys and support paths."""

from copy import deepcopy

from modules.package.application.planning import definition_digest
from modules.package.domain.bundle import component_references, portable_path


def semantic_digests(components, order, paths, inventory, credentials):
    files = {item["path"]: item["sha256"] for item in inventory}
    result = {}
    for key in order:
        document = deepcopy(components[key])
        document.get("metadata", {}).pop("key", None)
        for ref, _, pointer in component_references(document):
            parent = document
            parts = pointer.lstrip("/").split("/")
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            parent[parts[-1]] = result[ref]
        kind, spec = document["kind"], document["spec"]
        if kind == "Model":
            alias = spec["credential"]["ref"]
            spec["credential"]["ref"] = credentials[alias]
        if kind == "Skill":
            package = spec["package"]
            package["manifest"] = files[
                portable_path(package["manifest"], descriptor=paths[key])
            ]
            package["resources"] = [
                files[portable_path(value, descriptor=paths[key])]
                for value in package.get("resources", [])
            ]
        if kind == "Knowledge":
            for item in spec.get("documents", []):
                item["path"] = files[portable_path(item["path"], descriptor=paths[key])]
        result[key] = definition_digest(document)
    return result
