"""Project captured owner definitions into a closed, destination-independent bundle."""

from copy import deepcopy
import json
import re

from modules.package.domain.bundle import (
    portable_path,
    MAX_FILES,
    MAX_FILE_BYTES,
    MAX_BUNDLE_BYTES,
)
from modules.package.domain.errors import PackageError

_ENV = re.compile(r"\{\{\s*project_env\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_SECRET = re.compile(r"\{\{secret:([^}]+)\}\}")


def reference_requirements(value):
    environment, secrets = set(), set()

    def visit(item):
        if isinstance(item, str):
            environment.update(_ENV.findall(item))
            secrets.update(name.strip() for name in _SECRET.findall(item))
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            if item.get("kind") == "project_environment" and isinstance(
                item.get("field"), str
            ):
                environment.add(item["field"])
            auth = item.get("auth") or {}
            if isinstance(auth, dict):
                secrets.update(auth.get("credentials") or [])
            secrets.update((item.get("env_secret_refs") or {}).values())
            for child in item.values():
                visit(child)

    visit(value)
    return environment, secrets


class ExportProjection:
    def __init__(self, *, knowledge_mode, environment_kinds):
        self.knowledge_mode, self.environment_kinds = knowledge_mode, environment_kinds
        self.files, self.documents, self.requirements = (
            {},
            {},
            {
                "credentials": [],
                "project_environment": [],
                "secrets": [],
                "knowledge": [],
            },
        )
        self.identities, self.credential_aliases = {}, {}
        self.environment, self.secrets = set(), set()
        self.document_reads = []
        self.total = 0

    def add_bytes(self, path, content):
        path = portable_path(path)
        if path in self.files:
            raise PackageError("PACKAGE_EXPORT_INVALID", "Export path is duplicated")
        if (
            len(self.files) >= MAX_FILES
            or len(content) > MAX_FILE_BYTES
            or self.total + len(content) > MAX_BUNDLE_BYTES
        ):
            raise PackageError(
                "PACKAGE_LIMIT_EXCEEDED", "Export exceeds bundle resource limits"
            )
        self.files[path], self.total = content, self.total + len(content)

    def add_document(
        self, kind, name, spec, *, key=None, version=None, description="", identity=None
    ):
        if identity is not None and (kind, identity) in self.identities:
            return self.identities[kind, identity]
        key = (
            key
            or f"{kind.lower()}-{1 + sum(item['kind'] == kind for item in self.documents.values())}"
        )
        document = {
            "format": "woobe-package",
            "schema_version": "1.0",
            "kind": kind,
            "metadata": {"key": key, "name": name, "description": description},
            "spec": deepcopy(spec),
        }
        if version is not None:
            document["metadata"]["version"] = version
        if key in self.documents:
            raise PackageError(
                "PACKAGE_EXPORT_INVALID", "Export component key is duplicated"
            )
        self.documents[key] = document
        if identity is not None:
            self.identities[kind, identity] = key
        return key

    def model(
        self,
        *,
        provider,
        model,
        credential_id,
        specification,
        credentials,
        base_url=None,
        model_type="language",
    ):
        if not specification:
            raise PackageError(
                "PACKAGE_EXPORT_INCOMPLETE", "Snapshot has no complete ModelSpec"
            )
        if credential_id not in credentials:
            raise PackageError(
                "PACKAGE_EXPORT_INCOMPLETE", "Snapshot credential intent is unavailable"
            )
        intent = credentials[credential_id]
        if intent["provider"] != provider:
            raise PackageError(
                "PACKAGE_EXPORT_INCOMPLETE", "Snapshot credential provider differs"
            )
        if credential_id not in self.credential_aliases:
            alias = f"credential-{len(self.credential_aliases) + 1}"
            self.credential_aliases[credential_id] = alias
            self.requirements["credentials"].append({"ref": alias, **intent})
        spec = {
            "provider": provider,
            "model": model,
            "credential": {"ref": self.credential_aliases[credential_id]},
            "model_type": model_type,
            "model_spec_hint": deepcopy(specification),
        }
        if base_url is not None:
            spec["base_url"] = base_url
        identity = json.dumps(spec, sort_keys=True, separators=(",", ":"))
        return self.add_document("Model", model, spec, identity=identity)

    def agent(self, captured, key):
        definition, runtime = (
            captured["definition"],
            captured["definition"]["runtime_config"],
        )
        primary = self.model(
            provider=definition["provider"],
            model=definition["model"],
            credential_id=definition["provider_credential_id"],
            specification=definition.get("model_spec_snapshot"),
            credentials=captured["credentials"],
            base_url=definition.get("base_url"),
        )
        model = {
            "primary": {"ref": primary},
            "parameters": {
                "temperature": definition.get("temperature"),
                "max_output_tokens": definition.get("max_output_tokens"),
            },
        }
        if definition.get("fallback_model"):
            model["fallback"] = {
                "ref": self.model(
                    provider=definition["fallback_provider"],
                    model=definition["fallback_model"],
                    credential_id=definition["fallback_credential_id"],
                    specification=definition.get("fallback_model_spec_snapshot"),
                    credentials=captured["credentials"],
                )
            }
        tools = []
        for tool in captured["tools"]:
            env, secrets = reference_requirements([tool["config"], tool["permissions"]])
            self.environment.update(env)
            self.secrets.update(secrets)
            spec = {
                field: deepcopy(tool[field])
                for field in (
                    "type",
                    "description",
                    "timeout_ms",
                    "config",
                    "input_schema",
                    "output_schema",
                    "permission",
                    "risk",
                    "permissions",
                )
            }
            identity = (tool["id"], json.dumps(spec, sort_keys=True))
            tools.append(
                {
                    "ref": self.add_document(
                        "Tool", tool["name"], spec, identity=identity
                    )
                }
            )
        skills = []
        for skill in captured["skills"]:
            identity = (skill["id"], skill["package_hash"])
            old = self.identities.get(("Skill", identity))
            if old is None:
                skill_key = f"skill-{1 + sum(item['kind'] == 'Skill' for item in self.documents.values())}"
                directory = f"skills/{skill_key}"
                package = skill["package"]
                self.add_bytes(directory + "/SKILL.md", package["skill_md"].encode())
                for path, content in package["resources"].items():
                    self.add_bytes(directory + "/" + path, content.encode())
                old = self.add_document(
                    "Skill",
                    skill["name"],
                    {
                        "version": skill["version"],
                        "package": {
                            "manifest": directory + "/SKILL.md",
                            "resources": [
                                directory + "/" + path for path in package["resources"]
                            ],
                        },
                        "required_tools": package["required_tools"],
                    },
                    key=skill_key,
                    version=skill["version"],
                    identity=identity,
                )
            skills.append(
                {"ref": old, "version": skill["version"], "enabled": skill["enabled"]}
            )
        spec = {
            "type": "chat",
            "model": model,
            "behavior": deepcopy(definition.get("behavior_spec")),
            "execution": {
                "strategy": runtime.get("execution_strategy", "standard"),
                "config": deepcopy(runtime.get("execution_strategy_config") or {}),
                "config_schema_version": runtime.get(
                    "execution_strategy_config_schema_version", "1"
                ),
            },
            "context": {
                "manager": deepcopy(
                    runtime.get("context_manager") or {"name": "stdcm"}
                ),
                "policy": deepcopy(runtime.get("context") or {}),
            },
            "session": {"mode": definition["session_mode"]},
            "tools": tools,
            "skills": skills,
            "external_context": deepcopy(
                definition.get("external_context_contract") or {}
            ),
            "output": {
                "response_format": deepcopy(definition.get("response_format")),
                "output_schema": deepcopy(definition.get("output_schema")),
            },
        }
        artifacts = captured["artifacts"]
        if prompt := artifacts.get("prompt_version_id"):
            spec["prompt_ref"] = self.add_document(
                "Prompt",
                prompt["name"],
                {"version": prompt["version"], "content": prompt["content"]},
                identity=json.dumps(prompt, sort_keys=True),
            )
        elif spec["behavior"] is None:
            spec["legacy_system_prompt"] = definition["system_prompt"]
        if contract := artifacts.get("contract_version_id"):
            native = {
                field: deepcopy(contract[field])
                for field in (
                    "version",
                    "validation_mode",
                    "repair_attempts",
                    "input_schema",
                    "output_schema",
                    "additional_instructions",
                )
            }
            if native["validation_mode"] == "loose":
                native["validation_mode"] = "lenient"
            spec["output"]["contract_ref"] = self.add_document(
                "Contract",
                contract["name"],
                native,
                identity=json.dumps(native, sort_keys=True),
            )
        if knowledge := captured["knowledge"]:
            vector, embedding = knowledge["vector"], knowledge["embedding"]
            knowledge_key = f"knowledge-{1 + sum(item['kind'] == 'Knowledge' for item in self.documents.values())}"
            if self.knowledge_mode == "binding":
                alias = knowledge_key + "-destination"
                self.requirements["knowledge"].append({"ref": alias})
                knowledge_spec = {"mode": "binding", "binding": {"ref": alias}}
            else:
                embedding_ref = self.model(
                    provider=vector["embedding_provider"],
                    model=embedding["model"],
                    credential_id=str(embedding["provider_credential_id"]),
                    specification=embedding["spec"],
                    credentials=captured["credentials"],
                    model_type=embedding["model_type"],
                )
                documents = []
                for index, document in enumerate(knowledge["documents"]):
                    suffix = document["file_name"].rsplit(".", 1)[-1].lower()
                    if not re.fullmatch(r"[a-z0-9]{1,10}", suffix):
                        raise PackageError(
                            "PACKAGE_EXPORT_INVALID",
                            "Document filename has no portable extension",
                        )
                    path = f"documents/{knowledge_key}/{index + 1}.{suffix}"
                    self.document_reads.append((path, document))
                    documents.append(
                        {
                            "path": path,
                            "title": document["title"],
                            "content_type": document["content_type"],
                        }
                    )
                knowledge_spec = {
                    "mode": "portable",
                    "collection": knowledge["collection"],
                    "documents": documents,
                    "embedding": {"model_ref": embedding_ref},
                    "vector_snapshot": deepcopy(vector["build_config"]),
                }
            self.add_document(
                "Knowledge",
                knowledge["collection"]["name"],
                knowledge_spec,
                key=knowledge_key,
            )
            spec["knowledge"] = {
                "source": {"ref": knowledge_key},
                "strategy": runtime.get("knowledge_strategy", "rag"),
                "strategy_config": deepcopy(
                    runtime.get("knowledge_strategy_config") or {}
                ),
                "strategy_config_schema_version": runtime.get(
                    "knowledge_strategy_config_schema_version", "1"
                ),
                "rag": deepcopy(runtime.get("rag") or {}),
            }
        return self.add_document(
            "Agent",
            definition["name"],
            spec,
            key=key,
            description=definition.get("description") or "",
        )

    def finish(self, *, kind, captured, name, version):
        if kind == "Agent":
            entry = self.agent(captured, "agent-1")
        else:
            for agent in captured["agents"]:
                self.agent(agent, agent["key"])
            entry = self.add_document(
                "Network",
                captured["name"],
                captured["spec"],
                key="network-1",
                description=captured["description"],
            )
        for key in sorted(self.environment):
            if key not in self.environment_kinds:
                raise PackageError(
                    "PACKAGE_EXPORT_INCOMPLETE",
                    "Project Environment requirement is unavailable",
                )
            self.requirements["project_environment"].append(
                {"key": key, "kind": self.environment_kinds[key]}
            )
        self.requirements["secrets"] = [{"ref": name} for name in sorted(self.secrets)]
        # Descriptors live at the root so support paths have one canonical base.
        for key, document in self.documents.items():
            self.add_bytes(
                key + ".yaml",
                (
                    json.dumps(
                        document, ensure_ascii=False, sort_keys=True, allow_nan=False
                    )
                    + "\n"
                ).encode(),
            )
        manifest = {
            "format": "woobe-package",
            "schema_version": "1.0",
            "kind": "Package",
            "metadata": {"name": name, "version": version},
            "spec": {
                "entrypoint": {"kind": kind, "ref": entry},
                "resources": [key + ".yaml" for key in self.documents],
                "requires": self.requirements,
                "integrity": {"algorithm": "sha256"},
            },
            "provenance": {
                "exporter": "woobe",
                "snapshot_schema_version": "1.0",
                "source_release": {
                    "version": captured["source"].get("version"),
                    "kind": captured["source"]["kind"],
                },
            },
        }
        self.add_bytes(
            "woobe.yaml",
            (
                json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, allow_nan=False
                )
                + "\n"
            ).encode(),
        )
        return self
