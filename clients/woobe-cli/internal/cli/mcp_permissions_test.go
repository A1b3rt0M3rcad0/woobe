package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestInvalidMCPPermissionsNeverReachServer(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; w.Write([]byte(`{}`)) }))
	defer server.Close()
	for _, permissions := range []string{`[]`, `[{"remote_tool_name":"search","mode":"all"}]`, `[{"remote_tool_name":" search","mode":"allow"}]`, `[{"remote_tool_name":"search","mode":"review","conditions":{}}]`, `[{"remote_tool_name":"search","mode":"allow"},{"remote_tool_name":"search","mode":"deny"}]`} {
		body := `{"tool_id":"11111111-1111-4111-8111-111111111111","permissions":` + permissions + `}`
		code, _ := invoke(t, []string{"project", "tool", "mcp", "set", "--project", "p", "--api-url", server.URL, "--file", "-"}, body)
		if code != 2 {
			t.Fatal(code, body)
		}
	}
	if calls != 0 {
		t.Fatal(calls)
	}
}

func TestCanonicalMCPModesRemainExplicit(t *testing.T) {
	for _, mode := range []string{"allow", "deny", "review"} {
		body := []byte(`{"tool_id":"11111111-1111-4111-8111-111111111111","mode":"` + mode + `"}`)
		if e := validateMCPPermissions("project tool mcp bulk", body); e != nil {
			t.Fatal(mode, e)
		}
	}
}
