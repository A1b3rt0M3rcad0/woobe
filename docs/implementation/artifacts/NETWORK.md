# Network Artifact bindings

An Artifact-enabled Network declares one hidden External Context string field and
resolves that logical key to a Workspace during run acceptance. The Network stores
the accepted Workspace identity, catalog version, scope and action ceiling on its
Session and Run. The runtime principal snapshot contains authentication metadata only;
it never contains an API secret and is kept in private database fields.

Every Node can narrow the Network action ceiling with `artifact_actions`. At child
acceptance, the effective actions are the intersection of Network, Node and frozen
Agent Release policy. A Node with no actions receives no Artifact binding. The
child Agent's namespace, External Context field and scope must match the Network's
binding before Artifacts can be used. No Node or model argument can replace the
accepted Workspace ID.

The runtime reconstructs the same binding for retries, reattachment and reruns.
Artifact authorization still checks the current principal and grants for every
operation, so a saved binding preserves execution identity without preserving old
permissions. Session-scoped bindings cannot change Workspace; a run-scoped binding
also cannot change after that Network Session has history.

Package 2.0 Network settings use this shape:

```yaml
settings:
  artifacts_enabled: true
  artifact_workspace_binding:
    field: workspace_key
    namespace: customer-documents
    scope: session
    actions: [read, search, write]
nodes:
  - key: writer
    agent_ref: writer-agent
    artifact_actions: [write]
  - key: reader
    agent_ref: reader-agent
    artifact_actions: [read, search]
  - key: coordinator
    agent_ref: coordinator-agent
```

The Network, Node and Agent Release contracts all apply. A wider Node policy never
widens the root action ceiling, and a Node without `artifact_actions` cannot list,
inspect or open an Artifact through the runtime facade.
