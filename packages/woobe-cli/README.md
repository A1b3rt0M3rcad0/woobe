# Woobe CLI

Minimal control-plane client. Authorization is enforced by the Woobe backend; the CLI does not implement a second permission model.

Install locally:

```bash
uv tool install ./packages/woobe-cli
```

Configure:

```bash
export WOOBE_API_URL=http://localhost:8000
export WOOBE_API_KEY=woobe_control_...
```

Examples:

```bash
woobe control-key list --workspace <workspace-id>

woobe request GET /core/projects --query workspace_id=<workspace-id>

woobe request POST /ai/agents --data @agent.json

woobe request PATCH /network/<network-id>/draft --data @network.json

woobe request POST /knowledge/documents/upload \
  --form project_id=<project-id> \
  --form collection_id=<collection-id> \
  --file file=./manual.pdf
```

`woobe request` intentionally exposes the complete HTTP control-plane surface. Resource-specific commands can be added without changing the server-side authorization model.
