package output

import (
	"bytes"
	"strings"
	"testing"
)

func TestTableProjectsNestedServerList(t *testing.T) {
	out := &bytes.Buffer{}
	data := map[string]any{"success": true, "data": []any{map[string]any{"id": "agent-a", "name": "A\nB", "api_key": "must-not-leak"}}}
	if e := Write(out, "table", Redact(data), nil, nil); e != nil {
		t.Fatal(e)
	}
	s := out.String()
	if !strings.Contains(s, "ID") || !strings.Contains(s, "agent-a") || !strings.Contains(s, "A B") || strings.Contains(s, "must-not-leak") {
		t.Fatal(s)
	}
}
func TestTableScalarEmptyAndError(t *testing.T) {
	for _, data := range []any{[]any{}, []any{"agent:read"}, map[string]any{"id": "a"}, nil} {
		out := &bytes.Buffer{}
		if e := Write(out, "table", data, nil, nil); e != nil || out.Len() == 0 {
			t.Fatal(e)
		}
	}
	out := &bytes.Buffer{}
	if e := Write(out, "table", nil, nil, New(4, "denied")); e != nil || !strings.Contains(out.String(), "ERROR 4") {
		t.Fatal(e, out.String())
	}
}
