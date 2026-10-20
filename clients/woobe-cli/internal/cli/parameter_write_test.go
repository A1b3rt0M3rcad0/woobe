package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestParameterValidationPreventsWritesAndReads(t *testing.T) {
	writes, reads := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}":{"parameters":[{"name":"agent_id","in":"path","required":true,"schema":{"type":"string","format":"uuid"}}],"get":{},"patch":{}}}}`))
			return
		}
		if r.Method == "GET" {
			reads++
		} else {
			writes++
		}
		w.Write([]byte(`{"id":"ok"}`))
	}))
	defer s.Close()
	for _, verb := range []string{"get", "update"} {
		code, v := invoke(t, []string{"project", "agent", verb, "not-a-uuid", "--file", "-", "--yes", "--api-url", s.URL, "--validate-parameters"}, "{}")
		if code != 2 {
			t.Fatal(code, v)
		}
		if verb == "update" && v["error"].(map[string]any)["write_outcome"] != "not_attempted" {
			t.Fatal(v)
		}
	}
	if writes != 0 || reads != 0 {
		t.Fatal(writes, reads)
	}
	code, v := invoke(t, []string{"project", "agent", "get", "550e8400-e29b-41d4-a716-446655440000", "--api-url", s.URL, "--validate-parameters"}, "{}")
	if code != 0 || reads != 1 {
		t.Fatal(code, v, reads)
	}
}
func TestParameterValidationCannotBeIgnored(t *testing.T) {
	for _, args := range [][]string{{"request", "GET", "/anything"}, {"runtime", "target", "run", "alias"}, {"version"}} {
		code, v := invoke(t, append(args, "--validate-parameters"), "")
		if code != 9 {
			t.Fatal(code, v)
		}
	}
}

func TestValidateInputParameterOnlyIsReadOnly(t *testing.T) {
	calls := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.Path != "/openapi.json" {
			t.Error("operation executed")
		}
		w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}":{"get":{"parameters":[{"name":"agent_id","in":"path","required":true,"schema":{"type":"string","format":"uuid"}}]}}}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"validate-input", "--command", "project agent get", "--validate-parameters", "--path-param", "agent_id=550e8400-e29b-41d4-a716-446655440000", "--api-url", s.URL}, "")
	if code != 0 || calls != 1 {
		t.Fatal(code, v, calls)
	}
	data := v["data"].(map[string]any)
	if data["path_query_validation"] != "supported_schema_subset" || data["body_validation"] != "not_evaluated" || data["executed"] != false {
		t.Fatal(v)
	}
}
