package cli

import (
	"bytes"
	"encoding/json"
	"github.com/spf13/cobra"
	"testing"
)

func TestDiscoveryCoversEveryExecutableHandler(t *testing.T) {
	a := New(&bytes.Buffer{}, &bytes.Buffer{}, &bytes.Buffer{})
	paths := map[string]Operation{}
	for _, op := range a.Registry {
		if _, ok := paths[op.Command]; ok {
			t.Fatalf("duplicate discovery path %s", op.Command)
		}
		paths[op.Command] = op
	}
	var walk func(*cobra.Command)
	walk = func(cmd *cobra.Command) {
		if cmd.Runnable() && cmd.Annotations["command_group"] != "true" {
			path := cmd.CommandPath()[len("woobe "):]
			op, ok := paths[path]
			if !ok {
				t.Errorf("undiscovered handler %s", path)
			}
			if op.Usage == "" || len(op.Flags) == 0 {
				t.Errorf("incomplete invocation metadata %s", path)
			}
		}
		for _, child := range cmd.Commands() {
			walk(child)
		}
	}
	walk(a.Root)
	for _, path := range []string{"manifest apply", "context credential attach", "auth credential import", "runtime target observe", "project knowledge document upload", "help", "schema", "completion bash"} {
		if _, ok := paths[path]; !ok {
			t.Fatal(path)
		}
	}
}
func TestLocalSchemaDescribesRealFlags(t *testing.T) {
	code, v := invoke(t, []string{"schema", "--command", "manifest apply", "--kind", "input"}, "")
	if code != 0 {
		t.Fatal(v)
	}
	data := v["data"].(map[string]any)
	flags := data["properties"].(map[string]any)["flags"].(map[string]any)["properties"].(map[string]any)
	if flags["checkpoint"] == nil || flags["yes"].(map[string]any)["type"] != "boolean" {
		t.Fatal(data)
	}
}
func TestStreamSchemaPreservesRuntimeProtocol(t *testing.T) {
	code, v := invoke(t, []string{"schema", "--command", "runtime target observe", "--kind", "output"}, "")
	if code != 0 {
		t.Fatal(v)
	}
	data := v["data"].(map[string]any)
	props := data["properties"].(map[string]any)
	if props["protocol_version"].(map[string]any)["const"] != float64(2) || props["run_id"] == nil {
		t.Fatal(data)
	}
}
func TestLocalActionsCannotBypassManifestOperationRestrictions(t *testing.T) {
	for _, command := range []string{"auth credential import", "manifest apply", "request", "runtime target run"} {
		b, _ := json.Marshal(map[string]any{"schema_version": "1", "steps": []any{map[string]any{"id": "unsafe", "command": command}}})
		code, _ := invoke(t, []string{"manifest", "validate", "--file", "-"}, string(b))
		if code != 2 {
			t.Fatalf("local %s accepted into HTTP composition", command)
		}
	}
}
