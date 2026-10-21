package output

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"unicode"
)

// Options controls presentation only; it never changes a request or saved data.
type Options struct {
	Mode, Command string
	Fields        []string
	Wide          bool
	StrictFields  bool
}

func ValidMode(mode string) bool {
	switch mode {
	case "auto", "text", "table", "compact", "json", "jsonl":
		return true
	}
	return false
}

func ValidateFields(fields []string) error {
	for _, field := range fields {
		for _, segment := range strings.Split(field, ".") {
			if segment == "" {
				return New(2, "--fields requires comma-separated field paths, such as id,name,status")
			}
			for _, c := range segment {
				if !unicode.IsLetter(c) && !unicode.IsDigit(c) && c != '_' && c != '-' && c != '$' {
					return New(2, "--fields contains an invalid field path; in PowerShell quote the list, e.g. --fields \"id,name\"")
				}
			}
		}
	}
	return nil
}

// WriteView keeps the full JSON/JSONL contract separate from concise views.
func WriteView(w io.Writer, options Options, data any, scope map[string]string, err error, meta map[string]any) error {
	if options.Mode == "json" || options.Mode == "jsonl" {
		return WriteWithMeta(w, options.Mode, data, scope, err, meta)
	}
	if options.Mode != "text" && options.Mode != "table" && options.Mode != "compact" {
		return New(2, "invalid output mode")
	}
	value, e := normalized(data)
	if e != nil {
		return e
	}
	value, inferred := unwrap(value)
	evidence := map[string]any{}
	for k, v := range inferred {
		evidence[k] = v
	}
	for k, v := range meta {
		evidence[k] = Redact(v)
	}
	// A successful command is not necessarily a complete collection/operation.
	if err != nil {
		evidence["complete"] = false
	} else if evidence["complete"] == true {
		delete(evidence, "complete")
	}
	if len(options.Fields) > 0 {
		if err == nil && data != nil && options.StrictFields {
			if missing := absentFields(value, options.Fields); len(missing) != 0 {
				return New(2, "--fields paths absent from response: "+strings.Join(missing, ", ")+"; inspect --wide or --output json")
			}
		}
		value = project(value, options.Fields, true)
	} else if !options.Wide {
		value = summarize(options.Command, value)
	}
	if options.Mode == "compact" {
		result := map[string]any{}
		if data != nil {
			result["data"] = value
		}
		if err != nil {
			result["error"] = Redact(Normalize(err))
		}
		if len(evidence) > 0 {
			result["meta"] = evidence
		}
		return json.NewEncoder(w).Encode(result)
	}
	return renderView(w, options, value, err, evidence)
}

func normalized(v any) (any, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var result any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	err = d.Decode(&result)
	return result, err
}

func unwrap(v any) (any, map[string]any) {
	meta := map[string]any{}
	for {
		obj, ok := v.(map[string]any)
		if !ok {
			return v, meta
		}
		for _, k := range []string{"meta", "pagination"} {
			if sub, ok := obj[k].(map[string]any); ok {
				for key, value := range sub {
					meta[key] = value
				}
			}
		}
		for _, k := range []string{"has_next", "next_cursor", "next_revision", "next_before_revision", "total", "page_count", "traversal_complete", "collection_complete", "next_query", "started_from_marker", "continuation"} {
			if value, ok := obj[k]; ok {
				meta[k] = value
			}
		}
		if pages, ok := obj["pages"].([]any); ok {
			if complete, exists := obj["complete"]; exists {
				meta["complete"] = complete
			}
			rows := []any{}
			for _, page := range pages {
				value, _ := unwrap(page)
				if list, ok := value.([]any); ok {
					rows = append(rows, list...)
				} else {
					rows = append(rows, value)
				}
			}
			return rows, meta
		}
		_, hasID := obj["id"]
		_, hasName := obj["name"]
		if items, ok := obj["items"].([]any); ok && !hasID && !hasName {
			if complete, exists := obj["complete"]; exists {
				meta["complete"] = complete
			}
			return items, meta
		}
		_, wrapped := obj["success"]
		if nested, ok := obj["data"]; ok && (wrapped || len(obj) == 1) {
			v = nested
			continue
		}
		return v, meta
	}
}

func lookup(v any, path string) (any, bool) {
	for _, part := range strings.Split(path, ".") {
		obj, ok := v.(map[string]any)
		if !ok {
			return nil, false
		}
		v, ok = obj[part]
		if !ok {
			return nil, false
		}
	}
	return v, true
}

func project(v any, fields []string, explicit bool) any {
	if rows, ok := v.([]any); ok {
		out := make([]any, len(rows))
		for i, row := range rows {
			out[i] = project(row, fields, explicit)
		}
		return out
	}
	if _, ok := v.(map[string]any); !ok {
		return v
	}
	out := map[string]any{}
	for _, field := range fields {
		value, ok := lookup(v, field)
		if ok {
			out[field] = value
		}
	}
	return out
}

func absentFields(value any, fields []string) []string {
	missing := map[string]bool{}
	var visit func(any)
	visit = func(v any) {
		if rows, ok := v.([]any); ok {
			for _, row := range rows {
				visit(row)
			}
			return
		}
		for _, field := range fields {
			if _, exists := lookup(v, field); !exists {
				missing[field] = true
			}
		}
	}
	visit(value)
	return sortedKeysBool(missing)
}

func sortedKeysBool(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

var relevantFields = []string{
	"name", "status", "state", "model", "provider", "type", "kind", "slug", "description", "id", "agent_id", "network_id", "run_id", "session_id", "operation_id",
	"version", "revision", "environment", "active", "enabled", "eligible", "terminal", "ready", "success", "valid", "authenticated", "executed",
	"action", "context", "api_url", "workspace_id", "project_id", "credential_source", "logged_out", "revoked", "method", "path",
	"message", "result", "output", "text", "content", "stopped_at", "checkpoint_saved", "counts", "diagnostics", "errors", "warnings", "complete", "apply_ready",
	"checkpoint", "inventory", "resource_id", "destination", "artifact_path", "plan_id", "plan_digest", "expires_at",
	"candidate_id", "preparation_operation_id", "evaluation_id", "publication_id", "release_id", "deployment_id", "draft_id", "revision_id", "upload_id", "export_id", "resource_uid", "registry_id", "workflow_id", "lease_id", "generation", "write_outcome", "pending", "next_command",
}

func summarize(command string, value any) any {
	if command == "project configuration bind" {
		if data, ok := value.(map[string]any); ok {
			if data["executed"] == false {
				return project(data, []string{"method", "path", "body", "executed"}, false)
			}
			result := project(data, []string{"target_kind", "target_id", "route_id", "revision"}, false).(map[string]any)
			if result["route_id"] == nil {
				delete(result, "route_id")
			}
			if auth, ok := data["authentication"].(map[string]any); ok {
				result["authentication"] = auth["type"]
				if fields, ok := auth["fields"].(map[string]any); ok {
					bindings, sources := map[string]any{}, map[string]any{}
					for name, raw := range fields {
						if ref, ok := raw.(map[string]any); ok {
							bindings[name], sources[name] = ref["key"], ref["source"]
						}
					}
					if len(bindings) > 0 {
						result["bindings"], result["sources"] = bindings, sources
					}
				}
			}
			return result
		}
	}
	if command == "init" {
		return project(value, []string{"initialized", "executed", "reused", "config", "root", "context", "agents", "instructions", "lab"}, false)
	}
	if command == "develop agent deploy" || command == "develop network deploy" {
		return project(value, []string{"kind", "resource_id", "intent_id", "source", "environment", "status", "release_id", "previous_release_id", "publication_id", "deployment_id", "generation_before", "generation_after", "actor", "write_outcome", "observed_current_matches", "executed", "server_qualification"}, false)
	}
	if command == "develop agent deployment" || command == "develop network deployment" {
		return project(value, []string{"kind", "state", "environment", "release_id", "publication_id", "plan_id", "deployment_id", "operation_id", "expected_generation", "generation_before", "generation_after", "selection_changed", "action", "reason", "expires_at", "executed", "method", "path", "body", "complete", "write_outcome"}, false)
	}

	if strings.HasPrefix(command, "develop ") && (strings.HasSuffix(command, " status") || strings.HasSuffix(command, " current") || strings.HasSuffix(command, " history") || strings.HasSuffix(command, " heads") || strings.HasSuffix(command, " revision")) {
		return value
	}
	if strings.HasPrefix(command, "skills ") {
		return value // Keep installation destinations and drift evidence visible.
	}
	if strings.HasPrefix(command, "package export ") {
		if obj, ok := value.(map[string]any); ok {
			summary := project(obj, []string{"name", "version", "destination", "integrity", "closure_complete", "self_contained", "knowledge", "next_command"}, false).(map[string]any)
			if source, ok := obj["source"].(map[string]any); ok {
				summary["source"] = project(source, []string{"environment", "version"}, false)
			}
			return summary
		}
	}
	if command == "package validate" {
		if obj, ok := value.(map[string]any); ok && obj["valid"] == true {
			summary := project(obj, []string{"valid", "validation_mode", "capture_integrity", "entrypoint", "artifact_digest", "authorization", "semantic_validation", "executed", "diagnostics"}, false).(map[string]any)
			if inventory, ok := obj["inventory"].([]any); ok {
				summary["files"] = len(inventory)
			}
			return summary
		}
	}
	if command == "package plan" {
		if obj, ok := value.(map[string]any); ok && obj["executed"] != false {
			summary := project(obj, []string{"plan_id", "project_id", "lifecycle", "expires_at", "artifact_digest", "bindings", "diagnostics", "permissions", "release_notes", "reason"}, false).(map[string]any)
			if effects, ok := obj["effects"].([]any); ok {
				summary["effects_count"] = len(effects)
				summary["effects"] = project(effects, []string{"key", "owner", "action", "permission", "state"}, false)
			}
			return summary
		}
	}
	if strings.HasPrefix(command, "schema") || command == "server-schema" || command == "validate-input" || strings.Contains(command, "manifest") || strings.HasPrefix(command, "package ") {
		// Schemas, plans and recovery evidence must not lose operational details.
		return value
	}
	if rows, ok := value.([]any); ok {
		out := make([]any, len(rows))
		fields := relevantFields
		switch command {
		case "help":
			fields = []string{"command", "method", "scope", "effect", "availability"}
		case "project agent list":
			fields = []string{"name", "status", "model", "id"}
		case "project network list":
			fields = []string{"name", "status", "id"}
		case "project agent release list":
			fields = []string{"version", "snapshot_kind", "status", "id", "created_at"}
		case "project network version list":
			fields = []string{"version", "kind", "id", "created_at"}
		}
		for i, row := range rows {
			selected := project(row, fields, false)
			if command != "project agent list" && command != "project network list" && command != "project agent release list" && command != "project network version list" && command != "help" {
				selected = summarize("", row)
			}
			if obj, ok := selected.(map[string]any); ok && len(obj) == 0 {
				selected = row // Unknown DTOs retain their data rather than show an empty result.
			}
			out[i] = selected
		}
		return out
	}
	obj, ok := value.(map[string]any)
	if !ok {
		return value
	}
	if command == "doctor" {
		checks := map[string]any{}
		if all, ok := obj["checks"].(map[string]any); ok {
			for name, check := range all {
				checks[name] = project(check, []string{"success", "error"}, false)
			}
		}
		advertised, total := 0, 0
		if routes, ok := obj["routes"].([]any); ok {
			total = len(routes)
			for _, route := range routes {
				if yes, _ := lookup(route, "advertised"); yes == true {
					advertised++
				}
			}
		}
		return map[string]any{"client_version": obj["client_version"], "checks": checks, "complete": obj["complete"], "advertised_routes": advertised, "reviewed_routes": total, "authorization": "not_evaluated"}
	}
	if command == "help" {
		return project(obj, []string{"command", "usage", "method", "path", "scope", "effect", "availability", "path_parameters", "body_required", "permission", "permission_source", "summary", "examples", "commands"}, false)
	}
	if command == "version" {
		return project(obj, []string{"version", "commit", "os", "arch", "go_version"}, false)
	}
	if command == "auth login" || command == "auth status" || command == "auth key inspect" {
		return authSummary(obj)
	}
	if command == "context list" {
		rows := []any{}
		if contexts, ok := obj["contexts"].(map[string]any); ok {
			for _, name := range sortedKeys(contexts) {
				row := project(contexts[name], []string{"api_url", "workspace_id", "project_id"}, false).(map[string]any)
				row["name"], row["current"] = name, name == obj["current"]
				rows = append(rows, row)
			}
		}
		return rows
	}
	if command == "project agent get" || command == "project agent create" || command == "project agent update" {
		return project(obj, relevantFields, false)
	}
	if strings.HasPrefix(command, "context ") || strings.HasPrefix(command, "auth credential ") {
		return obj
	}
	if obj["executed"] == false || obj["kind"] == "ResourceProjection" || obj["kind"] == "ManifestProjection" {
		return obj
	}
	// Unknown nested documents may contain usage, snapshots, graphs or bindings.
	// Never discard them just because their parent also has an ID or status.
	for _, sub := range obj {
		switch sub.(type) {
		case map[string]any, []any:
			return obj
		}
	}
	out := project(obj, relevantFields, false).(map[string]any)
	if len(out) == 0 {
		return obj
	}
	return out
}

func authSummary(obj map[string]any) any {
	out := project(obj, []string{"authenticated", "state", "context", "api_url", "credential_source"}, false).(map[string]any)
	identity := obj
	if nested, ok := obj["identity"].(map[string]any); ok {
		identity = nested
	}
	if workspace, ok := identity["workspace"]; ok {
		out["workspace"] = project(workspace, []string{"name", "id", "status"}, false)
	}
	if key, ok := identity["key_metadata"]; ok {
		out["key_metadata"] = project(key, []string{"name", "id", "expires_at"}, false)
	}
	projects, ok := identity["projects"].([]any)
	if !ok {
		return obj // Human-session status retains its existing shape.
	}
	eligible := []any{}
	for _, candidate := range projects {
		p, ok := candidate.(map[string]any)
		if !ok {
			continue
		}
		if p["id"] == obj["project_id"] && obj["project_id"] != "" {
			out["project"] = project(p, []string{"name", "id", "status"}, false)
		}
		if p["eligible"] == true {
			eligible = append(eligible, project(p, []string{"name", "id", "slug"}, false))
		}
	}
	out["available_project_count"] = len(eligible)
	if obj["state"] == "project_selection_required" || obj["project_id"] == nil {
		out["available_projects"] = eligible
	}
	return out
}

func sortedKeys(obj map[string]any) []string {
	keys := make([]string, 0, len(obj))
	for k := range obj {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func safeText(s string) string {
	return strings.Map(func(r rune) rune {
		if unicode.IsControl(r) {
			return ' '
		}
		return r
	}, s)
}

func encodeCell(value any) string {
	if value == nil {
		return "-"
	}
	if s, ok := value.(string); ok {
		return safeText(s)
	}
	b, _ := json.Marshal(value)
	return safeText(string(b))
}

func detail(w io.Writer, prefix string, value any) error {
	if obj, ok := value.(map[string]any); ok {
		for _, k := range orderedKeys(obj, nil) {
			if err := detail(w, prefix+safeText(k)+".", obj[k]); err != nil {
				return err
			}
		}
		return nil
	}
	label := strings.TrimSuffix(prefix, ".")
	if list, ok := value.([]any); ok {
		if _, err := fmt.Fprintf(w, "%s: %d items\n", label, len(list)); err != nil {
			return err
		}
		for i, item := range list {
			if err := detail(w, fmt.Sprintf("  %s[%d].", label, i), item); err != nil {
				return err
			}
		}
		return nil
	}
	_, err := fmt.Fprintf(w, "%s: %s\n", label, encodeCell(value))
	return err
}
