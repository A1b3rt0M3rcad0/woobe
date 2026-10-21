#!/usr/bin/env python3
"""Generate terminal comparisons using the real CLI and a local fixture API."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PROJECT = "00000000-0000-7000-8000-000000000010"
WORKSPACE = "00000000-0000-7000-8000-000000000020"
AGENTS = [
    {
        "id": f"00000000-0000-7000-8000-00000000000{index}",
        "project_id": PROJECT,
        "name": name,
        "description": f"Agent de {name.lower()}",
        "type": "LLM",
        "provider": "openai",
        "model": model,
        "status": status,
        "system_prompt": "Atenda em portugues. Consulte a base de conhecimento. " * 3,
        "behavior_spec": None,
        "provider_model_id": None,
        "fallback_provider_model_id": None,
        "provider_credential_id": None,
        "fallback_credential_id": None,
        "fallback_provider": None,
        "fallback_model": None,
        "temperature": 0.3,
        "max_output_tokens": 2048,
        "session_mode": "STATEFUL",
        "settings": {"max_steps": 8},
        "created_at": "2026-10-07T12:00:00Z",
        "updated_at": "2026-10-07T12:00:00Z",
    }
    for index, name, model, status in [
        (1, "Suporte", "gpt-4.1-mini", "draft"),
        (2, "Vendas", "gpt-4.1", "active"),
    ]
]
IDENTITY = {
    "schema_version": "1",
    "credential_type": "control",
    "key": {"id": "demo-control", "name": "Administrador", "expires_at": None},
    "workspace": {"id": WORKSPACE, "name": "My Workspace", "status": "active"},
    "projects": [{
        "id": PROJECT, "name": "ChatBot", "slug": "chatbot", "status": "active", "eligible": True,
        "permissions": [f"{domain}:{action}" for domain in ["agent", "network", "tool", "knowledge", "model", "project"] for action in ["read", "write", "delete"]],
    }],
}
OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Woobe fixture", "version": "example"},
    "paths": {
        "/ai/agents": {"get": {"responses": {"200": {"description": "Agents"}}}, "post": {"responses": {"200": {"description": "Created"}}}},
        "/network/projects/{project_id}/networks": {"get": {"responses": {"200": {"description": "Networks"}}}},
        "/identity/control-key/me": {"get": {"responses": {"200": {"description": "Identity"}}}},
    },
    "components": {"schemas": {"Agent": {"type": "object", "properties": {name: {"type": "string", "description": f"Agent field {name}"} for name in AGENTS[0]}}}},
}


class FixtureAPI(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/ai/agents":
            value = {"success": True, "data": AGENTS}
        elif path == f"/ai/agents/{AGENTS[0]['id']}":
            value = {"success": True, "data": AGENTS[0]}
        elif path == f"/network/projects/{PROJECT}/networks":
            value = {"success": True, "data": [{"id": "00000000-0000-7000-8000-000000000030", "project_id": PROJECT, "name": "Atendimento", "status": "draft", "description": "Rede de atendimento", "created_at": "2026-10-07T12:00:00Z"}]}
        elif path == "/identity/control-key/me":
            value = {"success": True, "data": IDENTITY}
        elif path == "/identity/instance/status":
            value = {"success": True, "data": {"status": "ready", "version": "example"}}
        elif path == "/openapi.json":
            value = OPENAPI
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path("docs"))
    args = parser.parse_args()
    binary = str(args.binary.resolve())
    destination = args.destination.resolve()
    examples = destination / "examples" / "output"
    examples.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureAPI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            origin = f"http://127.0.0.1:{server.server_port}"
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"version": 1, "current": "woobe", "contexts": {"woobe": {"api_url": origin, "workspace_id": WORKSPACE, "project_id": PROJECT}}}))
            env = {**os.environ, "WOOBE_CONTROL_KEY": "local-fixture-not-a-real-key", "WOOBE_OUTPUT": "auto"}
            for name in ["WOOBE_CONTEXT", "WOOBE_CREDENTIAL", "WOOBE_RUNTIME_CREDENTIAL", "WOOBE_API_URL", "WOOBE_WORKSPACE_ID", "WOOBE_PROJECT_ID"]:
                env[name] = ""
            commands = {"agent-list": ["agent", "list"], "agent-get": ["agent", "get", AGENTS[0]["id"]], "network-list": ["network", "list"], "auth-status": ["auth", "status"], "doctor": ["doctor"], "context-list": ["context", "list"]}
            rows, sections = [], []
            for name, command in commands.items():
                outputs = {}
                for mode in ["json", "text", "compact"]:
                    output = subprocess.check_output([binary, *command, "--config", str(config), "--output", mode], env=env, text=True)
                    output = output.replace(origin, "http://localhost:8000")
                    outputs[mode] = output
                    (examples / f"{name}.{mode}.txt").write_text(output)
                old, new = len(outputs["json"].encode()), len(outputs["compact"].encode())
                rows.append(f"| `woobe {' '.join(command)}` | {old:,} | {new:,} | {100 * (1 - new / old):.1f}% |")
                before = outputs["json"].strip()
                if name == "doctor":
                    before = before[:260] + " ... [display excerpt; full response in linked file]"
                sections.append(f"## `woobe {' '.join(command)}`\n\nPrevious JSON ([full response](examples/output/{name}.json.txt)):\n\n```text\n{before}\n```\n\nNew terminal view:\n\n```text\n{outputs['text'].strip()}\n```\n\nNew `--output compact`:\n\n```json\n{outputs['compact'].strip()}\n```\n")
            report = "# Output comparison\n\nGenerated by `scripts/output_examples.py` against a local fixture API using the real CLI. These are demonstration records, not user resources. `--output json` represents the previous complete envelope.\n\nThe table measures UTF-8 output bytes, not model tokens. Token savings depend on the tokenizer. Field selection changes presentation, not HTTP requests or authorization. No rows or IDs are truncated.\n\n| Command | Previous JSON bytes | Compact bytes | Reduction |\n| --- | ---: | ---: | ---: |\n" + "\n".join(rows) + "\n\n" + "\n".join(sections)
            (destination / "OUTPUT_EXAMPLES.md").write_text(report)
            print("\n".join(rows))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
