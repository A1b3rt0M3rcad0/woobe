package cli

import "testing"

func TestResourceManifestDiscoveryOffline(t *testing.T) {
	code, v := invoke(t, []string{"schema", "--command", "manifest validate", "--kind", "document", "--manifest-version", "2"}, "")
	if code != 0 || v["data"].(map[string]any)["$id"] != "urn:woobe:manifest:resources:2" {
		t.Fatal(v)
	}
	code, v = invoke(t, []string{"manifest", "kinds"}, "")
	if code != 0 || len(v["data"].([]any)) != 14 {
		t.Fatal(v)
	}
	code, v = invoke(t, []string{"manifest", "compile", "--file", "-", "--api-url", "http://127.0.0.1:1"}, `{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"create","spec":{"name":"A"}}]}`)
	if code != 0 || v["data"].(map[string]any)["executed"] != false {
		t.Fatal(v)
	}
}
