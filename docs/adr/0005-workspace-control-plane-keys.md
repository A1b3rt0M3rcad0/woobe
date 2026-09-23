# ADR 0005: Workspace control-plane keys

## Status

Accepted for implementation in `feat/cli-control-plane`.

## Context

Woobe currently has project/runtime API keys focused on runtime execution, traces and usage. They are not suitable as management credentials for CLI, CI/CD or coding agents because a project key is bound to one project and management endpoints reject API-key principals.

The control plane needs a non-user credential that belongs to a Workspace, can be granted access to one or more Projects, and carries explicit permissions for management operations.

## Decision

Introduce a new API-key kind named `control`.

A control key:

- belongs to exactly one Workspace;
- may have grants for one or more Projects in that Workspace;
- has Workspace-level permissions for Workspace/control-key operations;
- has Project-level permissions per Project grant;
- is revocable and rotatable;
- can never mutate, revoke or rotate its own credential;
- can never delegate a Workspace permission, Project grant or Project permission that it does not itself possess;
- is authorized by the backend. The CLI is only a client and contains no authoritative permission logic.

Project/runtime/chat-surface keys retain their current behavior.

## Permission vocabulary

Workspace permissions:

- `workspace:read`
- `keys:read`
- `keys:create`
- `keys:update`
- `keys:revoke`
- `keys:rotate`

Project permissions:

- `project:read`
- `project:update`
- `project:environment:read`
- `project:environment:write`
- `project:access:read`
- `project:access:write`
- `agent:read`, `agent:write`, `agent:delete`, `agent:version`, `agent:production`
- `network:read`, `network:write`, `network:delete`, `network:version`, `network:production`
- `tool:read`, `tool:write`, `tool:delete`, `tool:execute`
- `knowledge:read`, `knowledge:write`, `knowledge:delete`
- `provider:read`, `provider:write`, `provider:delete`
- `provider:credential:revoke`
- `model:read`, `model:write`, `model:delete`
- `skill:read`, `skill:write`, `skill:delete`, `skill:version`
- `observability:read`
- `usage:read`

## Authorization invariants

1. Workspace isolation is absolute.
2. A Project grant must reference a Project in the key's Workspace.
3. A control key may only access Projects for which it has an active grant.
4. A management operation requires the exact permission mapped to that operation.
5. Key management by another control key is subset-only: no privilege amplification.
6. The actor credential lineage cannot update, rotate, revoke or change its own grants/permissions.
7. Secret values are returned only at issuance/rotation, never by list/get endpoints.
8. User principals continue to use the existing Workspace/Project membership authorization paths.

## Consequences

The same HTTP control-plane API can be used by the web UI, CLI, CI/CD and coding agents. Authorization remains server-side and cannot be bypassed by calling the HTTP API directly.
