package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestServerSchemaInheritedParameters(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents":{"parameters":[{"name":"scope","in":"query"}],"post":{"requestBody":{}}}}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"server-schema", "--command", "project agent create", "--api-url", s.URL}, "")
	if code != 0 || v["data"].(map[string]any)["path_parameters"] == nil {
		t.Fatal(v)
	}
	code, _ = invoke(t, []string{"server-schema", "--command", "context list", "--api-url", s.URL}, "")
	if code != 2 {
		t.Fatal(code)
	}
}
