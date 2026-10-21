package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestYAMLRequestsReachExistingContract(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		decoder := json.NewDecoder(r.Body)
		decoder.UseNumber()
		var body map[string]any
		if err := decoder.Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["description"] != nil || body["count"] != json.Number("9007199254740993") {
			t.Error(body)
		}
		if _, ok := body["name"]; ok {
			t.Error("omitted field was invented")
		}
		w.Write([]byte(`{"data":{"id":"agent"}}`))
	}))
	defer server.Close()
	args := []string{"project", "agent", "update", "agent", "--project", "project", "--api-url", server.URL, "--file", "-", "--input-format", "yaml"}
	code, result := invoke(t, args, "description: null\ncount: 9007199254740993")
	if code != 0 || requests != 1 {
		t.Fatal(code, result, requests)
	}
	code, result = invoke(t, args, "description: one\ndescription: two")
	if code != 2 || requests != 1 {
		t.Fatal(code, result, requests)
	}
}
