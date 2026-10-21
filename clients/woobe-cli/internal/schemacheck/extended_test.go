package schemacheck

import "testing"

func TestSemanticNumericEquality(t *testing.T) {
	s := decode(`{"enum":[1,{"count":1}]}`)
	for _, v := range []string{`1.0`, `1e0`, `{"count":1.00}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`2`, `"1"`, `{"count":2}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestUniqueNumericItems(t *testing.T) {
	s := decode(`{"uniqueItems":true}`)
	for _, v := range []string{`[1,2]`, `[1,"1"]`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`[1,1.0]`, `[{"n":1},{"n":1e0}]`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestInvalidTypeDeclarations(t *testing.T) {
	for _, s := range []string{`{"type":[]}`, `{"type":"typo"}`, `{"type":["number",4]}`, `{"type":["null","null"]}`} {
		e := Check(decode(s), nil, nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(s, e)
		}
	}
}

func TestMalformedAssertions(t *testing.T) {
	for _, s := range []string{`{"required":"name"}`, `{"enum":[]}`, `{"minItems":-1}`, `{"properties":[]}`, `{"uniqueItems":"yes"}`, `{"pattern":4}`, `{"$ref":4}`} {
		e := Check(decode(s), nil, nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(s, e)
		}
	}
}

func TestUnsupportedInactiveProperty(t *testing.T) {
	e := Check(decode(`{"type":"object","properties":{"absent":{"format":"email"}}}`), decode(`{}`), nil)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}

func TestObjectPropertyBounds(t *testing.T) {
	s := decode(`{"minProperties":1,"maxProperties":2}`)
	for _, v := range []string{`{"a":1}`, `{"a":null,"b":2}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{}`, `{"a":1,"b":2,"c":3}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestDependentRequired(t *testing.T) {
	s := decode(`{"dependentRequired":{"card":["billing"]}}`)
	for _, v := range []string{`{}`, `{"card":null,"billing":"A"}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{"card":"C"}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestDependentSchemas(t *testing.T) {
	s := decode(`{"dependentSchemas":{"card":{"required":["billing"]}}}`)
	for _, v := range []string{`{}`, `{"card":1,"billing":"B"}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{"card":1}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestPropertyNames(t *testing.T) {
	s := decode(`{"propertyNames":{"pattern":"^[a-z]+$"}}`)
	for _, v := range []string{`{}`, `{"name":1}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{"NAME":1}`, `{"name1":1}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestPatternProperties(t *testing.T) {
	s := decode(`{"patternProperties":{"^x":{"type":"integer"},"z$":{"minimum":2}},"additionalProperties":false}`)
	for _, v := range []string{`{"x":1}`, `{"xz":2}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{"x":"bad"}`, `{"other":2}`, `{"xz":1}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestConditionals(t *testing.T) {
	s := decode(`{"if":{"required":["flag"]},"then":{"required":["yes"]},"else":{"required":["no"]}}`)
	for _, v := range []string{`{"flag":null,"yes":1}`, `{"no":1}`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`{}`, `{"flag":1}`, `{"yes":1}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestPrefixItems(t *testing.T) {
	s := decode(`{"prefixItems":[{"type":"string"},{"type":"integer"}],"items":false}`)
	for _, v := range []string{`[]`, `["x"]`, `["x",1]`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`[1]`, `["x","y"]`, `["x",1,2]`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestContainsBounds(t *testing.T) {
	s := decode(`{"contains":{"type":"integer"},"minContains":1,"maxContains":2}`)
	for _, v := range []string{`["x",1]`, `[1,2]`} {
		if e := Check(s, decode(v), nil); e != nil {
			t.Fatal(v, e)
		}
	}
	for _, v := range []string{`[]`, `["x"]`, `[1,2,3]`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
}

func TestEvaluationBudget(t *testing.T) {
	sub := any(true)
	for i := 0; i < 18; i++ {
		sub = map[string]any{"allOf": []any{sub, sub}}
	}
	e := Check(sub, nil, nil)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}

func TestRecursiveSchemaInspection(t *testing.T) {
	doc := decode(`{"type":"object","properties":{"child":{"$ref":"#"}}}`)
	if e := Check(doc, decode(`{"child":{}}`), doc); e != nil {
		t.Fatal(e)
	}
}
func TestNumericEvaluationBounds(t *testing.T) {
	for _, v := range []string{"1e1000000000", "1e-1000000000"} {
		e := Check(decode(`{}`), decode(v), nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(e)
		}
	}
}
func TestMalformedInactiveComposition(t *testing.T) {
	e := Check(decode(`{"type":"object","properties":{"absent":{"allOf":4}}}`), decode(`{}`), nil)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}

func TestMalformedTypeUnionAndHugeEnum(t *testing.T) {
	for _, schema := range []string{`{"type":"null|object"}`, `{"enum":[1e1000000000]}`} {
		e := Check(decode(schema), nil, nil)
		if x, ok := e.(*Error); !ok || !x.Unsupported {
			t.Fatal(schema, e)
		}
	}
}

func TestNullablePreservesOtherConstraints(t *testing.T) {
	if Check(decode(`{"type":"string","nullable":true,"enum":["x"]}`), nil, nil) == nil {
		t.Fatal("enum bypassed")
	}
	if e := Check(decode(`{"type":"string","nullable":true}`), nil, nil); e != nil {
		t.Fatal(e)
	}
}
