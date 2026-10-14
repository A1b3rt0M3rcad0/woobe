"""Versioned portable configuration intent, never destination authority."""


def package_requirements(manifest):
    if manifest.get("schema_version", "1.0") == "1.0":
        return manifest["spec"].get("requires", {})
    spec = manifest["spec"]
    declarations = spec.get("configuration", {}).get("keys", [])
    connections = spec.get("connections", {})
    return {"credentials": [{"ref": alias, "provider": item["provider"], "metadata": item.get("metadata")}
            for alias, item in connections.items()], "project_environment": declarations,
        "knowledge": spec.get("requires", {}).get("knowledge", []),
        "configuration": {item["key"]: item for item in declarations}, "connections": connections}
