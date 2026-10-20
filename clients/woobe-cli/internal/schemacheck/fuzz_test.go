package schemacheck

import (
	"bytes"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"testing"
)

func FuzzSchemaCheck(f *testing.F) {
	for _, seed := range []string{`true`, `{"type":"object"}`, `{"allOf":[{},false]}`, `{"$ref":"#"}`, `{"properties":{"x":{"type":"integer"}}}`, `{"enum":[1,1.0]}`, `{"format":"uuid"}`, `{"format":"date-time"}`, `{"required":["id"],"properties":{"id":{"readOnly":true}}}`, `{"not":{"$ref":"#"}}`} {
		f.Add([]byte(seed), []byte(`{"x":1}`))
	}
	f.Fuzz(func(t *testing.T, schema, value []byte) {
		if len(schema) > 4096 || len(value) > 4096 || jsoninput.Validate(schema) != nil || jsoninput.Validate(value) != nil {
			t.Skip()
		}
		read := func(b []byte) any {
			var v any
			d := json.NewDecoder(bytes.NewReader(b))
			d.UseNumber()
			if e := d.Decode(&v); e != nil {
				t.Fatal(e)
			}
			return v
		}
		s, v := read(schema), read(value)
		_ = Check(s, v, s)
		_ = CheckRequest(s, v, s)
	})
}
