"""Portable execution-intent digest from a verified, closed package inventory."""
from copy import deepcopy

from modules.package.domain.bundle import component_references, portable_path
from modules.package.domain.errors import PackageError
from shared.contracts.asac import asac_digest

DEFINITION_SCOPE = "woobe-portable-definition@1.0"
CONFIGURATION_DEFINITION_SCOPE = "woobe-portable-definition@2.0"


def definition_scope(manifest):
    version = manifest.get("schema_version", "1.0")
    if version not in {"1.0", "2.0"}:
        raise PackageError("ASAC_DEFINITION_INVALID", "Unsupported portable definition schema")
    return CONFIGURATION_DEFINITION_SCOPE if version == "2.0" else DEFINITION_SCOPE


def connection_intents(manifest):
    if definition_scope(manifest) == CONFIGURATION_DEFINITION_SCOPE:
        # Names and aliases are presentation; typed authentication and endpoint
        # intent are execution semantics. No destination authority enters here.
        return {key: {field: value for field, value in item.items() if field != "name"}
                for key, item in manifest["spec"].get("connections", {}).items()}
    return {item["ref"]: {key: value for key, value in item.items() if key != "ref"}
            for item in (manifest["spec"].get("requires") or {}).get("credentials", [])}


def portable_definition(bundle):
    files = {item["path"]: "sha256:" + item["sha256"] for item in bundle.inventory}
    requirements = bundle.graph.manifest["spec"].get("requires") or {}
    intents = connection_intents(bundle.graph.manifest)
    v2 = definition_scope(bundle.graph.manifest) == CONFIGURATION_DEFINITION_SCOPE
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
        components[key] = asac_digest("portable-component@2" if v2 else "portable-component", document)
    entrypoint = bundle.graph.manifest["spec"]["entrypoint"]["ref"]
    public = {key: value for key, value in requirements.items() if key != "credentials"}
    definition = {"entrypoint": components[entrypoint], "components": sorted(components.values()), "requires": public}
    if v2:
        definition["configuration"] = sorted(
            bundle.graph.manifest["spec"].get("configuration", {}).get("keys", []), key=lambda item: item["key"])
        definition["connections"] = sorted(provider_definition_digests(bundle.graph.manifest).values())
    digest = asac_digest("portable-definition@2" if v2 else "portable-definition", definition)
    return digest, components


def provider_definition_digests(manifest):
    if definition_scope(manifest) == CONFIGURATION_DEFINITION_SCOPE:
        return {key: asac_digest("portable-provider@2", value) for key, value in connection_intents(manifest).items()}
    result = {}
    for item in (manifest["spec"].get("requires") or {}).get("credentials", []):
        value = {"provider": item["provider"], **(item.get("metadata") or {})}
        result[item["ref"]] = asac_digest("portable-provider", value)
    return result
