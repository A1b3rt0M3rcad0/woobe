package cli

import "testing"

func TestNestedCanonicalCreateIsNotMistakenForDevelopmentReference(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, group := range []string{"prompt", "contract", "release"} {
		code, reply := invoke(t, []string{"agent", group, "create", "native-agent", "--project", "project", "--file", "-", "--dry-run", "--output", "json"}, "{}")
		if code != 0 {
			t.Fatal(group, code, reply)
		}
		if reply["data"].(map[string]any)["path"] == "" {
			t.Fatal(reply)
		}
	}
}
