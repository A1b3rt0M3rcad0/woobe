"""Portable execution-intent digest from a verified, closed package inventory."""
from copy import deepcopy

from modules.package.domain.bundle import component_references, portable_path
from modules.package.domain.errors import PackageError
from shared.contracts.asac import asac_digest

DEFINITION_SCOPE = "woobe-portable-definition@1.0"


def portable_definition(bundle):
    files = {item["path"]: "sha256:" + item["sha256"] for item in bundle.inventory}
    requirements = bundle.graph.manifest["spec"].get("requires") or {}
    intents = {item["ref"]: {key: value for key, value in item.items() if key != "ref"} for item in requirements.get("credentials", [])}
    components = {}
    for key in bundle.graph.order:
        document = deepcopy(bundle.graph.components[key])
        document["metadata"].pop("key", None)
        document.pop("provenance", None)
        for ref, _, pointer in component_references(document):
            parent = document
            parts = pointer.lstrip("/").split("/")
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            parent[parts[-1]] = components[ref]
        kind, spec = document["kind"], document["spec"]
        if kind == "Model":
            alias = spec["credential"]["ref"]
            if alias not in intents:
                raise PackageError("ASAC_DEFINITION_INVALID", "Model has no portable credential intent")
            spec["credential"] = intents[alias]
        def support_hash(value):
            return files[portable_path(value, descriptor=bundle.graph.paths[key])]
        if kind == "Skill":
            spec["package"]["manifest"] = support_hash(spec["package"]["manifest"])
            spec["package"]["resources"] = [support_hash(value) for value in spec["package"].get("resources", [])]
        if kind == "Knowledge":
            for item in spec.get("documents", []):
                item["path"] = support_hash(item["path"])
        components[key] = asac_digest("portable-component", document)
    entrypoint = bundle.graph.manifest["spec"]["entrypoint"]["ref"]
    public = {key: value for key, value in requirements.items() if key != "credentials"}
    digest = asac_digest("portable-definition", {"entrypoint": components[entrypoint], "components": sorted(components.values()), "requires": public})
    return digest, components


def provider_definition_digests(manifest):
    result = {}
    for item in (manifest["spec"].get("requires") or {}).get("credentials", []):
        value = {"provider": item["provider"], **(item.get("metadata") or {})}
        result[item["ref"]] = asac_digest("portable-provider", value)
    return result
