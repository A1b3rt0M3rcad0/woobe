package cli

import "strings"

// Catalog annotations describe the inspected feature branch, never grant authority.
func permissionHint(op Operation) string {
	if op.Command == "project provider-credential rotate" {
		return "provider:credential:rotate"
	}
	if op.Command == "project provider-credential revoke" {
		return "provider:credential:revoke"
	}
	if op.Command == "project agent release create" || op.Command == "project agent release test" {
		return "agent:version"
	}
	read := op.Method == "GET"
	verb := "write"
	if read {
		verb = "read"
	}
	if op.Method == "DELETE" {
		verb = "delete"
	}
	for _, entry := range []struct{ prefix, family string }{{"workspace control-key ", "keys"}, {"project env ", "project:environment"}, {"project api-key ", "api_key"}, {"project runtime-key ", "api_key"}, {"project knowledge ", "knowledge"}, {"project provider-model ", "model"}, {"project provider-credential ", "provider"}, {"project skill ", "skill"}, {"project trace ", "observability"}, {"project usage ", "usage"}} {
		if strings.HasPrefix(op.Command, entry.prefix) {
			if entry.family == "keys" {
				action := strings.Fields(op.Command)[len(strings.Fields(op.Command))-1]
				if action == "list" || action == "get" {
					action = "read"
				}
				return "keys:" + action
			}
			if entry.family == "api_key" && verb == "delete" {
				verb = "write"
			}
			return entry.family + ":" + verb
		}
	}
	for _, family := range []string{"agent", "network", "tool", "surface"} {
		if strings.HasPrefix(op.Command, "project "+family+" ") {
			if family == "surface" {
				family = "chat_surface"
			}
			if op.Effect == "publication" {
				if family == "chat_surface" {
					return "chat_surface:release"
				}
				return family + ":production"
			}
			return family + ":" + verb
		}
	}
	return ""
}
