package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/url"
	"testing"
)

func parameter(name, location, typ string, required bool) map[string]any {
	return map[string]any{"name": name, "in": location, "required": required, "schema": map[string]any{"type": typ}}
}
func TestParameterDeclarationsAndPrimitiveValidation(t *testing.T) {
	doc := map[string]any{"openapi": "3.1.0"}
	path := map[string]any{"parameters": []any{parameter("id", "path", "string", true)}}
	def := map[string]any{"parameters": []any{parameter("limit", "query", "integer", false), parameter("enabled", "query", "boolean", false)}}
	for _, tc := range []struct {
		query url.Values
		code  int
	}{
		{url.Values{"limit": {"2"}, "enabled": {"true"}}, 0},
		{url.Values{"limit": {"2.5"}}, 2},
		{url.Values{"limit": {"2", "3"}}, 2},
		{url.Values{"enabled": {"yes"}}, 2},
		{url.Values{"unknown": {"x"}}, 9},
	} {
		e := validateParameterSchema(doc, path, def, map[string]string{"id": "a"}, tc.query)
		if e == nil && tc.code != 0 || e != nil && output.Normalize(e).Code != tc.code {
			t.Fatal(tc, e)
		}
	}
}
func TestOperationParameterOverride(t *testing.T) {
	path := map[string]any{"parameters": []any{parameter("limit", "query", "string", false)}}
	def := map[string]any{"parameters": []any{parameter("limit", "query", "integer", true)}}
	if e := validateParameterSchema(map[string]any{}, path, def, nil, url.Values{"limit": {"3"}}); e != nil {
		t.Fatal(e)
	}
	if e := validateParameterSchema(map[string]any{}, path, def, nil, nil); e == nil || output.Normalize(e).Code != 2 {
		t.Fatal(e)
	}
	def["parameters"] = []any{parameter("limit", "query", "integer", true), parameter("limit", "query", "string", false)}
	if _, e := parameterDeclarations(map[string]any{}, path, def); e == nil {
		t.Fatal("duplicate accepted")
	}
}

func TestNullableAndReferencedParameterSerialization(t *testing.T) {
	doc := map[string]any{"openapi": "3.1.0", "components": map[string]any{"schemas": map[string]any{"Limit": map[string]any{"anyOf": []any{map[string]any{"type": "integer", "minimum": float64(1)}, map[string]any{"type": "null"}}}}}}
	p := parameter("limit", "query", "string", false)
	p["schema"] = map[string]any{"$ref": "#/components/schemas/Limit"}
	def := map[string]any{"parameters": []any{p}}
	for _, tc := range []struct {
		value string
		code  int
	}{{"2", 0}, {"0", 2}, {"null", 2}, {"1 garbage", 2}, {"2.5", 2}} {
		e := validateParameterSchema(doc, nil, def, nil, url.Values{"limit": {tc.value}})
		if e == nil && tc.code != 0 || e != nil && output.Normalize(e).Code != tc.code {
			t.Fatal(tc, e)
		}
	}
	p["schema"] = map[string]any{"type": []any{"integer", "string"}}
	if e := validateParameterSchema(doc, nil, def, nil, url.Values{"limit": {"2"}}); e == nil || output.Normalize(e).Code != 9 {
		t.Fatal(e)
	}
}

func TestQueryArraySerializationAndConstraints(t *testing.T) {
	p := parameter("ids", "query", "array", false)
	p["schema"] = map[string]any{"type": "array", "items": map[string]any{"type": "integer"}, "uniqueItems": true, "maxItems": float64(2)}
	def := map[string]any{"parameters": []any{p}}
	for _, tc := range []struct {
		values []string
		code   int
	}{{[]string{"1", "2"}, 0}, {[]string{"1", "1"}, 2}, {[]string{"1", "2", "3"}, 2}, {[]string{"x"}, 2}} {
		e := validateParameterSchema(map[string]any{}, nil, def, nil, url.Values{"ids": tc.values})
		if e == nil && tc.code != 0 || e != nil && output.Normalize(e).Code != tc.code {
			t.Fatal(tc, e)
		}
	}
	p["explode"] = false
	if e := validateParameterSchema(map[string]any{}, nil, def, nil, url.Values{"ids": {"1,2"}}); e != nil {
		t.Fatal(e)
	}
	if e := validateParameterSchema(map[string]any{}, nil, def, nil, url.Values{"ids": {"1", "2"}}); e == nil {
		t.Fatal("duplicate non-exploded arrays accepted")
	}
}

func TestAdvertisedTemplateAliasesRetainCanonicalArgumentNames(t *testing.T) {
	doc := map[string]any{"paths": map[string]any{"/core/projects/{access_project_id}/access": map[string]any{"post": map[string]any{"parameters": []any{parameter("access_project_id", "path", "string", true)}}}}}
	op := Operation{Method: "POST", Path: "/core/projects/{project_id}/access"}
	if e := validateOperationParameters(doc, op, map[string]string{"project_id": "p"}, nil); e != nil {
		t.Fatal(e)
	}
	if _, e := operationDefinition(doc, op); e != nil {
		t.Fatal(e)
	}
	paths := doc["paths"].(map[string]any)
	paths["/core/projects/{another_id}/access"] = paths["/core/projects/{access_project_id}/access"]
	if _, e := operationDefinition(doc, op); e == nil || output.Normalize(e).Code != 9 {
		t.Fatal("ambiguous route accepted", e)
	}
}
