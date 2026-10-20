package cli

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

const directionSchema = `{"openapi":"3.1.0","paths":{"/ai/agents":{"post":{"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/Agent"}}}}}}},"components":{"schemas":{"Agent":{"type":"object","required":["id","model_id","created_at"],"properties":{"id":{"type":"string","readOnly":true},"model_id":{"type":"string","format":"uuid"},"created_at":{"type":"string","format":"date-time"}}}}}}`
const validDirectionBody = `{"model_id":"6ba7b810-9dad-11d1-80b4-00c04fd430c8","created_at":"2026-10-05T20:40:46-03:00"}`

func TestAdvertisedRequestDirectionAcrossEntryPoints(t *testing.T) {
	for _, command := range []string{"validate-input", "write", "preflight", "apply"} {
		for _, tc := range []struct {
			body  string
			valid bool
		}{
			{validDirectionBody, true},
			{`{"id":"server","model_id":"6ba7b810-9dad-11d1-80b4-00c04fd430c8","created_at":"2026-10-05T20:40:46Z"}`, false},
			{`{"model_id":"invalid","created_at":"2026-10-05T20:40:46Z"}`, false},
			{`{"model_id":"6ba7b810-9dad-11d1-80b4-00c04fd430c8","created_at":"2026-02-29T20:40:46Z"}`, false},
		} {
			t.Run(command+"/"+tc.body, func(t *testing.T) {
				reads, writes := 0, 0
				s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path == "/openapi.json" && r.Method == http.MethodGet {
						reads++
						w.Write([]byte(directionSchema))
						return
					}
					if r.URL.Path != "/ai/agents" || r.Method != http.MethodPost {
						t.Error("unexpected request", r.Method, r.URL.Path)
					}
					writes++
					w.Write([]byte(`{"id":"a"}`))
				}))
				defer s.Close()
				args, input := []string{}, tc.body
				switch command {
				case "validate-input":
					args = []string{"validate-input", "--command", "project agent create"}
				case "write":
					args = []string{"project", "agent", "create", "--validate-body"}
				case "preflight", "apply":
					args = []string{"manifest", command, "--project", "p"}
					input = `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":` + tc.body + `}]}`
					if command == "apply" {
						args = append(args, "--yes", "--validate-body", "--checkpoint", filepath.Join(t.TempDir(), "checkpoint"))
					}
				}
				args = append(args, "--file", "-", "--api-url", s.URL)
				code, result := invoke(t, args, input)
				want, wantWrites := 2, 0
				if tc.valid {
					want = 0
					if command == "write" || command == "apply" {
						wantWrites = 1
					}
				} else if command == "apply" {
					want = 10
				}
				if code != want || reads != 1 || writes != wantWrites {
					t.Fatal(code, reads, writes, result)
				}
				if !tc.valid && (command == "write" || command == "apply") && result["error"].(map[string]any)["write_outcome"] != "not_attempted" {
					t.Fatal(result)
				}
			})
		}
	}
}

func TestBodyValidationRejectsAmbiguousJSON(t *testing.T) {
	def := schemaDoc(`{"requestBody":{"content":{"application/json":{"schema":true}}}}`)
	for _, body := range []string{`{} {}`, `{"a":1,"a":2}`, `{"a":{"b":1,"b":2}}`, `null true`} {
		if e := validateBodySchema(nil, def, []byte(body)); output.Normalize(e).Code != 2 {
			t.Fatal(body, e)
		}
	}
}

func TestAdvertisedDialectGuard(t *testing.T) {
	def := schemaDoc(`{"requestBody":{"content":{"application/json":{"schema":true}}}}`)
	for _, tc := range []struct {
		doc  string
		code int
	}{
		{`{"openapi":"3.1.0"}`, 0}, {`{"openapi":"3.1.1"}`, 0},
		{`{"openapi":"3.1.0","jsonSchemaDialect":"https://json-schema.org/draft/2020-12/schema"}`, 0},
		{`{"openapi":"3.1.0","jsonSchemaDialect":"https://spec.openapis.org/oas/3.1/dialect/base"}`, 0},
		{`{"openapi":"3.0.3"}`, 9}, {`{"openapi":"3.2.0"}`, 9}, {`{"openapi":true}`, 9},
		{`{"jsonSchemaDialect":"https://json-schema.org/draft-07/schema"}`, 9}, {`{"jsonSchemaDialect":{}}`, 9},
	} {
		e := validateBodySchema(schemaDoc(tc.doc), def, []byte(`{}`))
		code := 0
		if e != nil {
			code = output.Normalize(e).Code
		}
		if code != tc.code {
			t.Fatal(tc.doc, code, e)
		}
	}
}

func TestLegacyNullableInModernDocumentDoesNotAuthorizeWrite(t *testing.T) {
	writes := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents":{"post":{"requestBody":{"content":{"application/json":{"schema":{"type":"string","nullable":true}}}}}}}}`))
			return
		}
		writes++
	}))
	defer s.Close()
	code, result := invoke(t, []string{"project", "agent", "create", "--validate-body", "--api-url", s.URL, "--file", "-"}, `null`)
	if code != 9 || writes != 0 || result["error"].(map[string]any)["write_outcome"] != "not_attempted" {
		t.Fatal(code, writes, result)
	}
}
