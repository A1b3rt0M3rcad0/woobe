package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
	"sort"
	"strings"
)

func artifactDiscoveryOperation(path string) (Operation, bool) {
	operations := map[string]Operation{
		"artifacts workspace list":    {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces", Scope: "project+environment", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", Pagination: controlplane.CursorHasNext},
		"artifacts workspace create":  {Kind: "runtime-artifact", Method: "POST", Path: "/v1/artifact-workspaces", Scope: "project+environment", Effect: "mutation", Status: "server-dependent", Permission: "artifact:write", PermissionSource: "runtime_key_grants", Body: true},
		"artifacts workspace resolve": {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces/resolve", Scope: "project+environment", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants"},
		"artifacts workspace get":     {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces/{workspace_id}", Scope: "project+environment", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants"},
		"artifacts workspace update":  {Kind: "runtime-artifact", Method: "PATCH", Path: "/v1/artifact-workspaces/{workspace_id}", Scope: "project+environment", Effect: "mutation", Status: "server-dependent", Permission: "artifact:write", PermissionSource: "runtime_key_grants", Body: true},
		"artifacts list":              {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces/{workspace_id}/artifacts", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", Pagination: controlplane.CursorHasNext},
		"artifacts get":               {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants"},
		"artifacts revision":          {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifacts/{artifact_id}/revisions/{revision_id}", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id"},
		"artifacts search":            {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifact-workspaces/{workspace_id}/search", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", Pagination: controlplane.CursorHasNext},
		"artifacts process":           {Kind: "runtime-artifact", Method: "POST", Path: "/v1/artifacts/{artifact_id}/processing", Scope: "project+environment+workspace", Effect: "execution", Status: "server-dependent", Permission: "artifact:process", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id", Body: true},
		"artifacts tree":              {Kind: "runtime-artifact", Method: "GET", Path: "/v1/document-indexes/{index_id}/nodes", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id", Pagination: controlplane.CursorHasNext},
		"artifacts read-node":         {Kind: "runtime-artifact", Method: "GET", Path: "/v1/document-indexes/{index_id}/nodes/{node_id}/content", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id"},
		"artifacts read-source":       {Kind: "runtime-artifact", Method: "POST", Path: "/v1/artifact-sources/read", Scope: "project+environment+workspace", Effect: "read", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id", Body: true},
		"artifacts upload":            {Kind: "runtime-artifact", Method: "POST", Path: "/v1/artifact-workspaces/{workspace_id}/uploads", Scope: "project+environment+workspace", Effect: "mutation", Status: "server-dependent", Permission: "artifact:write", PermissionSource: "runtime_key_grants", Body: true},
		"artifacts upload resume":     {Kind: "runtime-artifact-workflow", Scope: "project+environment+workspace", Effect: "reconcile_and_resume_upload", Status: "server-dependent", Permission: "artifact:write", PermissionSource: "runtime_key_grants"},
		"artifacts download":          {Kind: "runtime-artifact", Method: "GET", Path: "/v1/artifacts/{artifact_id}/revisions/{revision_id}/content", Scope: "project+environment+workspace", Effect: "read_stream", Status: "server-dependent", Permission: "artifact:read", PermissionSource: "runtime_key_grants", QueryScope: "artifact_workspace_id"},
		"artifacts move":              {Kind: "runtime-artifact", Method: "PATCH", Path: "/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}", Scope: "project+environment+workspace", Effect: "mutation", Status: "server-dependent", Permission: "artifact:write", PermissionSource: "runtime_key_grants", Body: true},
		"artifacts delete":            {Kind: "runtime-artifact", Method: "DELETE", Path: "/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}", Scope: "project+environment+workspace", Effect: "mutation", Status: "server-dependent", Permission: "artifact:delete", PermissionSource: "runtime_key_grants"},
	}
	operation, ok := operations[path]
	if ok {
		operation.Command = path
		operation.ID = strings.ReplaceAll(path, " ", ".")
		operation.Summary = "Direct Artifact API operation using the scoped Runtime Key"
	}
	return operation, ok
}

type FlagDescriptor struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
	Required    bool   `json:"required"`
}

// CompleteDiscovery derives executable command paths and flags from the actual
// Cobra tree. HTTP policy metadata remains attached to its registered handler.
func (a *App) completeDiscovery() {
	a.Root.InitDefaultCompletionCmd()
	known := map[string]int{}
	for i, op := range a.Registry {
		known[op.Command] = i
	}
	var walk func(*cobra.Command)
	walk = func(cmd *cobra.Command) {
		cmd.InitDefaultHelpFlag()
		path := strings.TrimPrefix(cmd.CommandPath(), "woobe ")
		if cmd.RunE != nil || cmd.Run != nil {
			i, ok := known[path]
			if !ok {
				kind, effect, availability := "local", "local", "local"
				switch {
				case strings.HasPrefix(path, "develop "):
					kind, effect, availability = "development", "local", "local"
					if strings.HasSuffix(path, " pull") {
						kind, effect, availability = "development-http", "export", "server-dependent"
					}
					if strings.HasSuffix(path, " push") {
						kind, effect, availability = "development-http", "mutation", "server-dependent"
					}
					if strings.HasSuffix(path, " current") {
						kind, effect, availability = "development-http", "read", "server-dependent"
					}
					if strings.HasSuffix(path, " deploy") {
						kind, effect, availability = "deployment-orchestration", "explicit_activation_or_read", "server-dependent"
					}
					if strings.HasSuffix(path, " history") {
						effect, availability = "local_history_or_remote_fetch", "local_or_server-dependent"
					}
					if strings.HasSuffix(path, " status") {
						effect, availability = "local_or_explicit_remote_read", "local_or_server-dependent"
					}
					if strings.HasSuffix(path, " revision") {
						effect = "local_checkpoint_or_read"
					}
				case strings.HasPrefix(path, "completion "):
					kind = "shell-completion"
					effect = "local"
				case strings.HasPrefix(path, "runtime target "):
					kind = "runtime-sdk"
					effect = "read"
					availability = "server-dependent"
					if strings.HasSuffix(path, " run") || strings.HasSuffix(path, " stream") || strings.HasSuffix(path, " cancel") {
						effect = "execution"
					}
				case path == "project knowledge document upload":
					kind = "multipart-http"
					effect = "mutation"
					availability = "observed"
				case path == "package plan":
					kind, effect, availability = "package-http", "planning", "server-dependent"
				case path == "package export agent" || path == "package export network":
					kind, effect, availability = "package-http", "export", "server-dependent"
				case path == "package import":
					kind, effect, availability = "package-http", "mutation", "server-dependent"
				case path == "package status":
					kind, effect, availability = "package-http", "read", "server-dependent"
				case path == "package cancel" || path == "package resume":
					kind, effect, availability = "package-http", "mutation", "server-dependent"
				case path == "project agent export" || path == "export" || path == "manifest export" || path == "manifest capture":
					kind = "http-projection"
					effect = "read"
					availability = "observed"
				case path == "request" || path == "request-pages":
					kind = "generic-http"
					effect = "specified_by_request"
					availability = "server-dependent"
				case path == "doctor" || path == "package doctor" || path == "server-schema" || path == "validate-input":
					kind = "diagnostic-http"
					effect = "read"
					availability = "server-dependent"
				case path == "auth logout":
					kind = "http-session"
					effect = "mutation"
					availability = "observed"
				case path == "manifest apply" || path == "manifest reconcile":
					kind = "composition"
					effect = "mutation"
				case path == "manifest preflight":
					kind = "diagnostic-http"
					effect = "read"
					availability = "server-dependent"
				case path == "manifest diff" || path == "workspace authority category diff":
					kind = "composition"
					effect = "read"
					availability = "server-dependent"
				case path == "agent" || path == "network" || path == "control-key":
					kind = "alias"
					effect = "delegated"
				}
				op := Operation{Command: path, ID: strings.ReplaceAll(path, " ", "."), Kind: kind, Effect: effect, Status: availability, Scope: "client", PermissionSource: "not_evaluated"}
				if artifactOperation, ok := artifactDiscoveryOperation(path); ok {
					op = artifactOperation
				}
				a.Registry = append(a.Registry, op)
				i = len(a.Registry) - 1
			}
			op := &a.Registry[i]
			if op.Kind == "" {
				op.Kind = "http"
			}
			op.Usage = cmd.UseLine()
			op.Summary = cmd.Short
			op.Details = cmd.Long
			if cmd.Example != "" {
				op.Examples = strings.Split(cmd.Example, "\n")
			}
			switch path {
			case "manifest validate", "manifest preflight", "manifest plan", "manifest diff", "manifest apply", "manifest reconcile", "manifest compile":
				op.Body = true
			}
			flags := map[string]FlagDescriptor{}
			add := func(f *pflag.Flag) {
				if f.Hidden || !packageVisibleFlag(path, f.Name) {
					return
				}
				_, required := f.Annotations[cobra.BashCompOneRequiredFlag]
				flags[f.Name] = FlagDescriptor{Name: f.Name, Type: f.Value.Type(), Description: f.Usage, Required: required}
			}
			cmd.InheritedFlags().VisitAll(add)
			cmd.Flags().VisitAll(add)
			op.Flags = nil
			for _, f := range flags {
				if f.Name == "file" && op.Body && path != "auth login" {
					f.Required = true
				}
				op.Flags = append(op.Flags, f)
			}
			sort.Slice(op.Flags, func(i, j int) bool { return op.Flags[i].Name < op.Flags[j].Name })
		}
		for _, child := range cmd.Commands() {
			walk(child)
		}
	}
	// help is installed explicitly so it is discoverable before Execute.
	walk(a.Root)
	sort.Slice(a.Registry, func(i, j int) bool { return a.Registry[i].Command < a.Registry[j].Command })
}

func flagSchema(f FlagDescriptor) map[string]any {
	t := "string"
	switch f.Type {
	case "bool":
		t = "boolean"
	case "int", "int64", "uint", "uint64":
		t = "integer"
	case "stringArray", "stringSlice":
		t = "array"
	}
	s := map[string]any{"type": t, "description": f.Description}
	if t == "array" {
		s["items"] = map[string]any{"type": "string"}
	}
	return s
}
func commandSchema(op Operation, kind string) map[string]any {
	s := map[string]any{"$schema": "https://json-schema.org/draft/2020-12/schema", "schema_version": "1", "operation": op, "kind": kind, "type": "object"}
	if kind == "input" {
		props := map[string]any{}
		required := []string{}
		for _, f := range op.Flags {
			props[f.Name] = flagSchema(f)
			if f.Required {
				required = append(required, f.Name)
			}
		}
		s["properties"] = map[string]any{"args": map[string]any{"type": "array", "items": map[string]any{"type": "string"}}, "flags": map[string]any{"type": "object", "properties": props, "required": required, "additionalProperties": false}, "body": map[string]any{"description": "Endpoint body; consult server-schema for authoritative domain fields"}}
		if op.Command == "runtime target run" || op.Command == "runtime target stream" {
			optionProperties := map[string]any{}
			for _, key := range []string{"session_id", "tenant_id", "user_id", "SessionID", "TenantID", "UserID"} {
				optionProperties[key] = map[string]any{"type": "string", "minLength": 1}
			}
			for _, key := range []string{"metadata", "external_context", "Metadata", "ExternalContext"} {
				optionProperties[key] = map[string]any{"type": "object"}
			}
			inputSchema := map[string]any{"type": "string", "minLength": 1, "pattern": `\S`}
			partsSchema := map[string]any{"type": "array", "minItems": 1, "maxItems": 32, "items": map[string]any{"oneOf": []any{
				map[string]any{"type": "object", "required": []string{"type", "text"}, "additionalProperties": false, "properties": map[string]any{"type": map[string]any{"const": "text"}, "text": map[string]any{"type": "string", "minLength": 1, "maxLength": 32768}}},
				map[string]any{"type": "object", "required": []string{"type", "ref"}, "additionalProperties": false, "properties": map[string]any{"type": map[string]any{"const": "artifact"}, "media_type_hint": map[string]any{"type": "string", "maxLength": 255}, "ref": map[string]any{"type": "object", "required": []string{"artifact_id", "revision_id"}, "additionalProperties": false, "properties": map[string]any{"artifact_id": map[string]any{"type": "string", "minLength": 1, "maxLength": 128}, "revision_id": map[string]any{"type": "string", "minLength": 1, "maxLength": 128}}}}},
			}}}
			bodySchema := map[string]any{"type": "object", "additionalProperties": false,
				"properties": map[string]any{"input": inputSchema, "content_parts": partsSchema,
					"session_id": map[string]any{"type": "string", "minLength": 1},
					"options":    map[string]any{"type": "object", "additionalProperties": false, "properties": optionProperties}}}
			bodySchema["oneOf"] = []any{
				map[string]any{"required": []string{"input"}, "properties": map[string]any{"input": inputSchema}, "not": map[string]any{"required": []string{"content_parts"}}},
				map[string]any{"required": []string{"content_parts"}, "properties": map[string]any{"input": map[string]any{"type": "string", "maxLength": 0}}},
			}
			s["properties"].(map[string]any)["body"] = bodySchema
		}
		if op.Command == "auth login" {
			flags := s["properties"].(map[string]any)["flags"].(map[string]any)
			flags["anyOf"] = []any{
				map[string]any{"required": []string{"cli-key"}, "properties": map[string]any{"cli-key": map[string]any{"const": true}, "file": map[string]any{"const": ""}, "validate-body": map[string]any{"const": false}, "validate-parameters": map[string]any{"const": false}, "schema-sha256": map[string]any{"const": ""}}},
				map[string]any{"required": []string{"file"}, "properties": map[string]any{"cli-key": map[string]any{"const": false}, "stdin": map[string]any{"const": false}, "select-project": map[string]any{"const": ""}}},
			}
		}
		s["additionalProperties"] = false
		s["description"] = "CLI invocation transport schema. Resource IDs accept positional arguments or named flags; server owns domain validation and authorization."
	} else if op.Kind == "shell-completion" {
		s["type"] = "string"
		s["description"] = "Shell completion script written as text"
	} else if strings.HasPrefix(op.Command, "runtime target ") && (strings.HasSuffix(op.Command, " stream") || strings.HasSuffix(op.Command, " observe")) {
		s["required"] = []string{"protocol_version", "event_id", "run_id", "session_id", "run_kind", "sequence", "type", "occurred_at", "payload"}
		s["properties"] = map[string]any{"protocol_version": map[string]any{"const": 2}, "event_id": map[string]any{"type": "string"}, "run_id": map[string]any{"type": "string"}, "session_id": map[string]any{"type": "string"}, "run_kind": map[string]any{"enum": []string{"AGENT", "NETWORK"}}, "sequence": map[string]any{"type": "integer", "minimum": 0}, "type": map[string]any{"type": "string"}, "occurred_at": map[string]any{"type": "string", "format": "date-time"}, "payload": map[string]any{"type": "object"}}
		s["additionalProperties"] = false
	} else {
		s["required"] = []string{"schema_version", "success", "meta"}
		s["properties"] = map[string]any{"schema_version": map[string]any{"const": "1"}, "success": map[string]any{"type": "boolean"}, "context": map[string]any{"type": "object", "additionalProperties": map[string]any{"type": "string"}}, "data": map[string]any{}, "error": map[string]any{"type": "object"}, "meta": map[string]any{"type": "object", "required": []string{"complete"}, "properties": map[string]any{"complete": map[string]any{"type": "boolean"}}}}
		s["additionalProperties"] = false
	}
	return s
}
