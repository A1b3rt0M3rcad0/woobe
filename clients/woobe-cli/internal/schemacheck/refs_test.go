package schemacheck

import "testing"

func TestLocalReferencesAndComposition(t *testing.T) {
	doc := decode(`{"components":{"schemas":{"Count":{"type":"integer","minimum":1}}}}`)
	s := decode(`{"anyOf":[{"$ref":"#/components/schemas/Count"},{"type":"null"}]}`)
	for _, v := range []string{`null`, `2`} {
		if e := Check(s, decode(v), doc); e != nil {
			t.Fatal(e)
		}
	}
	if Check(s, decode(`0`), doc) == nil {
		t.Fatal("invalid")
	}
	if Check(decode(`{"$ref":"https://foreign/schema"}`), nil, doc) == nil {
		t.Fatal("external fetched")
	}
	if Check(decode(`{"anyOf":[{}, {"format":"email"}]}`), nil, doc) == nil {
		t.Fatal("unsupported hidden")
	}
}

func TestJSONPointerReferences(t *testing.T) {
	doc := decode(`{"a/b":{"~x":[{"type":"integer"}]},"space name":true}`)
	for _, ref := range []string{"#/a~1b/~0x/0", "#/space%20name"} {
		if _, e := Resolve(doc, ref); e != nil {
			t.Fatal(ref, e)
		}
	}
	if _, e := Resolve(doc, "#"); e != nil {
		t.Fatal(e)
	}
	for _, ref := range []string{"#/a~2b", "#/a~1b/~0x/00", "#/space%xxname", "#anchor"} {
		if _, e := Resolve(doc, ref); e == nil {
			t.Fatal(ref)
		}
	}
}

func TestInlineDefinitionsWithDocumentRelativeReferences(t *testing.T) {
	schema := map[string]any{"type": "object", "$defs": map[string]any{"Name": map[string]any{"type": "string", "minLength": float64(2)}}, "properties": map[string]any{"name": map[string]any{"$ref": "#/schema/$defs/Name"}}, "required": []any{"name"}}
	doc := map[string]any{"openapi": "3.1.0", "schema": schema}
	if e := CheckRequest(schema, map[string]any{"name": "ok"}, doc); e != nil {
		t.Fatal(e)
	}
	if e := CheckRequest(schema, map[string]any{"name": "x"}, doc); e == nil {
		t.Fatal("invalid definition value accepted")
	}
	schema["$defs"] = []any{}
	if e := CheckRequest(schema, map[string]any{"name": "ok"}, doc); e == nil {
		t.Fatal("invalid definitions accepted")
	}
}
