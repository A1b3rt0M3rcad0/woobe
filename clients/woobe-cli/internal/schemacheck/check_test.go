package schemacheck

import (
	"encoding/json"
	"strings"
	"testing"
)

func decode(s string) any {
	var v any
	d := json.NewDecoder(strings.NewReader(s))
	d.UseNumber()
	_ = d.Decode(&v)
	return v
}
func TestConstraints(t *testing.T) {
	s := decode(`{"type":"object","required":["count"],"additionalProperties":false,"properties":{"count":{"type":"integer","minimum":1,"maximum":9007199254740993},"label":{"type":"string","minLength":2}}}`)
	for _, v := range []string{`{}`, `{"count":0}`, `{"count":1.2}`, `{"count":9007199254740994}`, `{"count":1,"extra":true}`, `{"count":1,"label":"x"}`} {
		if Check(s, decode(v), nil) == nil {
			t.Fatal(v)
		}
	}
	if e := Check(s, decode(`{"count":9007199254740993}`), nil); e != nil {
		t.Fatal(e)
	}
}
func TestUnsupportedAssertions(t *testing.T) {
	e := Check(decode(`{"format":"email"}`), "invalid", nil)
	if x, ok := e.(*Error); !ok || !x.Unsupported {
		t.Fatal(e)
	}
}
