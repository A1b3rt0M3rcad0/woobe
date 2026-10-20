package schemacheck

import "testing"

func TestRequestDirectionRequiredAndForbiddenFields(t *testing.T) {
	s := decode(`{"type":"object","required":["id","secret"],"properties":{"id":{"type":"string","readOnly":true},"secret":{"type":"string","writeOnly":true}}}`)
	for _, tc := range []struct {
		value string
		valid bool
	}{
		{`{"secret":"private"}`, true}, {`{}`, false}, {`{"id":"server","secret":"private"}`, false}, {`{"id":null,"secret":"private"}`, false},
	} {
		if e := CheckRequest(s, decode(tc.value), nil); (e == nil) != tc.valid {
			t.Fatal(tc.value, e)
		}
	}
	// Neutral schema checks still apply the original required set.
	if Check(s, decode(`{"secret":"private"}`), nil) == nil {
		t.Fatal("neutral semantics changed")
	}
}

func TestRequestDirectionThroughReferencesAndAllOf(t *testing.T) {
	doc := decode(`{"components":{"schemas":{"ID":{"allOf":[{"type":"string"},{"readOnly":true}]}}}}`)
	s := decode(`{"required":["id"],"properties":{"id":{"$ref":"#/components/schemas/ID"},"children":{"type":"array","items":{"properties":{"id":{"readOnly":true}}}}}}`)
	if e := CheckRequest(s, decode(`{"children":[{}]}`), doc); e != nil {
		t.Fatal(e)
	}
	for _, value := range []string{`{"id":"server"}`, `{"children":[{"id":"server"}]}`} {
		if CheckRequest(s, decode(value), doc) == nil {
			t.Fatal(value)
		}
	}
}

func TestRequestDirectionDoesNotGuessConditionalAnnotations(t *testing.T) {
	for _, schema := range []string{
		`{"properties":{"id":{"not":{"readOnly":true}}}}`,
		`{"if":{"properties":{"id":{"readOnly":true}}},"then":true}`,
		`{"properties":{"id":{"readOnly":true,"writeOnly":true}}}`,
	} {
		e := CheckRequest(decode(schema), decode(`{}`), nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(schema, e)
		}
	}
}

func TestPredicateReferenceInspectionIsSeparate(t *testing.T) {
	doc := decode(`{"properties":{"a":{"$ref":"#/components/schemas/ID"}},"not":{"$ref":"#/components/schemas/ID"},"components":{"schemas":{"ID":{"readOnly":true}}}}`)
	// Keep definitions outside the schema: components is an OpenAPI keyword.
	s := decode(`{"properties":{"a":{"$ref":"#/components/schemas/ID"}},"not":{"$ref":"#/components/schemas/ID"}}`)
	e := CheckRequest(s, decode(`{}`), doc)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}

func TestRecursiveRequiredDirectionRemainsBounded(t *testing.T) {
	doc := decode(`{"components":{"schemas":{"ID":{"$ref":"#/components/schemas/ID"}}}}`)
	s := decode(`{"required":["id"],"properties":{"id":{"$ref":"#/components/schemas/ID"}}}`)
	e := CheckRequest(s, decode(`{}`), doc)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}

func TestSupportedFormats(t *testing.T) {
	for _, tc := range []struct {
		format, value string
		valid         bool
	}{
		{"uuid", "6BA7B810-9DAD-11D1-80B4-00C04FD430C8", true},
		{"uuid", "00000000-0000-0000-0000-000000000000", true},
		{"uuid", "6ba7b8109dad11d180b400c04fd430c8", false},
		{"uuid", "urn:uuid:6ba7b810-9dad-11d1-80b4-00c04fd430c8", false},
		{"uuid", "6ba7b810-9dad-11d1-80b4-00c04fd430cz", false},
		{"date", "2024-02-29", true}, {"date", "2026-02-29", false},
		{"date", "2026-1-01", false}, {"date", "2026-10-05T00:00:00Z", false},
		{"date-time", "2026-10-05t20:40:46.123456789123z", true},
		{"date-time", "2026-10-05T20:40:46-03:00", true},
		{"date-time", "2016-12-31T23:59:60Z", true},
		{"date-time", "2017-01-01T00:59:60+01:00", true},
		{"date-time", "2016-12-31T22:59:60Z", false},
		{"date-time", "2026-10-05T20:40:46", false},
		{"date-time", "2026-10-05T20:40:46+24:00", false},
		{"date-time", "2026-10-05T20:40:46+01:60", false},
		{"date-time", "2026-10-05T24:00:00Z", false},
		{"date-time", "2026-02-29T20:40:46Z", false},
		{"date-time", "2026-10-05T20:40:46,123Z", false},
	} {
		t.Run(tc.format+"/"+tc.value, func(t *testing.T) {
			s := map[string]any{"type": "string", "format": tc.format}
			if e := Check(s, tc.value, nil); (e == nil) != tc.valid {
				t.Fatal(e)
			}
		})
	}
	if e := Check(decode(`{"format":"uuid"}`), nil, nil); e != nil {
		t.Fatal("format applied to non-string", e)
	}
}

func TestFormatAndDialectDeclarationsFailClosed(t *testing.T) {
	for _, schema := range []string{
		`{"format":4}`, `{"format":"uri"}`, `{"format":""}`,
		`{"properties":{"absent":{"format":"unknown"}}}`,
		`{"$schema":"https://json-schema.org/draft-07/schema"}`, `{"$schema":true}`,
	} {
		e := Check(decode(schema), nil, nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(schema, e)
		}
	}
	for _, dialect := range []string{"https://json-schema.org/draft/2020-12/schema", "https://spec.openapis.org/oas/3.1/dialect/base"} {
		if e := Check(map[string]any{"$schema": dialect}, nil, nil); e != nil {
			t.Fatal(e)
		}
	}
}

func TestAdvertisedDialectDoesNotEnableLegacyNullable(t *testing.T) {
	for _, doc := range []any{
		decode(`{"openapi":"3.1.0"}`),
		decode(`{"jsonSchemaDialect":"https://json-schema.org/draft/2020-12/schema"}`),
		decode(`{"$schema":"https://json-schema.org/draft/2020-12/schema"}`),
	} {
		e := CheckRequest(decode(`{"properties":{"absent":{"type":"string","nullable":true}}}`), decode(`{}`), doc)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(doc, e)
		}
	}
	for _, schema := range []string{
		`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string","nullable":true}`,
		`{"$schema":"https://json-schema.org/draft/2020-12/schema","properties":{"absent":{"nullable":true}}}`,
		`{"properties":{"absent":{"$schema":"https://json-schema.org/draft/2020-12/schema","nullable":false}}}`,
	} {
		e := CheckRequest(decode(schema), nil, nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(schema, e)
		}
	}
	if e := CheckRequest(decode(`{"type":"string","nullable":true}`), nil, nil); e != nil {
		t.Fatal("unversioned legacy subset changed", e)
	}
	if e := CheckRequest(decode(`{"type":["string","null"]}`), nil, decode(`{"openapi":"3.1.0"}`)); e != nil {
		t.Fatal(e)
	}
}
