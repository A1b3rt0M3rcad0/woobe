package manifest

import "testing"

func TestCanonicalHash(t *testing.T) {
	a := Document{Steps: []Step{{ID: "a", Command: "x", Body: []byte(`{"a":1,"b":2}`)}}}
	b := a
	b.Steps = []Step{{ID: "a", Command: "x", Body: []byte(`{ "b": 2, "a": 1 }`)}}
	if a.Hash() != b.Hash() {
		t.Fatal("format changed plan identity")
	}
	b.Steps[0].Body = []byte(`{"a":null,"b":2}`)
	if a.Hash() == b.Hash() {
		t.Fatal("null ignored")
	}
}
