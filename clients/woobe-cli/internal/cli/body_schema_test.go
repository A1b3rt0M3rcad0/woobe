package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"testing"
)

func schemaDoc(s string) map[string]any {
	var v map[string]any
	json.Unmarshal([]byte(s), &v)
	return v
}
func TestSharedBodySchema(t *testing.T) {
	def := schemaDoc(`{"requestBody":{"content":{"application/json":{"schema":{"required":["name"]}}}}}`)
	if e := validateBodySchema(nil, def, []byte(`{"name":"A"}`)); e != nil {
		t.Fatal(e)
	}
	if e := validateBodySchema(nil, def, []byte(`{}`)); output.Normalize(e).Code != 2 {
		t.Fatal(e)
	}
}

func TestRequestBodyReferenceChains(t *testing.T) {
	doc := schemaDoc(`{"components":{"requestBodies":{"a":{"$ref":"#/components/requestBodies/b"},"b":{"content":{"application/json":{"schema":true}}}}}}`)
	def := schemaDoc(`{"requestBody":{"$ref":"#/components/requestBodies/a"}}`)
	if e := validateBodySchema(doc, def, []byte(`{}`)); e != nil {
		t.Fatal(e)
	}
	doc["components"] = schemaDoc(`{"requestBodies":{"a":{"$ref":"#/components/requestBodies/a"}}}`)
	if e := validateBodySchema(doc, def, []byte(`{}`)); output.Normalize(e).Code != 9 {
		t.Fatal(e)
	}
}

func TestActualJSONMediaMatching(t *testing.T) {
	for _, media := range []string{"application/json", "application/*", "*/*"} {
		def := schemaDoc(`{"requestBody":{"content":{"` + media + `":{"schema":true}}}}`)
		if e := validateBodySchema(nil, def, []byte(`{}`)); e != nil {
			t.Fatal(e)
		}
	}
	def := schemaDoc(`{"requestBody":{"content":{"application/custom+json":{"schema":true}}}}`)
	if output.Normalize(validateBodySchema(nil, def, []byte(`{}`))).Code != 9 {
		t.Fatal("wrong media accepted")
	}
}

func TestOptionalBodyAndRequiredDeclaration(t *testing.T) {
	if e := validateBodySchema(nil, map[string]any{}, nil); e != nil {
		t.Fatal(e)
	}
	if e := validateBodySchema(nil, schemaDoc(`{"requestBody":{"required":true}}`), nil); output.Normalize(e).Code != 2 {
		t.Fatal(e)
	}
	if e := validateBodySchema(nil, schemaDoc(`{"requestBody":{"required":"yes"}}`), nil); output.Normalize(e).Code != 9 {
		t.Fatal(e)
	}
}
