package jsoninput

import "testing"

func TestAmbiguousJSON(t *testing.T) {
	for _, s := range []string{`{"a":1,"a":2}`, `{"nested":[{"x":0,"x":1}]}`, `{} {}`, `[`, ``} {
		if Validate([]byte(s)) == nil {
			t.Fatal(s)
		}
	}
	if e := Validate([]byte(`{"a":null,"b":[1,{"x":2}]}`)); e != nil {
		t.Fatal(e)
	}
}
