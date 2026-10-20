package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"testing"
)

func TestProtectedToolCompileRoundTrip(t *testing.T) {
	plan := `{"schema_version":"2","project_id":"p","resources":[{"key":"tool","kind":"Tool","action":"create","spec":{"config":{"headers":{"Authorization":{"$secret_ref":"tool-auth"}}}}}]}`
	code, v := invoke(t, []string{"manifest", "compile", "--file", "-"}, plan)
	if code != 0 {
		t.Fatal(code, v)
	}
	b, _ := json.Marshal(v["data"].(map[string]any)["document"])
	d, e := manifest.Parse(b)
	if e != nil {
		t.Fatal(e, string(b))
	}
	if len(stepSecretNames(d.Steps[0])) != 1 {
		t.Fatal("compiled marker lost", string(b))
	}
}
