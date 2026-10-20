package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAdvertisedSchemaValidationIsReadOnly(t *testing.T) {
	for _, tc := range []struct {
		name, schema, body string
		code               int
	}{
		{"dependencies", `{"dependentRequired":{"provider":["model"]}}`, `{"provider":"x"}`, 2},
		{"condition", `{"if":{"required":["kind"]},"then":{"required":["config"]}}`, `{"kind":"x","config":null}`, 0},
		{"patterns", `{"patternProperties":{"^option_":{"type":"boolean"}},"additionalProperties":false}`, `{"option_a":true}`, 0},
		{"numeric enum", `{"enum":[1]}`, `1.0`, 0},
		{"inactive unsupported", `{"properties":{"hidden":{"format":"email"}}}`, `{}`, 9},
		{"malformed inactive", `{"properties":{"hidden":{"required":"x"}}}`, `{}`, 9},
		{"huge exponent", `{}`, `1e1000000000`, 9},
	} {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.Method != http.MethodGet || r.URL.Path != "/openapi.json" {
					t.Error("mutation attempted")
				}
				_, _ = w.Write([]byte(`{"paths":{"/ai/agents":{"post":{"requestBody":{"content":{"application/json":{"schema":` + tc.schema + `}}}}}}}`))
			}))
			defer s.Close()
			code, v := invoke(t, []string{"validate-input", "--command", "project agent create", "--file", "-", "--api-url", s.URL}, tc.body)
			if code != tc.code || calls != 1 {
				t.Fatal(code, calls, v)
			}
			if code == 0 && v["data"].(map[string]any)["executed"] != false {
				t.Fatal(v)
			}
		})
	}
}
