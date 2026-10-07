from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import posixpath
import re
import unicodedata

from modules.package.domain.errors import PackageError


MAX_FILES = 1024
MAX_DESCRIPTOR_TOTAL = 16 << 20
MAX_FILE_BYTES = 64 << 20
MAX_BUNDLE_BYTES = 512 << 20
MAX_ARCHIVE_BYTES = 128 << 20
RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


class PathRegistry:
    def __init__(self):
        self.paths = {}

    def register(self, path, *, directory=False):
        parts = path.split("/")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            is_directory = index < len(parts) or directory
            identity = (prefix, is_directory)
            normalized = unicodedata.normalize("NFC", prefix.casefold())
            previous = self.paths.get(normalized)
            if previous is not None and previous != identity:
                raise PackageError(
                    "PACKAGE_PATH_INVALID",
                    "Path case collision or file/directory conflict",
                    file=path,
                )
            self.paths[normalized] = identity


def portable_path(value: str, *, descriptor: str = "") -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
    ):
        raise PackageError("PACKAGE_PATH_INVALID", "Path must be portable and relative")
    if any(ord(char) < 32 or ord(char) == 127 or char in '<>:"|?*' for char in value):
        raise PackageError("PACKAGE_PATH_INVALID", "Path contains a nonportable name")
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(descriptor), value))
    if joined in {".", ".."} or joined.startswith("../"):
        raise PackageError("PACKAGE_PATH_INVALID", "Path escapes package root")
    for part in joined.split("/"):
        if (
            not part
            or part.endswith((".", " "))
            or RESERVED.match(part)
            or part.casefold() == ".git"
        ):
            raise PackageError("PACKAGE_PATH_INVALID", "Path contains a reserved name")
    return joined


def inventory_digest(inventory: list[dict]) -> str:
    tuples = [
        [item["path"], item["size_bytes"], item["sha256"]]
        for item in sorted(inventory, key=lambda item: item["path"])
    ]
    data = json.dumps(
        tuples, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    data = data.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return sha256(b"woobe-package@1.0\n" + data.encode("utf-8")).hexdigest()


def component_references(document: dict) -> list[tuple[str, str, str]]:
    spec = document["spec"]
    kind = document["kind"]
    refs = []

    def add(value, expected, path):
        if value:
            refs.append((value, expected, path))

    if kind == "Agent":
        for role in ("primary", "fallback"):
            add(
                (spec["model"].get(role) or {}).get("ref"),
                "Model",
                f"/spec/model/{role}/ref",
            )
        for index, item in enumerate(spec.get("tools", [])):
            add(item["ref"], "Tool", f"/spec/tools/{index}/ref")
        for index, item in enumerate(spec.get("skills", [])):
            add(item["ref"], "Skill", f"/spec/skills/{index}/ref")
        add(spec.get("prompt_ref"), "Prompt", "/spec/prompt_ref")
        add(
            (spec.get("output") or {}).get("contract_ref"),
            "Contract",
            "/spec/output/contract_ref",
        )
        add(
            ((spec.get("knowledge") or {}).get("source") or {}).get("ref"),
            "Knowledge",
            "/spec/knowledge/source/ref",
        )
    if kind == "Network":
        for index, item in enumerate(spec["nodes"]):
            add(item["agent_ref"], "Agent", f"/spec/nodes/{index}/agent_ref")
    if kind == "Knowledge":
        add(
            (spec.get("embedding") or {}).get("model_ref"),
            "Model",
            "/spec/embedding/model_ref",
        )
    return refs


def support_paths(document: dict, descriptor: str) -> list[str]:
    spec = document["spec"]
    if document["kind"] == "Skill":
        package = spec["package"]
        return [
            portable_path(value, descriptor=descriptor)
            for value in [package["manifest"], *package.get("resources", [])]
        ]
    if document["kind"] == "Knowledge":
        return [
            portable_path(item["path"], descriptor=descriptor)
            for item in spec.get("documents", [])
        ]
    return []


@dataclass(frozen=True)
class PackageGraph:
    manifest: dict
    components: dict[str, dict]
    paths: dict[str, str]
    order: tuple[str, ...]


def resolve_graph(manifest: dict, documents: dict[str, dict]) -> PackageGraph:
    index, paths = {}, {}
    for path, document in documents.items():
        if document["kind"] in {"Package", "PackageLock", "ImportBindings"}:
            raise PackageError(
                "PACKAGE_RESOURCE_INVALID",
                "Operational documents cannot be components",
                file=path,
            )
        key = document["metadata"]["key"]
        if key in index:
            raise PackageError(
                "PACKAGE_REFERENCE_DUPLICATE",
                "Component key is duplicated",
                file=path,
                path="/metadata/key",
            )
        index[key], paths[key] = document, path
    entry = manifest["spec"]["entrypoint"]
    if entry["ref"] not in index or index[entry["ref"]]["kind"] != entry["kind"]:
        raise PackageError(
            "PACKAGE_REFERENCE_NOT_FOUND",
            "Entrypoint does not resolve to its declared kind",
        )
    adjacency = {}
    requirements = manifest["spec"].get("requires", {})
    for group in ("credentials", "project_environment", "secrets", "knowledge"):
        field = "key" if group == "project_environment" else "ref"
        aliases = [item[field] for item in requirements.get(group, [])]
        if len(aliases) != len(set(aliases)):
            raise PackageError(
                "PACKAGE_REQUIREMENT_DUPLICATE",
                "Destination requirement is duplicated",
                path=f"/spec/requires/{group}",
            )
    knowledge_requirements = {item["ref"] for item in requirements.get("knowledge", [])}
    credential_requirements = {}
    for requirement in requirements.get("credentials", []):
        if requirement["ref"] in credential_requirements:
            raise PackageError(
                "PACKAGE_REQUIREMENT_DUPLICATE", "Credential requirement is duplicated"
            )
        credential_requirements[requirement["ref"]] = requirement["provider"]
    for key, document in index.items():
        adjacency[key] = []
        if document["kind"] == "Model":
            spec = document["spec"]
            if (
                credential_requirements.get(spec["credential"]["ref"])
                != spec["provider"]
            ):
                raise PackageError(
                    "PACKAGE_REQUIREMENT_INVALID",
                    "Model credential must reference a declared requirement with the same provider",
                    file=paths[key],
                    path="/spec/credential/ref",
                )
        if document["kind"] == "Network":
            validate_network_structure(document["spec"], paths[key])
        for ref, kind, pointer in component_references(document):
            if ref not in index:
                raise PackageError(
                    "PACKAGE_REFERENCE_NOT_FOUND",
                    "Component reference is missing",
                    file=paths[key],
                    path=pointer,
                )
            if index[ref]["kind"] != kind:
                raise PackageError(
                    "PACKAGE_REFERENCE_KIND",
                    "Component reference has the wrong kind",
                    file=paths[key],
                    path=pointer,
                )
            adjacency[key].append(ref)
        if document["kind"] == "Agent":
            spec = document["spec"]
            sources = [
                spec.get("behavior"),
                spec.get("prompt_ref"),
                spec.get("legacy_system_prompt"),
            ]
            if sum(value is not None for value in sources) != 1:
                raise PackageError(
                    "PACKAGE_BEHAVIOR_CONFLICT",
                    "Agent requires exactly one instruction source",
                    file=paths[key],
                )
            for binding in spec.get("skills", []):
                if index[binding["ref"]]["spec"]["version"] != binding["version"]:
                    raise PackageError(
                        "PACKAGE_REFERENCE_VERSION",
                        "Skill version assertion differs from descriptor",
                        file=paths[key],
                    )
        if document["kind"] == "Knowledge":
            spec = document["spec"]
            if spec["mode"] == "portable":
                if (
                    not spec.get("collection")
                    or not spec.get("documents")
                    or not spec.get("embedding")
                    or not isinstance(spec.get("vector_snapshot"), dict)
                    or spec.get("binding")
                ):
                    raise PackageError(
                        "PACKAGE_KNOWLEDGE_INVALID",
                        "Portable Knowledge requires documents, collection, embedding and build configuration",
                        file=paths[key],
                    )
            elif not spec.get("binding") or any(
                spec.get(field)
                for field in ("collection", "documents", "embedding", "vector_snapshot")
            ):
                raise PackageError(
                    "PACKAGE_KNOWLEDGE_INVALID",
                    "Binding Knowledge must contain only a destination requirement",
                    file=paths[key],
                )
            if (
                spec["mode"] == "binding"
                and spec["binding"]["ref"] not in knowledge_requirements
            ):
                raise PackageError(
                    "PACKAGE_REQUIREMENT_NOT_FOUND",
                    "Knowledge binding must declare a destination requirement",
                    file=paths[key],
                )
    order = topological_order(
        adjacency,
        sorted(index),
        lambda key: PackageError(
            "PACKAGE_REFERENCE_CYCLE", "Component reference cycle", file=paths[key]
        ),
    )
    return PackageGraph(manifest, index, paths, tuple(order))


def topological_order(adjacency, roots, cycle_error):
    colors, order = {}, []
    for root in roots:
        stack = [(root, False)]
        while stack:
            key, exiting = stack.pop()
            if exiting:
                colors[key] = 2
                order.append(key)
                continue
            if colors.get(key) == 2:
                continue
            if colors.get(key) == 1:
                raise cycle_error(key)
            colors[key] = 1
            stack.append((key, True))
            stack.extend((child, False) for child in reversed(adjacency[key]))
    return order


def validate_network_structure(spec, file):
    nodes = {node["key"] for node in spec["nodes"]}
    if len(nodes) != len(spec["nodes"]) or spec["root"] not in nodes:
        raise PackageError(
            "PACKAGE_NETWORK_INVALID",
            "Network requires unique node keys and a declared root",
            file=file,
        )
    edges, adjacency = set(), {node: [] for node in nodes}
    for edge in spec.get("edges", []):
        pair = (edge["from"], edge["to"])
        if pair in edges or any(node not in nodes for node in pair):
            raise PackageError(
                "PACKAGE_NETWORK_INVALID",
                "Network edge is duplicated or references an unknown node",
                file=file,
            )
        edges.add(pair)
        adjacency[pair[0]].append(pair[1])
    order = topological_order(
        adjacency,
        [spec["root"]],
        lambda _: PackageError(
            "PACKAGE_NETWORK_INVALID", "Network graph contains a cycle", file=file
        ),
    )
    if set(order) != nodes:
        raise PackageError(
            "PACKAGE_NETWORK_INVALID",
            "Network contains nodes unreachable from the root",
            file=file,
        )
