package cli

import (
	"bytes"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/schemacheck"
	"strings"
)

// These canonical permission rules are enforced without optional schema flags.
func validateMCPPermissions(command string, b []byte) error {
	if command != "project tool mcp set" && command != "project tool mcp bulk" {
		return nil
	}
	var body any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	if d.Decode(&body) != nil {
		return output.New(2, "MCP permissions require a JSON object")
	}
	mode := map[string]any{"enum": []any{"allow", "deny", "review"}}
	text := map[string]any{"type": "string", "minLength": json.Number("1"), "maxLength": json.Number("256")}
	risk := map[string]any{"anyOf": []any{text, map[string]any{"type": "null"}}}
	permission := map[string]any{"type": "object", "additionalProperties": false, "required": []any{"remote_tool_name", "mode"}, "properties": map[string]any{"remote_tool_name": text, "mode": mode, "risk_level": risk}}
	props := map[string]any{"tool_id": map[string]any{"type": "string", "format": "uuid"}}
	required := []any{"tool_id"}
	if command == "project tool mcp set" {
		props["permissions"] = map[string]any{"type": "array", "minItems": json.Number("1"), "maxItems": json.Number("1000"), "items": permission}
		required = append(required, "permissions")
	} else {
		props["mode"] = mode
		props["risk_level"] = risk
		required = append(required, "mode")
	}
	schema := map[string]any{"type": "object", "additionalProperties": false, "required": required, "properties": props}
	if e := schemacheck.CheckRequest(schema, body, schema); e != nil {
		return schemaError(e)
	}
	object := body.(map[string]any)
	check := func(obj map[string]any) error {
		for _, key := range []string{"remote_tool_name", "risk_level"} {
			if value, ok := obj[key].(string); ok && (value == "" || value != strings.TrimSpace(value)) {
				return output.New(2, "MCP permission strings require nonblank values without surrounding whitespace")
			}
		}
		return nil
	}
	if command == "project tool mcp bulk" {
		return check(object)
	}
	names := map[string]bool{}
	for _, item := range object["permissions"].([]any) {
		obj := item.(map[string]any)
		if e := check(obj); e != nil {
			return e
		}
		name := obj["remote_tool_name"].(string)
		if names[name] {
			return output.New(2, "MCP remote tool names must be unique")
		}
		names[name] = true
	}
	return nil
}
