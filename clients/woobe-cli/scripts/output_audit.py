#!/usr/bin/env python3
"""Audit every discovered command; measure only explicit, successful scenarios."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from output_examples import AGENTS, IDENTITY, OPENAPI, PROJECT, WORKSPACE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path("docs"))
    args = parser.parse_args()
    binary = str(args.binary.resolve())
    registry = json.loads(subprocess.check_output([binary, "help", "--output", "json"]))["data"]
    current = {}
    openapi = json.loads(json.dumps(OPENAPI))
    for op in registry:
        if op["kind"] == "http":
            openapi["paths"].setdefault(op["path"], {})[op["method"].lower()] = {"responses": {"200": {"description": "Presentation fixture"}}, "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}}}

    class API(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self):
            if self.command in ["POST", "PATCH", "PUT"]:
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            path = self.path.split("?", 1)[0]
            if path == "/openapi.json":
                value = openapi
            elif path == "/identity/control-key/me":
                value = {"success": True, "data": IDENTITY}
            else:
                op = current.get("op", {})
                name = op.get("command", "fixture")
                if name.startswith("project agent ") and name.split()[-1] in ["list", "get", "create", "update"] and len(name.split()) == 3:
                    data = AGENTS if name.endswith(" list") else AGENTS[0]
                else:
                    data = {"id": "00000000-0000-7000-8000-000000000001", "name": "Demonstracao", "status": "active", "description": "Presentation fixture; not a domain-validation test", "revision": 1, "created_at": "2026-10-07T12:00:00Z", "updated_at": "2026-10-07T12:00:00Z"}
                    if name.endswith(" list") or name.endswith(" sessions") or name.endswith(" messages"):
                        data = [data]
                if op.get("pagination"):
                    items = data if isinstance(data, list) else [data]
                    data = {"items": items, "complete": True, "has_next": False, "next_cursor": None, "next_revision": None}
                value = {"success": True, "data": data}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", '"fixture-revision"')
            self.end_headers()
            self.wfile.write(json.dumps(value).encode())

        do_GET = respond
        do_POST = respond
        do_PATCH = respond
        do_PUT = respond
        do_DELETE = respond

    server = ThreadingHTTPServer(("127.0.0.1", 0), API)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = []
    cleanup_config = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cleanup_config = root / "cleanup.json"
            origin = f"http://127.0.0.1:{server.server_port}"
            env = {**os.environ, "WOOBE_CONTROL_KEY": "fixture-only", "WOOBE_OUTPUT": "auto"}
            for name in ["WOOBE_CONTEXT", "WOOBE_CREDENTIAL", "WOOBE_RUNTIME_CREDENTIAL", "WOOBE_API_URL", "WOOBE_WORKSPACE_ID", "WOOBE_PROJECT_ID"]:
                env[name] = ""
            body = root / "body.json"
            body.write_text("{}")
            for index, op in enumerate(registry):
                command, kind = op["command"], op["kind"]
                row = {"command": command, "kind": kind, "previous_bytes": "", "compact_bytes": "", "reduction_percent": "", "scenario": "", "note": ""}
                if kind == "alias":
                    row.update(scenario="delegated", note="Alias; use the corresponding canonical operation row")
                elif kind == "shell-completion":
                    row.update(scenario="preserved script", note="Shell script, not a JSON response; compact does not apply")
                elif command in ["runtime target stream", "runtime target observe"]:
                    row.update(scenario="preserved stream", note="JSONL event protocol; compact is intentionally unsupported")
                elif kind in ["package-http", "runtime-sdk", "composition", "http-projection"]:
                    row.update(scenario="not measured", note="Requires a dedicated operation/recovery/SDK scenario; no invented reduction")
                else:
                    outputs = {}
                    for mode in ["json", "compact"]:
                        config = root / f"config-{index}-{mode}.json"
                        config.write_text(json.dumps({"version": 1, "current": "woobe", "contexts": {"woobe": {"api_url": origin, "workspace_id": WORKSPACE, "project_id": PROJECT}}}))
                        invocation = command.split()
                        current["op"] = op
                        if kind == "http":
                            invocation += ["00000000-0000-7000-8000-000000000001"] * len(op.get("path_parameters") or [])
                            if op.get("body_required"):
                                request = {}
                                if command == "project tool mcp set":
                                    request = {"tool_id": AGENTS[0]["id"], "permissions": [{"remote_tool_name": "demo", "mode": "allow"}]}
                                elif command == "project tool mcp bulk":
                                    request = {"tool_id": AGENTS[0]["id"], "mode": "allow"}
                                body.write_text(json.dumps(request))
                                invocation += ["--file", str(body)]
                            if op.get("secret_emission"):
                                invocation += ["--secret-file", str(root / f"secret-{index}-{mode}.json")]
                            invocation += ["--yes"]
                        elif command == "schema":
                            invocation += ["--command", "project agent create", "--kind", "input"]
                        elif command == "server-schema":
                            invocation += ["--command", "project agent create"]
                        elif command == "validate-input":
                            body.write_text("{}")
                            invocation += ["--command", "project agent create", "--file", str(body)]
                        elif command == "context create":
                            invocation += ["nova", "--api-url", origin]
                        elif command in ["context update", "context set"]:
                            invocation += ["woobe", "--api-url", origin]
                        elif command in ["context use", "context delete"]:
                            invocation += ["woobe"]
                        elif command == "auth logout":
                            invocation += ["--cli-key"]
                        elif command == "context project select":
                            invocation += ["chatbot", "--dry-run"]
                        elif command == "context unset":
                            invocation += ["woobe", "project"]
                        elif command in ["context credential detach", "context runtime-credential detach"]:
                            invocation += ["woobe"]
                        elif command in ["auth credential import", "auth credential remove", "context credential attach", "context runtime-credential attach"]:
                            subprocess.run([binary, "auth", "credential", "import", "--name", "fixture-ref", "--stdin", "--config", str(config), "--output", "json"], input=b"fixture-only", env=env, capture_output=True, check=True)
                            if command == "auth credential import":
                                invocation += ["--name", "imported", "--stdin"]
                            elif command == "auth credential remove":
                                invocation += ["fixture-ref"]
                            else:
                                invocation += ["woobe", "--runtime-credential" if "runtime-credential" in command else "--credential", "fixture-ref"]
                        elif command == "manifest kinds":
                            pass
                        elif command == "request":
                            invocation += ["GET", "/ai/agents"]
                        elif command == "request-pages":
                            invocation += ["/ai/agents"]
                        elif command not in ["help", "version", "doctor", "context list", "context show", "auth credential list"]:
                            break
                        result = subprocess.run([binary, *invocation, "--config", str(config), "--output", mode], input=b"fixture-only" if command == "auth credential import" else None, env=env, capture_output=True, timeout=20)
                        if result.returncode != 0:
                            row["note"] = "Scenario did not complete: " + (result.stdout + result.stderr).decode(errors="replace")[:180].replace("\n", " ")
                            break
                        outputs[mode] = result.stdout.replace(origin.encode(), b"http://localhost:8000")
                    if len(outputs) == 2:
                        before, after = len(outputs["json"]), len(outputs["compact"])
                        row.update(previous_bytes=before, compact_bytes=after, reduction_percent=round(100 * (1 - after / before), 1), scenario="HTTP presentation fixture" if kind == "http" else "local/diagnostic scenario")
                        if command == "context project select":
                            row["note"] = "Dry-run selection; authentication/project mutation is not executed"
                    else:
                        row["scenario"] = "not measured"
                        row["note"] = row["note"] or "Requires a dedicated valid input/state scenario; no invented reduction"
                rows.append(row)
    finally:
        # Native Windows credentials outlive temporary directories. Remove only
        # the dummy references in this audit's unique credential-store namespace.
        if cleanup_config is not None:
            for reference in ["fixture-ref", "imported"]:
                subprocess.run([binary, "auth", "credential", "remove", reference, "--config", str(cleanup_config), "--output", "json"], capture_output=True, timeout=10)
        server.shutdown()
        server.server_close()
        thread.join()
    destination = args.destination
    destination.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (destination / "OUTPUT_AUDIT.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    measured = sum(r["previous_bytes"] != "" for r in rows)
    lines = ["# Complete command output audit", "", f"Every discovered command is listed: {len(rows)} entries, {measured} successful measured scenarios.", "", "Measurements are UTF-8 bytes from the real executable, comparing full JSON to compact. HTTP commands use a loopback presentation fixture; except the Agent records, response shapes are generic probes, not authoritative Woobe DTOs. These numbers are illustrative and do not qualify actual backend writes or estimate production token counts. Local scenarios use temporary state. All remote writes go only to the fixture API. Blank sizes mean not measured, never zero. Scripts, aliases and streams have explicit classifications.", "", "[Download CSV](OUTPUT_AUDIT.csv). More realistic six-command examples are in [OUTPUT_EXAMPLES.md](OUTPUT_EXAMPLES.md).", "", "| Command | Previous bytes | Compact bytes | Reduction | Scenario / limitation |", "| --- | ---: | ---: | ---: | --- |"]
    for row in rows:
        reduction = f"{row['reduction_percent']}%" if row["reduction_percent"] != "" else "—"
        note = (row["scenario"] + (": " + row["note"] if row["note"] else "")).replace("|", "/").replace("\n", " ")
        lines.append(f"| `{row['command']}` | {row['previous_bytes'] or '—'} | {row['compact_bytes'] or '—'} | {reduction} | {note} |")
    (destination / "OUTPUT_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} catalog entries; {measured} measured scenarios; {len(rows)-measured} classified without fabricated metrics")


if __name__ == "__main__":
    main()
