package cli

import "testing"

func TestManifestDocumentDiscovery(t *testing.T) {
	code, v := invoke(t, []string{"schema", "--command", "manifest validate", "--kind", "document"}, "")
	if code != 0 || v["data"].(map[string]any)["$id"] != "urn:woobe:manifest:steps:1" {
		t.Fatal(v)
	}
}
