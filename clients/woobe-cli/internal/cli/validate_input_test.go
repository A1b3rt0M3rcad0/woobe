package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestValidateInputMakesOnlyDiscoveryRead(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.Method != "GET" || r.URL.Path != "/openapi.json" {
			t.Error("operation executed")
		}
		_, _ = w.Write([]byte(`{"paths":{"/ai/agents":{"post":{"requestBody":{"content":{"application/json":{"schema":{"$ref":"#/components/schemas/Agent"}}}}}}},"components":{"schemas":{"Agent":{"type":"object","required":["name"],"properties":{"name":{"type":"string","minLength":1}}}}}}`))
	}))
	defer s.Close()
	for _, tc := range []struct {
		body string
		code int
	}{{`{"name":"A"}`, 0}, {`{}`, 2}, {`{"name":null}`, 2}} {
		code, _ := invoke(t, []string{"validate-input", "--command", "project agent create", "--file", "-", "--api-url", s.URL}, tc.body)
		if code != tc.code {
			t.Fatal(code)
		}
	}
	if n != 3 {
		t.Fatal(n)
	}
}
