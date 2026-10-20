package cli

import (
	"encoding/json"
	"net/url"
	"testing"
)

func FuzzParameterSchemaValidation(f *testing.F) {
	for _, seed := range []string{
		`{"type":"integer"}`, `{"anyOf":[{"type":"integer"},{"type":"null"}]}`,
		`{"type":"array","items":{"type":"string","format":"uuid"}}`, `{"$ref":"#/missing"}`,
		`{"type":["string","object"]}`, `{"properties":[]}`, `true`,
	} {
		f.Add(seed, "1")
	}
	f.Fuzz(func(t *testing.T, schemaText, value string) {
		if len(schemaText) > 16384 || len(value) > 16384 {
			return
		}
		var schema any
		if json.Unmarshal([]byte(schemaText), &schema) != nil {
			return
		}
		def := map[string]any{"parameters": []any{map[string]any{"name": "value", "in": "query", "schema": schema}}}
		_ = validateParameterSchema(map[string]any{"openapi": "3.1.0"}, nil, def, nil, url.Values{"value": {value}})
	})
}
