package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestProtectedPreflightNeverReadsCredentialValues(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/openapi.json" {
			t.Fatal("mutation attempted")
		}
		w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/credentials":{"post":{"requestBody":{"required":true,"content":{"application/json":{"schema":{"type":"object","required":["api_key"],"properties":{"api_key":{"type":"string"}}}}}}}}}}`))
	}))
	defer server.Close()
	plan := `{"schema_version":"1","project_id":"p","steps":[{"id":"s","command":"project provider-credential create","body":{"api_key":{"$secret_ref":"missing"}}}]}`
	for _, require := range []bool{false, true} {
		args := []string{"manifest", "preflight", "--project", "p", "--api-url", server.URL, "--file", "-"}
		if require {
			args = append(args, "--require-complete")
		}
		code, v := invoke(t, args, plan)
		if require && code != 9 || !require && code != 0 {
			t.Fatal(code, v)
		}
		data := v["data"].(map[string]any)
		if data["complete"] != false {
			t.Fatal(v)
		}
		row := data["operations"].([]any)[0].(map[string]any)
		if row["body_validation"] != "deferred_protected_credential" || row["secret_values_read"] != false {
			t.Fatal(row)
		}
	}
}
